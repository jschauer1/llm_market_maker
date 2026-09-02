"""COUNTS ONLY from the frozen corpus. No win rates, no edges.

Counts decide the inclusion rules and the power floor, which are part of
the bar and must be written before any outcome is computed. This script
deliberately computes no outcome of any kind.
"""
import sqlite3
import sys

DB = sys.argv[1]
conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row

print("obs rows            :", conn.execute("SELECT COUNT(*) FROM obs").fetchone()[0])
print("distinct series     :", conn.execute(
    "SELECT COUNT(DISTINCT series_ticker) FROM obs").fetchone()[0])
print("rows with ask_24h   :", conn.execute(
    "SELECT COUNT(*) FROM obs WHERE ask_24h IS NOT NULL").fetchone()[0])
print("rows with BOTH      :", conn.execute(
    "SELECT COUNT(*) FROM obs WHERE ask_24h IS NOT NULL AND ask IS NOT NULL"
).fetchone()[0])
print("early_settled=1     :", conn.execute(
    "SELECT COUNT(*) FROM obs WHERE early_settled=1").fetchone()[0])
print("distinct close days :", conn.execute(
    "SELECT COUNT(DISTINCT substr(close_time,1,10)) FROM obs").fetchone()[0])
print()
print("series with >=40 paired rows:")
rows = conn.execute(
    "SELECT series_ticker, COUNT(*) n, "
    "COUNT(DISTINCT substr(close_time,1,10)) nd "
    "FROM obs WHERE ask_24h IS NOT NULL AND ask IS NOT NULL "
    "GROUP BY series_ticker HAVING n >= 40 ORDER BY n DESC").fetchall()
print("  count:", len(rows))
for r in rows[:12]:
    print(f"   {r['series_ticker']:28} n={r['n']:4d} days={r['nd']:3d}")
print()
print("paired rows by offset bucket (hours before close, the MAIN point):")
for r in conn.execute(
        "SELECT CASE WHEN offset_h < 6 THEN '<6h' "
        "WHEN offset_h < 24 THEN '6-24h' "
        "WHEN offset_h < 72 THEN '1-3d' "
        "WHEN offset_h < 168 THEN '3-7d' ELSE '7d+' END b, COUNT(*) n "
        "FROM obs WHERE ask_24h IS NOT NULL GROUP BY 1 ORDER BY 2 DESC"):
    print(f"   {r['b']:6} {r['n']}")
