"""Prepare immutable blind batches and ingest complete first outputs."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from tools.atomic_write import write_json
from tools.domain import Verdict
from tools.judgments import BatchRequest, JudgmentBatchReceipt, complete_batch, load_batch, write_payload

LABELS = {'substantive_barrier', 'plausible_path', 'formalities_only', 'insufficient_evidence', 'not_applicable'}


def chunks(events, limit=15, market_limit=70):
    chunk, count = [], 0
    for event in events:
        if chunk and (len(chunk) >= limit or count + len(event['markets']) > market_limit):
            yield chunk
            chunk, count = [], 0
        chunk.append(event)
        count += len(event['markets'])
    if chunk:
        yield chunk


def prepare(census, out, prompt):
    if out.exists():
        raise ValueError('Batch root already exists; resume the persisted manifest')
    out.mkdir(parents=True)
    source = json.loads(census.read_text(encoding='utf-8'))
    at = datetime.now(timezone.utc).isoformat()
    template = prompt.read_text(encoding='utf-8')
    manifest = dict(decision_at=at, snapshot_at=source['as_of'], requested_model='gpt-5.6-sol',
                    resolved_model=None, requested_effort='high', web_search=True, batches=[])
    for i, events in enumerate(chunks(source['events'])):
        folder = (out / f'batch-{i:03d}').resolve()
        folder.mkdir()
        payload = dict(decision_at=at, snapshot_at=source['as_of'], events=events)
        keys = [m['key'] for e in events for m in e['markets']]
        rendered = template + '\n\nBare input: ' + str(folder/'input.json') + '\nOutput: ' + str(folder/'first-output.jsonl') + '\n'
        request = BatchRequest.build(run_id='study/broad-procedural-20260905', theory_id='study/broad-procedural',
            theory_version=1, run_mode='study', decision_at=at, requested_model='gpt-5.6-sol',
            requested_effort='high', requested_web_search=True, output_path=folder/'first-output.jsonl',
            stage='analysis', batch_id=i, candidate_keys=keys, payload=payload, rendered_prompt=rendered)
        write_json(folder/'receipt.json', JudgmentBatchReceipt(request).to_dict())
        write_payload(folder/'input.json', request)
        (folder/'rendered-prompt.md').write_text(rendered, encoding='utf-8')
        manifest['batches'].append(dict(id=i, path=str(folder), events=len(events), markets=len(keys)))
    write_json(out/'manifest.json', manifest)
    # Work lists contain paths only; receipts/operator metadata stay off judge inputs.
    for worker in range(3):
        paths = [b['path'] for b in manifest['batches'] if b['id'] % 3 == worker]
        write_json(out/f'worker-{worker}.json', paths)
    print(json.dumps({k:v for k,v in manifest.items() if k!='batches'}))
    print(json.dumps(dict(batches=len(manifest['batches']), markets=sum(b['markets'] for b in manifest['batches']))))


def read_first(folder):
    receipt = load_batch(folder/'receipt.json')
    path = folder/'first-output.jsonl'
    if not path.exists():
        return receipt, []
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    keys = [r['key'] for r in rows]
    if len(keys) != len(set(keys)) or set(keys)-set(receipt.request.candidate_keys):
        raise ValueError(f'Duplicate/unexpected keys in {folder}')
    supplement_path = folder/'sources-supplement.jsonl'
    if supplement_path.exists():
        by_key = {r['key']:r for r in rows}
        seen = set()
        for line in supplement_path.read_text(encoding='utf-8-sig').splitlines():
            if not line.strip():
                continue
            supplement = json.loads(line)
            key = supplement.get('key')
            if (set(supplement) != {'key','sources','reason'} or key not in by_key
                    or key in seen or not supplement.get('sources') or not supplement.get('reason')):
                raise ValueError(f'Invalid source supplement in {folder}: {key}')
            seen.add(key)
            row = by_key[key]
            row['sources'] = row.get('sources', []) + supplement['sources']
            row['source_supplement_reason'] = supplement['reason']
    for row in rows:
        if row['bucket'] not in LABELS or not row.get('subject_key') or not row.get('rationale'):
            raise ValueError(f'Invalid verdict in {folder}: {row.get("key")}')
        if row['bucket'] in {'substantive_barrier', 'plausible_path', 'formalities_only'} and not row.get('sources'):
            raise ValueError(f'Affirmative classification without sources: {row["key"]}')
    return receipt, rows


def ingest(out):
    summary = dict(complete_batches=0, partial_batches=0, research_invalid_batches=0, repaired_batches=0, rows=0, labels=Counter(), families=Counter(), subjects=set())
    exclusions_path = out/'quality-exclusions.json'
    exclusions = json.loads(exclusions_path.read_text(encoding='utf-8')) if exclusions_path.exists() else {}
    all_rows = []
    for folder in sorted(out.glob('batch-*')):
        if folder.name in exclusions:
            summary['research_invalid_batches'] += 1
            replacement = Path(exclusions[folder.name]['replacement'])
            if not (replacement/'receipt.json').exists():
                continue
            original = load_batch(folder/'receipt.json').request
            replacement_request = load_batch(replacement/'receipt.json').request
            if original.payload_sha256 != replacement_request.payload_sha256 or original.candidate_keys != replacement_request.candidate_keys:
                raise ValueError('Repair must preserve the exact frozen cohort and payload')
            folder = replacement
        receipt, rows = read_first(folder)
        if len(rows) == len(receipt.request.candidate_keys):
            if not receipt.completed:
                complete_batch(folder/'receipt.json', model='gpt-5.6-sol', effort='high', web_search=True,
                    results={r['key']:Verdict(bucket=r['bucket'], rationale=json.dumps(r,sort_keys=True)) for r in rows})
            summary['complete_batches'] += 1
            if folder.parent != out.resolve() and folder.parent.resolve() != out.resolve():
                summary['repaired_batches'] += 1
        elif rows:
            summary['partial_batches'] += 1
        all_rows.extend(rows)
    for row in all_rows:
        summary['rows'] += 1
        summary['labels'][row['bucket']] += 1
        summary['families'][row['family']] += 1
        summary['subjects'].add(row['subject_key'])
    summary['subjects'] = len(summary['subjects'])
    write_json(out/'progress.json', summary)
    write_json(out/'all-judgments.json', all_rows)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['prepare','ingest'])
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--census', type=Path)
    p.add_argument('--prompt', type=Path)
    a = p.parse_args()
    if a.mode == 'prepare':
        prepare(a.census,a.out,a.prompt)
    else:
        ingest(a.out)
