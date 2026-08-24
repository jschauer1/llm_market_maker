import pytest

from tools import db, ledger, provenance, theories

TS = "2026-08-23T12:00:00Z"


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    theories.register(c, "t1", "One", "theories/t1", now=TS)
    yield c
    c.close()


@pytest.fixture
def prompt_file(tmp_path):
    p = tmp_path / "analysis.md"
    p.write_text("Judge whether a specific group already knows.\n",
                 encoding="utf-8")
    return p


def _record(conn, **kw):
    base = dict(theory_id="t1", theory_version=1, kalshi_ticker="TICK",
                outcome="yes", entry_price=0.8, edge_pts_net=2.0)
    base.update(kw)
    return ledger.record_opportunity(conn, **base)


# --- hashing -----------------------------------------------------------


def test_prompt_sha_is_stable_across_line_endings():
    # A git checkout that rewrites CRLF must not look like prompt drift.
    assert provenance.prompt_sha("a\r\nb") == provenance.prompt_sha("a\nb")
    assert provenance.prompt_sha("a\rb") == provenance.prompt_sha("a\nb")


def test_prompt_sha_changes_when_the_prompt_changes():
    assert provenance.prompt_sha("judge X") != provenance.prompt_sha("judge Y")


def test_read_prompt_raises_for_a_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        provenance.read_prompt(tmp_path / "nope.md")


# --- recording ---------------------------------------------------------


def test_record_from_a_prompt_file_hashes_what_is_on_disk(conn, prompt_file):
    provenance.record_judgment_run(
        conn, run_id="r1", theory_id="t1", theory_version=1,
        stage="analysis", model="claude-opus-5", prompt_path=str(prompt_file),
        now=TS,
    )
    row = provenance.list_judgment_runs(conn, theory_id="t1")[0]
    assert row["model"] == "claude-opus-5"
    assert row["prompt_sha256"] == provenance.read_prompt(prompt_file)[1]
    assert row["prompt_path"] == str(prompt_file)
    # The file is the record; the text is not duplicated into the row.
    assert row["prompt_text"] is None


def test_record_accepts_inline_prompt_text(conn):
    provenance.record_judgment_run(
        conn, run_id="r1", theory_id="t1", theory_version=1, stage="gate",
        model="haiku", prompt_text="does this fit the thesis?", now=TS,
    )
    row = provenance.list_judgment_runs(conn, theory_id="t1")[0]
    assert row["prompt_text"] == "does this fit the thesis?"
    assert row["prompt_sha256"] == provenance.prompt_sha(
        "does this fit the thesis?")


def test_record_requires_a_prompt(conn):
    with pytest.raises(ValueError):
        provenance.record_judgment_run(
            conn, run_id="r1", theory_id="t1", theory_version=1,
            stage="analysis", model="opus", now=TS,
        )


def test_record_requires_a_model(conn):
    with pytest.raises(ValueError):
        provenance.record_judgment_run(
            conn, run_id="r1", theory_id="t1", theory_version=1,
            stage="analysis", model="  ", prompt_text="x", now=TS,
        )


def test_record_rejects_an_unknown_stage(conn):
    with pytest.raises(ValueError):
        provenance.record_judgment_run(
            conn, run_id="r1", theory_id="t1", theory_version=1,
            stage="vibes", model="opus", prompt_text="x", now=TS,
        )


def test_record_rejects_text_that_contradicts_the_file(conn, prompt_file):
    with pytest.raises(ValueError):
        provenance.record_judgment_run(
            conn, run_id="r1", theory_id="t1", theory_version=1,
            stage="analysis", model="opus", prompt_path=str(prompt_file),
            prompt_text="a completely different prompt", now=TS,
        )


def test_re_recording_the_same_pairing_accumulates_items(conn):
    # A stage batched across several calls is one pairing, not several.
    for _ in range(3):
        provenance.record_judgment_run(
            conn, run_id="r1", theory_id="t1", theory_version=1,
            stage="analysis", model="opus", prompt_text="p", n_items=16,
            now=TS,
        )
    rows = provenance.list_judgment_runs(conn, theory_id="t1")
    assert len(rows) == 1
    assert rows[0]["n_items"] == 48


def test_a_different_prompt_is_a_different_row(conn):
    for text in ("prompt one", "prompt two"):
        provenance.record_judgment_run(
            conn, run_id="r1", theory_id="t1", theory_version=1,
            stage="analysis", model="opus", prompt_text=text, now=TS,
        )
    assert len(provenance.list_judgment_runs(conn, theory_id="t1")) == 2


# --- the guard ---------------------------------------------------------


def test_mechanical_theory_needs_no_provenance(conn):
    # uses_llm_judgment defaults to 0; a code-only theory has no prompt.
    opp_id, created = _record(conn, run_id="r1")
    assert created


def test_llm_theory_cannot_record_without_provenance(conn):
    theories.set_uses_llm_judgment(conn, "t1", True, now=TS)
    with pytest.raises(ValueError, match="judgment_runs provenance"):
        _record(conn, run_id="r1")


def test_llm_theory_records_once_provenance_exists(conn):
    theories.set_uses_llm_judgment(conn, "t1", True, now=TS)
    provenance.record_judgment_run(
        conn, run_id="r1", theory_id="t1", theory_version=1,
        stage="analysis", model="opus", prompt_text="p", now=TS,
    )
    opp_id, created = _record(conn, run_id="r1")
    assert created


def test_provenance_is_scoped_to_the_run(conn):
    # Provenance for yesterday's run does not license today's.
    theories.set_uses_llm_judgment(conn, "t1", True, now=TS)
    provenance.record_judgment_run(
        conn, run_id="r1", theory_id="t1", theory_version=1,
        stage="analysis", model="opus", prompt_text="p", now=TS,
    )
    with pytest.raises(ValueError, match="judgment_runs provenance"):
        _record(conn, run_id="r2")


def test_provenance_is_scoped_to_the_version(conn):
    # Bumping the version means the procedure changed; re-declare what judged.
    theories.set_uses_llm_judgment(conn, "t1", True, now=TS)
    provenance.record_judgment_run(
        conn, run_id="r1", theory_id="t1", theory_version=1,
        stage="analysis", model="opus", prompt_text="p", now=TS,
    )
    with pytest.raises(ValueError, match="judgment_runs provenance"):
        _record(conn, run_id="r1", theory_version=2)


def test_has_provenance_reports_both_ways(conn):
    assert not provenance.has_provenance(conn, "t1", 1, "r1")
    provenance.record_judgment_run(
        conn, run_id="r1", theory_id="t1", theory_version=1,
        stage="gate", model="haiku", prompt_text="p", now=TS,
    )
    assert provenance.has_provenance(conn, "t1", 1, "r1")


def test_set_uses_llm_judgment_rejects_unknown_theory(conn):
    with pytest.raises(KeyError):
        theories.set_uses_llm_judgment(conn, "nope", True)


def test_uses_llm_judgment_defaults_off(conn):
    assert theories.get(conn, "t1")["uses_llm_judgment"] == 0
