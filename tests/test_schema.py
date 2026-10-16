from pathlib import Path
import sqlite3


def test_schema_and_demo_seed():
    conn = sqlite3.connect(':memory:')
    conn.executescript(Path('db/migrations/0001_init.sql').read_text())
    conn.executescript(Path('db/seed/demo.sql').read_text())
    assert conn.execute('SELECT COUNT(*) FROM observations').fetchone()[0] == 6
    assert conn.execute("SELECT value FROM observations WHERE series_id='gold_eur_oz' AND period='2000-01'").fetchone()[0] == 300


def test_unique_observation_key():
    conn = sqlite3.connect(':memory:')
    conn.executescript(Path('db/migrations/0001_init.sql').read_text())
    conn.execute("INSERT INTO observations(series_id,period,value) VALUES ('gold_eur_oz','2000-01',300)")
    try:
        conn.execute("INSERT INTO observations(series_id,period,value) VALUES ('gold_eur_oz','2000-01',400)")
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError('Duplicate observation accepted')
