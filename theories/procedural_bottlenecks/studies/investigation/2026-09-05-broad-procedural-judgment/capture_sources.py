"""Retain cited public pages after judgment; capture success is not validation."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path

import requests

from tools.atomic_write import write_json

STUDY=Path(__file__).resolve().parent
batches=importlib.import_module('theories.procedural_bottlenecks.studies.investigation.2026-09-05-broad-procedural-judgment.batches')


def capture(url, root):
    key=hashlib.sha256(url.encode()).hexdigest()
    receipt=root/(key+'.json')
    if receipt.exists():
        return 'existing'
    record=dict(url=url, purpose='post-judgment preservation; not an as-of source-availability proof')
    try:
        response=requests.get(url, timeout=25, headers={'User-Agent':'MarketEdgeFinder-research-source-preservation/1.0'})
        body=response.content
        raw=root/(key+'.body')
        raw.write_bytes(body)
        record.update(status=response.status_code, final_url=response.url, bytes=len(body),
                      sha256=hashlib.sha256(body).hexdigest(), body_path=raw.as_posix())
    except requests.RequestException as exc:
        record.update(status=None,error=str(exc))
    record['captured_at']=datetime.now(timezone.utc).isoformat()
    write_json(receipt,record)
    return 'success' if record['status']==200 else 'failure'


def run():
    urls=set()
    root=STUDY/'data/judgments'
    exclusions=json.loads((root/'quality-exclusions.json').read_text(encoding='utf-8'))
    for original in root.glob('batch-*'):
        folder=Path(exclusions[original.name]['replacement']) if original.name in exclusions else original
        if not (folder/'receipt.json').exists():continue
        _,rows=batches.read_first(folder)
        for row in rows:
            urls.update(s['url'] for s in row.get('sources',[]) if str(s.get('url','')).startswith('https://'))
    out=STUDY/'data/cited-source-captures'
    out.mkdir(exist_ok=True)
    counts=dict(success=0,failure=0,existing=0)
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(capture,url,out) for url in sorted(urls)]
        for future in as_completed(futures):counts[future.result()]+=1
    write_json(out/'summary.json',dict(urls=len(urls),counts=counts))
    print(json.dumps(counts))


if __name__=='__main__':run()
