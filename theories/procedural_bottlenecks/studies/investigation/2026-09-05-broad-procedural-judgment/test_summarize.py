import importlib.util
import json
import hashlib
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('broad_summary', Path(__file__).with_name('summarize.py'))
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)


def test_recompute_keeps_capture_and_checks_raw_evidence(tmp_path):
    body=json.dumps({'orderbook_fp':{'yes_dollars':[['0.4','100']], 'no_dollars':[['0.7','100']]}}).encode()
    raw=tmp_path/'book.json'
    raw.write_bytes(body)
    row={'fee':{'status':'verified_quadratic','multiplier':1},
         'responses':{'orderbook':[{'status':200,'sha256':hashlib.sha256(body).hexdigest(),'response_path':str(raw),'captured_utc':'2026-09-05T20:00:00Z'}]},
         'depth_curves':{'old':'preserved'}}
    before=json.dumps(row)
    corrected=summary.recompute(row)
    assert corrected['buy_yes']['100']['fee_dollars']==1.47
    assert corrected['buy_yes']['100']['best_ask']==0.3
    assert corrected['buy_no']['100']['best_ask']==0.6
    assert json.dumps(row)==before
    raw.write_text('{}',encoding='utf-8')
    with pytest.raises(ValueError,match='hash'):
        summary.recompute(row)
