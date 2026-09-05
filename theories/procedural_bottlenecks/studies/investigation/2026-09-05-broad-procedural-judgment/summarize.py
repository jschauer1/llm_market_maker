"""Recompute same-capture prices and summarize coverage, never outcome effects."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
from statistics import median

from tools.atomic_write import write_json

STUDY = Path(__file__).resolve().parent
PREFIX = 'theories.procedural_bottlenecks.studies.investigation.2026-09-05-broad-procedural-judgment'
batches = importlib.import_module(PREFIX+'.batches')
books = importlib.import_module(PREFIX+'.capture_books')


def recompute(market):
    """Correct arithmetic from the exact retained quote, with no new request."""
    receipt = next((r for r in reversed(market.get('responses', {}).get('orderbook', []))
                    if r.get('status') == 200 and r.get('response_path')), None)
    if not receipt:
        return None
    body = Path(receipt['response_path']).read_bytes()
    if hashlib.sha256(body).hexdigest() != receipt['sha256']:
        raise ValueError('Retained orderbook hash mismatch')
    payload = json.loads(body)
    spec = market.get('fee') or {}
    fee = (books.FeeSpec.quadratic(spec['multiplier']) if spec.get('status') == 'verified_quadratic'
           else books.FeeSpec.unknown(spec.get('reason') or 'unverified'))
    return books.depth_curves(payload.get('orderbook_fp'), fee)


def summarize(root):
    exclusions_path = root/'quality-exclusions.json'
    exclusions = json.loads(exclusions_path.read_text(encoding='utf-8')) if exclusions_path.exists() else {}
    output = []
    seen = set()
    complete = 0
    review_files = []
    for original in sorted(root.glob('batch-*')):
        folder = Path(exclusions[original.name]['replacement']) if original.name in exclusions else original
        if not (folder/'receipt.json').exists():
            continue
        receipt, judgments = batches.read_first(folder)
        if len(judgments) != len(receipt.request.candidate_keys):
            continue
        complete += 1
        input_rows = {m['key']:m for e in receipt.request.payload['events'] for m in e['markets']}
        capture_path = folder/'book-capture.json'
        capture = json.loads(capture_path.read_text(encoding='utf-8')) if capture_path.exists() else {}
        for name in ('review.jsonl','qa-review.jsonl','root-review.jsonl'):
            if (folder/name).exists():
                review_files.append((folder/name).as_posix())
        for judgment in judgments:
            key = judgment['key']
            if key in seen:
                raise ValueError('Duplicate candidate across batches')
            seen.add(key)
            market = capture.get('markets', {}).get(key, {})
            metadata = market.get('market_metadata') or {}
            output.append(dict(key=key, batch=original.name, judgment_folder=folder.as_posix(),
                first_bucket=judgment['bucket'], subject_key=judgment['subject_key'],
                family=judgment['family'], category=input_rows[key].get('category'),
                event=input_rows[key]['event_key'], judgment=judgment,
                metadata={k:metadata.get(k) for k in ('status','open_time','created_time','close_time')},
                first_book_capture_at=capture.get('capture_started_utc'),
                capture_lag_seconds=capture.get('capture_lag_seconds'),
                corrected_depth_curves=recompute(market) if market else None))
    labels = Counter(r['first_bucket'] for r in output)
    categories = defaultdict(Counter)
    sides = defaultdict(lambda: defaultdict(list))
    missing = Counter()
    for row in output:
        label = row['first_bucket']
        categories[str(row['category'])][label] += 1
        curves = row['corrected_depth_curves']
        for side in ('buy_yes','buy_no'):
            curve = (curves or {}).get(side, {}).get('100', {})
            price = curve.get('average_payable')
            if price is None or row['metadata']['status'] != 'active':
                missing[f'{label}/{side}'] += 1
            else:
                sides[label][side].append(price)
    prices = {label:{side:dict(n=len(values), median_payable_100=median(values),
                               min_payable_100=min(values), max_payable_100=max(values))
                         for side,values in side_data.items()}
              for label,side_data in sides.items()}
    summary = dict(generated_at=datetime.now(timezone.utc).isoformat(),
        complete_batches=complete, expected_batches=len(list(root.glob('batch-*'))),
        rows=len(output), events=len({r['event'] for r in output}),
        first_labels=labels, categories=categories, active_payable_prices=prices,
        missing_or_inactive_quotes=missing, review_files=review_files,
        caveat='Original labels include documented errors. Reviews are separate; these are discovery coverage and price statistics, not probabilities, independent trials, or realized returns.')
    target=root.parent/'analysis'
    target.mkdir(exist_ok=True)
    write_json(target/'markets.json', output)
    write_json(target/'summary.json', summary)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('categories','review_files')},indent=2))


if __name__ == '__main__':
    summarize(STUDY/'data/judgments')
