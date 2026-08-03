"""Clean up all smoke test entries from pool. One-time use."""
import sys
sys.path.insert(0, ".")
from pa_cli.sample_pool import get_connection

conn = get_connection(readonly=False)
cur = conn.execute("SELECT qid FROM pool_entries WHERE qid LIKE 'smoketest%' OR qid LIKE 'should-fail%'")
rows = cur.fetchall()
print(f"Found {len(rows)} smoke test entries to clean")
for (qid,) in rows:
    conn.execute("DELETE FROM relevance_labels WHERE qid = ?", (qid,))
    conn.execute("DELETE FROM pool_entries WHERE qid = ?", (qid,))
    print(f"  cleaned: {qid}")
conn.execute("UPDATE gate_status SET current_n = 0")
conn.commit()
n = conn.execute("SELECT COUNT(*) FROM pool_entries").fetchone()[0]
print(f"Pool now has {n} entries")
conn.close()
