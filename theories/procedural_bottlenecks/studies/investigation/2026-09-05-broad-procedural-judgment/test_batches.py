import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('broad_batches', Path(__file__).with_name('batches.py'))
batches = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batches)


def test_chunking_does_not_split_or_drop_event_subjects():
    events = [dict(event_key=str(i), markets=[{'key':f'{i}-{j}'} for j in range(n)]) for i,n in enumerate([80,2,60,10])]
    grouped = list(batches.chunks(events))
    assert [len(group) for group in grouped] == [1,2,1]
    assert [event for group in grouped for event in group] == events


def prepared(tmp_path):
    source = tmp_path/'census.json'
    source.write_text(json.dumps(dict(as_of='2026-09-05T15:45:16Z', events=[dict(event_key='A',markets=[dict(key='A-1')])])),encoding='utf-8')
    prompt = tmp_path/'prompt.md'
    prompt.write_text('Classify without prices',encoding='utf-8')
    out = tmp_path/'judgments'
    batches.prepare(source,out,prompt)
    return out,source,prompt


def test_persistence_and_completed_ingestion_are_idempotent(tmp_path):
    out,source,prompt=prepared(tmp_path)
    folder=out/'batch-000'
    verdict=dict(key='A-1',bucket='insufficient_evidence',subject_key='a',family='unknown',rationale='Missing dated source',sources=[])
    (folder/'first-output.jsonl').write_text(json.dumps(verdict)+'\n',encoding='utf-8')
    batches.ingest(out)
    receipt=(folder/'receipt.json').read_bytes()
    batches.ingest(out)
    assert receipt==(folder/'receipt.json').read_bytes()
    assert json.loads((out/'progress.json').read_text())['rows']==1
    with pytest.raises(ValueError,match='already exists'):
        batches.prepare(source,out,prompt)


def test_duplicate_or_sourceless_affirmative_judgments_are_rejected(tmp_path):
    out,_,_=prepared(tmp_path)
    folder=out/'batch-000'
    verdict=dict(key='A-1',bucket='substantive_barrier',subject_key='a',family='x',rationale='Claim without citation',sources=[])
    path=folder/'first-output.jsonl'
    path.write_text(json.dumps(verdict)+'\n',encoding='utf-8')
    with pytest.raises(ValueError,match='without sources'):
        batches.read_first(folder)
    path.write_text((json.dumps(verdict)+'\n')*2,encoding='utf-8')
    with pytest.raises(ValueError,match='Duplicate'):
        batches.read_first(folder)
