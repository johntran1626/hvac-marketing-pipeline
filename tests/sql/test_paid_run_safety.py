"""Disposable SQLite SQL transaction safety contracts; NOT Postgres equivalence."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

DDL = '''
CREATE TABLE run_state (source TEXT PRIMARY KEY, generation INTEGER NOT NULL,
 status TEXT NOT NULL, watermark TEXT);
CREATE TABLE fact (source TEXT NOT NULL, day TEXT NOT NULL, amount TEXT NOT NULL,
 PRIMARY KEY(source,day));
CREATE TABLE staged (source TEXT NOT NULL, generation INTEGER NOT NULL,
 snapshot_id TEXT NOT NULL, day TEXT NOT NULL, amount TEXT NOT NULL,
 PRIMARY KEY(source,generation,day));
'''


def start(conn, source):
    with conn:
        conn.execute('INSERT INTO run_state(source,generation,status) VALUES(?,1,\'running\') '
                     'ON CONFLICT(source) DO UPDATE SET generation=generation+1,status=\'running\'', (source,))
    return conn.execute('SELECT generation FROM run_state WHERE source=?',(source,)).fetchone()[0]


def commit_window(conn, source, generation, snapshot_id, rows, fail=False):
    # This simulates required SQL transaction fencing; it is NOT the proposed production RPC.
    conn.execute('BEGIN IMMEDIATE')
    try:
        state=conn.execute('SELECT generation,status FROM run_state WHERE source=?',(source,)).fetchone()
        if state != (generation,'running'):
            raise ValueError('stale source generation')
        if not snapshot_id:
            raise ValueError('immutable snapshot ID required')
        if len({day for day,_ in rows}) != len(rows):
            raise ValueError('duplicate source/day')
        conn.execute('DELETE FROM fact WHERE source=?',(source,))
        for day, amount in rows:
            conn.execute('INSERT INTO fact VALUES(?,?,?)',(source,day,amount))
        if fail:
            raise RuntimeError('injected partial failure')
        conn.execute('UPDATE run_state SET status=\'complete\', watermark=? WHERE source=?',
                     (max((day for day,_ in rows), default=None),source))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


class PaidSqlSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=str(Path(self.tmp.name)/'isolated.db')
        self.db=sqlite3.connect(self.path, isolation_level=None, timeout=0.1)
        self.db.executescript(DDL)
        self.db.execute("INSERT INTO fact VALUES('google_ads','2026-09-01','12')")

    def tearDown(self):
        self.db.close();self.tmp.cleanup()

    def rows(self):
        return self.db.execute('SELECT * FROM fact ORDER BY source,day').fetchall()

    def test_stale_generation_cannot_overwrite_new_run(self):
        old=start(self.db,'google_ads'); new=start(self.db,'google_ads')
        before=self.rows()
        with self.assertRaisesRegex(ValueError,'stale'):
            commit_window(self.db,'google_ads',old,'snap-old',[('2026-09-01','99')])
        self.assertEqual(self.rows(),before)
        commit_window(self.db,'google_ads',new,'snap-new',[('2026-09-01','4')])
        self.assertEqual(self.rows(),[('google_ads','2026-09-01','4')])

    def test_partial_failure_rolls_back_delete_and_insert(self):
        gen=start(self.db,'google_ads');before=self.rows()
        with self.assertRaisesRegex(RuntimeError,'partial'):
            commit_window(self.db,'google_ads',gen,'snap',[('2026-09-02','3')],fail=True)
        self.assertEqual(self.rows(),before)
        self.assertEqual(self.db.execute("SELECT status FROM run_state WHERE source='google_ads'").fetchone()[0],'running')

    def test_cancelled_generation_rejected(self):
        gen=start(self.db,'google_ads')
        self.db.execute("UPDATE run_state SET status='cancelled' WHERE source='google_ads'")
        before=self.rows()
        with self.assertRaisesRegex(ValueError,'stale'):
            commit_window(self.db,'google_ads',gen,'snap',[('2026-09-02','3')])
        self.assertEqual(self.rows(),before)

    def test_missing_snapshot_identity_and_duplicate_day_fail_closed(self):
        gen=start(self.db,'google_ads');before=self.rows()
        for sid,rows in [('', [('2026-09-01','2')]),('snap',[('2026-09-01','2'),('2026-09-01','3')])]:
            with self.assertRaises(ValueError):commit_window(self.db,'google_ads',gen,sid,rows)
            self.assertEqual(self.rows(),before)

    def test_source_scope_preserves_other_sources(self):
        self.db.execute("INSERT INTO fact VALUES('crm','2026-09-01','10')")
        gen=start(self.db,'google_ads')
        commit_window(self.db,'google_ads',gen,'snap',[('2026-09-02','2')])
        self.assertIn(('crm','2026-09-01','10'),self.rows())

    def test_concurrent_writer_blocked_during_active_transaction(self):
        first=sqlite3.connect(self.path, isolation_level=None,timeout=0.05)
        second=sqlite3.connect(self.path,isolation_level=None,timeout=0.05)
        try:
            first.execute('BEGIN IMMEDIATE')
            first.execute("UPDATE fact SET amount='8' WHERE source='google_ads'")
            with self.assertRaises(sqlite3.OperationalError):
                second.execute("UPDATE fact SET amount='100' WHERE source='google_ads'")
            first.rollback()
            self.assertEqual(self.rows(),[('google_ads','2026-09-01','12')])
        finally:
            first.close();second.close()

if __name__=='__main__':unittest.main()
