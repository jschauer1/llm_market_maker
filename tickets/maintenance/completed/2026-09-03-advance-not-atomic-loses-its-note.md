---
title: tickets.advance renames first and reads second, so a transient lock moves a ticket with no note
lane: maintenance
created: 2026-09-03
created_by: fleet-w3-g4
author_lane: study
author_focus: 2026-08-30-parlay-markup
author_context: Hit for real while advancing parlay-markup from investigation/ to answer/; the move landed, the note did not, and I had to append it by hand in advance()'s own format.
status: done
closed: 2026-09-04
resolution: Made advance and close recoverable under stable per-ticket OS locks, atomic note writes and no-replace publication. Exact receipts support retries after write, move and unlink failures; threaded contention preserves the successful caller explanation. Independent review and fault regressions pass; no unrelated destination is replaced.
---
WHAT HAPPENED, ONCE, FOR REAL. `python -m tools.cli tickets advance tickets/study/investigation/2026-08-30-parlay-markup --to answer --note '...'` raised OSError from pathlib's io.open and exited non-zero. The directory had ALREADY been renamed into answer/. So the ticket moved and its note -- the record of WHY it moved -- was lost. Re-running was not an option either: advance() refuses when the target already exists, so the operation is not idempotent. I appended the note by hand in advance()'s exact format.

THE CODE, tools/tickets.py in advance():

    item.rename(moved)                                    # <- commits
    body_file = moved / STUDY_FILE if is_study else moved
    raw = body_file.read_text(encoding='utf-8').rstrip()  # <- can throw
    ...
    body_file.write_text(f'{raw}...{note}', encoding='utf-8')

The state change happens first and the thing that justifies it happens second, with two failure points (a read and a write) after the point of no return.

WHY IT IS WORTH FIXING RATHER THAN SHRUGGING AT. This tree lives inside OneDrive, which takes transient handles on files it is syncing -- the same reason tools/atomic_write.py exists. A ticket that moved with no note is not a loud failure: the directory says 'answer', nothing says why, and the ticket pipeline's whole argument is that a state is a claim somebody made for a reason. It is also the SECOND time this class has been found here; atomic_write.py fixed it for collectors and the ticket mover was never looked at.

THE FIX, which is small: read the body BEFORE the rename, and write the appended body to the OLD path (or a temp) before renaming -- i.e. make the rename the LAST step, so a failure leaves the ticket where it was with its note unwritten, which is a recoverable state a re-run fixes. Failing that, wrap everything after the rename in try/except and rename back on failure. Prefer the first: it needs no unwind path.

WORTH CHECKING FOR THE SAME SHAPE: tickets.close() also mutates then writes, and purge/advance share helpers. This ticket is about the class, not only the one call.
