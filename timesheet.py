import sqlite3
import argparse
import sys
import os
from datetime import date

DB_FILE = os.environ.get('TIMESHEET_DB', 'timesheet.db')


def connect_db():
    """Return a connection to the SQLite database or exit on failure."""
    try:
        return sqlite3.connect(DB_FILE)
    except sqlite3.Error as e:
        print(f"Could not open database '{DB_FILE}': {e}")
        sys.exit(1)


def init_db():
    try:
        with connect_db() as conn:
            cur = conn.cursor()
            cur.execute('''CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )''')
            cur.execute('''CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )''')
            cur.execute('''CREATE TABLE IF NOT EXISTS timesheets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                project_id INTEGER NOT NULL,
                entry_date TEXT NOT NULL,
                hours REAL NOT NULL,
                FOREIGN KEY (employee_id) REFERENCES employees(id),
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )''')
            conn.commit()
    except sqlite3.Error as e:
        print(f"Database initialization failed: {e}")
        sys.exit(1)


def get_or_create(cursor, table, name):
    cursor.execute(f"SELECT id FROM {table} WHERE name = ?", (name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute(f"INSERT INTO {table}(name) VALUES(?)", (name,))
    return cursor.lastrowid


def add_employee(args):
    with connect_db() as conn:
        cur = conn.cursor()
        try:
            get_or_create(cur, 'employees', args.name)
            conn.commit()
            print(f"Employee '{args.name}' added")
        except sqlite3.IntegrityError:
            print(f"Employee '{args.name}' already exists")
        except sqlite3.Error as e:
            print(f"Failed to add employee: {e}")
            sys.exit(1)


def add_project(args):
    with connect_db() as conn:
        cur = conn.cursor()
        try:
            get_or_create(cur, 'projects', args.name)
            conn.commit()
            print(f"Project '{args.name}' added")
        except sqlite3.IntegrityError:
            print(f"Project '{args.name}' already exists")
        except sqlite3.Error as e:
            print(f"Failed to add project: {e}")
            sys.exit(1)


def log_time(args):
    with connect_db() as conn:
        cur = conn.cursor()
        try:
            emp_id = get_or_create(cur, 'employees', args.employee)
            proj_id = get_or_create(cur, 'projects', args.project)
            cur.execute(
                'INSERT INTO timesheets(employee_id, project_id, entry_date, hours) VALUES (?, ?, ?, ?)',
                (emp_id, proj_id, args.date, args.hours)
            )
            conn.commit()
            print('Time entry recorded')
        except sqlite3.Error as e:
            print(f"Failed to log time: {e}")
            sys.exit(1)


def report(args):
    with connect_db() as conn:
        cur = conn.cursor()
        params = [args.project]
        if args.summary == 'employee':
            query = '''SELECT e.name, SUM(t.hours)
                       FROM timesheets t
                       JOIN employees e ON e.id = t.employee_id
                       JOIN projects p ON p.id = t.project_id
                       WHERE p.name = ?'''
        elif args.summary == 'date':
            query = '''SELECT t.entry_date, SUM(t.hours)
                       FROM timesheets t
                       JOIN employees e ON e.id = t.employee_id
                       JOIN projects p ON p.id = t.project_id
                       WHERE p.name = ?'''
        else:

        try:

            query = '''SELECT p.name, e.name, t.entry_date, t.hours
                       FROM timesheets t
                       JOIN employees e ON e.id = t.employee_id
                       JOIN projects p ON p.id = t.project_id
                       WHERE p.name = ?'''
        if args.start:
            query += ' AND t.entry_date >= ?'
            params.append(args.start)
        if args.end:
            query += ' AND t.entry_date <= ?'
            params.append(args.end)
        if args.summary == 'employee':
            query += ' GROUP BY e.name ORDER BY e.name'
        elif args.summary == 'date':
            query += ' GROUP BY t.entry_date ORDER BY t.entry_date'
        else:
            query += ' ORDER BY t.entry_date, e.name'
        cur.execute(query, params)
        rows = cur.fetchall()
        if not rows:
            print('No entries found')
            return
        total = 0
        if args.summary == 'employee':
            for employee, hours in rows:
                print(f"{employee} | {hours}h")
                total += hours
        elif args.summary == 'date':
            for entry_date, hours in rows:
                print(f"{entry_date} | {hours}h")
                total += hours
        else:
            for project, employee, entry_date, hours in rows:
                print(f"{entry_date} | {employee} | {hours}h")
                total += hours
        print(f"Total hours for {args.project}: {total}")
            params = [args.project]
            if args.start:
                query += ' AND t.entry_date >= ?'
                params.append(args.start)
            if args.end:
                query += ' AND t.entry_date <= ?'
                params.append(args.end)
            query += ' ORDER BY t.entry_date, e.name'
            cur.execute(query, params)
            rows = cur.fetchall()
            if not rows:
                print('No entries found')
                return
            total = 0
            for project, employee, entry_date, hours in rows:
                print(f"{entry_date} | {employee} | {hours}h")
                total += hours
            print(f"Total hours for {args.project}: {total}")
        except sqlite3.Error as e:
            print(f"Failed to run report: {e}")
            sys.exit(1)


def _find_entry(cur, entry_id=None, employee=None, project=None, entry_date=None):
    """Return the id of the entry matching the given criteria."""
    if entry_id:
        cur.execute('SELECT id FROM timesheets WHERE id = ?', (entry_id,))
        row = cur.fetchone()
        return row[0] if row else None
    if employee and project and entry_date:
        cur.execute(
            '''SELECT t.id FROM timesheets t
               JOIN employees e ON e.id = t.employee_id
               JOIN projects p ON p.id = t.project_id
               WHERE e.name = ? AND p.name = ? AND t.entry_date = ?''',
            (employee, project, entry_date),
        )
        row = cur.fetchone()
        return row[0] if row else None
    return None


def update_time(args):
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        entry_id = _find_entry(
            cur, args.id, args.employee, args.project, args.entry_date
        )
        if not entry_id:
            print('Entry not found')
            return
        updates = []
        params = []
        if args.new_hours is not None:
            updates.append('hours = ?')
            params.append(args.new_hours)
        if args.new_date:
            updates.append('entry_date = ?')
            params.append(args.new_date)
        if not updates:
            print('No updates specified')
            return
        params.append(entry_id)
        cur.execute(
            f'UPDATE timesheets SET {", ".join(updates)} WHERE id = ?', params
        )
        conn.commit()
        print(f'Entry {entry_id} updated')


def delete_time(args):
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        entry_id = _find_entry(
            cur, args.id, args.employee, args.project, args.entry_date
        )
        if not entry_id:
            print('Entry not found')
            return
        cur.execute('DELETE FROM timesheets WHERE id = ?', (entry_id,))
        conn.commit()
        print(f'Entry {entry_id} deleted')


def parse_args():
    parser = argparse.ArgumentParser(description='Simple timesheet tool')
    parser.add_argument('--db', default=DB_FILE,
                        help='Path to the SQLite database file')
    sub = parser.add_subparsers(dest='cmd')

    sub_add_emp = sub.add_parser('add-employee', help='Add a new employee')
    sub_add_emp.add_argument('name')
    sub_add_emp.set_defaults(func=add_employee)

    sub_add_proj = sub.add_parser('add-project', help='Add a new project')
    sub_add_proj.add_argument('name')
    sub_add_proj.set_defaults(func=add_project)

    sub_log = sub.add_parser('log', help='Log hours for a project')
    sub_log.add_argument('employee')
    sub_log.add_argument('project')
    sub_log.add_argument('hours', type=float)
    sub_log.add_argument('--date', default=date.today().isoformat())
    sub_log.set_defaults(func=log_time)

    sub_rep = sub.add_parser('report', help='Show hours for a project')
    sub_rep.add_argument('project')
    sub_rep.add_argument('--start')
    sub_rep.add_argument('--end')
    sub_rep.add_argument('--summary', choices=['employee', 'date'],
                         help='Show totals grouped by employee or date')
    sub_rep.set_defaults(func=report)

    sub_upd = sub.add_parser('update', help='Update a time entry')
    sub_upd.add_argument('--id', type=int, help='Entry ID')
    sub_upd.add_argument('--employee', help='Employee name')
    sub_upd.add_argument('--project', help='Project name')
    sub_upd.add_argument('--entry-date', help='Original entry date')
    sub_upd.add_argument('--new-hours', type=float, help='Updated hours')
    sub_upd.add_argument('--new-date', help='Updated date')
    sub_upd.set_defaults(func=update_time)

    sub_del = sub.add_parser('delete', help='Delete a time entry')
    sub_del.add_argument('--id', type=int, help='Entry ID')
    sub_del.add_argument('--employee', help='Employee name')
    sub_del.add_argument('--project', help='Project name')
    sub_del.add_argument('--entry-date', help='Entry date')
    sub_del.set_defaults(func=delete_time)

    return parser.parse_args()


def main():
    args = parse_args()
    global DB_FILE
    DB_FILE = args.db
    init_db()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        print('No command given. Use -h for help.')


if __name__ == '__main__':
    main()
