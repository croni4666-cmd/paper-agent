"""Real CLI e2e: pa export-screening with bib + judge db."""
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, '.')

from pa_cli.export_screening import run_export_screening

tmpdir = Path(tempfile.mkdtemp())
bib = tmpdir / 'demo.bib'
bib.write_text("""@article{key1, title = {AI Tutoring}, author = {Smith, J.}, year = {2023}}
@article{key2, title = {ChatGPT in HE}, author = {Jones, A.}, year = {2024}}
@article{key3, title = {Acemoglu Automation}, author = {Acemoglu, D.}, year = {2022}}
""", encoding='utf-8')

# Create a judge db
db = tmpdir / 'judges.sqlite'
conn = sqlite3.connect(str(db))
conn.executescript("""
    CREATE TABLE judgements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query TEXT NOT NULL, paper_key TEXT NOT NULL, paper_title TEXT,
        relevance INTEGER NOT NULL, reason TEXT, source TEXT DEFAULT 'manual',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(query, paper_key)
    );
""")
conn.execute("INSERT INTO judgements (query, paper_key, relevance, reason) VALUES (?, ?, ?, ?)",
             ("AI literacy", "key1", 2, "Direct hit"))
conn.execute("INSERT INTO judgements (query, paper_key, relevance, reason) VALUES (?, ?, ?, ?)",
             ("AI literacy", "key2", 1, "Topic adjacent"))
conn.commit()
conn.close()

# Run export-screening via run_export_screening function
out = tmpdir / 'screening.csv'
result = run_export_screening(
    bib_path=bib, out_path=out, judges_db=db, query='AI literacy'
)
print(f"Result: {result}")

# Read CSV
print(f"\n--- {out.name} ---")
import csv
with open(out, encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for i, row in enumerate(reader):
        print(f"row {i+1}: paper_key={row['paper_key']:20s} query={row['query']:15s} "
              f"relevance={row['relevance']:3s} title={row['title'][:30]}")
