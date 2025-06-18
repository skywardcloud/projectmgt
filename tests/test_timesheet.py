import os
import sqlite3
import io
import tempfile
from contextlib import redirect_stdout
from types import SimpleNamespace
import unittest

import timesheet

class TimesheetTests(unittest.TestCase):
    def setUp(self):
        # Use a temporary database file for each test
        self.db_fd, self.db_path = None, None
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.orig_db = timesheet.DB_FILE
        timesheet.DB_FILE = self.db_path
        timesheet.init_db()

    def tearDown(self):
        if self.db_fd:
            os.close(self.db_fd)
        if self.db_path and os.path.exists(self.db_path):
            os.remove(self.db_path)
        timesheet.DB_FILE = self.orig_db

    def test_init_db_creates_tables(self):
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cur.fetchall()}
        expected = {
            'employees',
            'projects',
            'timesheets',
            'project_master',
            'project_assignments',
        }
        self.assertTrue(expected.issubset(tables))

    def test_init_db_adds_missing_remarks_column(self):
        """Older databases may not have the remarks column."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("DROP TABLE timesheets")
            cur.execute(
                '''CREATE TABLE timesheets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_id INTEGER NOT NULL,
                    project_id INTEGER NOT NULL,
                    entry_date TEXT NOT NULL,
                    hours REAL NOT NULL,
                    FOREIGN KEY (employee_id) REFERENCES employees(id),
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                )'''
            )
            conn.commit()

        timesheet.init_db()

        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(timesheets)")
            cols = {row[1] for row in cur.fetchall()}
        self.assertIn('remarks', cols)

    def test_log_time_records_entry(self):
        args = SimpleNamespace(employee='Alice', project='Proj', hours=2.0, date='2023-01-01')
        buf = io.StringIO()
        with redirect_stdout(buf):
            timesheet.log_time(args)
        output = buf.getvalue()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM timesheets")
            count = cur.fetchone()[0]
        self.assertEqual(count, 1)
        self.assertIn('Time entry recorded', output)

    def test_report_outputs_entries(self):
        # Add two entries
        args = SimpleNamespace(employee='Alice', project='Proj', hours=2.0, date='2023-01-01')
        with redirect_stdout(io.StringIO()):
            timesheet.log_time(args)
        args = SimpleNamespace(employee='Bob', project='Proj', hours=1.5, date='2023-01-02')
        with redirect_stdout(io.StringIO()):
            timesheet.log_time(args)

        rep_args = SimpleNamespace(project='Proj', start=None, end=None)
        buf = io.StringIO()
        with redirect_stdout(buf):
            timesheet.report(rep_args)
        output = buf.getvalue()
        self.assertIn('Total hours for Proj: 3.5', output)
        self.assertIn('Alice', output)
        self.assertIn('Bob', output)

    def test_summary_project_totals(self):
        args = SimpleNamespace(employee='Alice', project='ProjA', hours=2.0, date='2023-01-01')
        with redirect_stdout(io.StringIO()):
            timesheet.log_time(args)
        args = SimpleNamespace(employee='Bob', project='ProjA', hours=1.5, date='2023-01-02')
        with redirect_stdout(io.StringIO()):
            timesheet.log_time(args)

        sum_args = SimpleNamespace(by='project', period=None, start=None, end=None)
        buf = io.StringIO()
        with redirect_stdout(buf):
            timesheet.summary(sum_args)
        output = buf.getvalue()
        self.assertIn('ProjA', output)
        self.assertIn('3.5h', output)

if __name__ == '__main__':
    unittest.main()

