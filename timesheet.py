import sqlite3
import argparse
import os
import sys
from datetime import date, datetime

# Default database file path
DB_FILE = os.environ.get('TIMESHEET_DB', 'timesheet.db')


def connect_db():
    """Return a connection to the SQLite database or exit on failure."""
    try:
        return sqlite3.connect(DB_FILE)
    except sqlite3.Error as e:
        print(f"Could not open database '{DB_FILE}': {e}")
        sys.exit(1)


def init_db(db_file=None):
    """Create required tables in the database and upgrade schema if needed."""
    global DB_FILE
    if db_file:
        DB_FILE = db_file
    try:
        with connect_db() as conn:
            cur = conn.cursor()
            cur.execute(
                '''CREATE TABLE IF NOT EXISTS employees (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                )'''
            )
            cur.execute(
                '''CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                )'''
            )
            cur.execute(
                '''CREATE TABLE IF NOT EXISTS project_master (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT UNIQUE,
                    project_name TEXT UNIQUE NOT NULL,
                    client_name TEXT,
                    project_code TEXT UNIQUE NOT NULL,
                    start_date TEXT,
                    end_date TEXT,
                    description TEXT,
                    manager_id INTEGER,
                    estimated_hours REAL,
                    actual_hours REAL DEFAULT 0,
                    status TEXT,
                    billing_type TEXT,
                    created_by INTEGER,
                    created_date TEXT,
                    modified_by INTEGER,
                    modified_date TEXT,
                    FOREIGN KEY (manager_id) REFERENCES users(id),
                    FOREIGN KEY (created_by) REFERENCES users(id),
                    FOREIGN KEY (modified_by) REFERENCES users(id)
                )'''
            )
            cur.execute(
                '''CREATE TABLE IF NOT EXISTS project_assignments (
                    project_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    PRIMARY KEY (project_id, user_id),
                    FOREIGN KEY (project_id) REFERENCES project_master(id),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )'''
            )
            cur.execute(
                '''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT UNIQUE,
                    full_name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    phone TEXT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    department TEXT NOT NULL,
                    designation TEXT,
                    role TEXT NOT NULL,
                    date_of_joining TEXT,
                    status TEXT NOT NULL,
                    reporting_manager INTEGER,
                    FOREIGN KEY (reporting_manager) REFERENCES users(id)
                )'''
            )
            cur.execute(
                '''CREATE TABLE IF NOT EXISTS timesheets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_id INTEGER NOT NULL,
                    project_id INTEGER NOT NULL,
                    entry_date TEXT NOT NULL,
                    hours REAL NOT NULL,
                    remarks TEXT,
                    FOREIGN KEY (employee_id) REFERENCES employees(id),
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                )'''
            )
            # Ensure the remarks column exists for databases created
            # with older versions of the schema.
            cur.execute("PRAGMA table_info(timesheets)")
            cols = [row[1] for row in cur.fetchall()]
            if 'remarks' not in cols:
                cur.execute('ALTER TABLE timesheets ADD COLUMN remarks TEXT')
            conn.commit()
    except sqlite3.Error as e:
        print(f"Database initialization failed: {e}")
        sys.exit(1)


def get_or_create(cursor, table, name):
    """Return the id for the given name, inserting a new row if needed.

    The function returns a tuple ``(id, created)`` where ``created`` is
    ``True`` when a new row was inserted and ``False`` when an existing
    row was found.  This allows callers to distinguish between the two
    cases without relying on catching an ``IntegrityError``.
    """

    cursor.execute(f"SELECT id FROM {table} WHERE name = ?", (name,))
    row = cursor.fetchone()
    if row:
        return row[0], False
    cursor.execute(f"INSERT INTO {table}(name) VALUES(?)", (name,))
    return cursor.lastrowid, True


def add_employee(args):
    with connect_db() as conn:
        cur = conn.cursor()
        try:
            _, created = get_or_create(cur, 'employees', args.name)
            if created:
                conn.commit()
                print(f"Employee '{args.name}' added")
            else:
                print(f"Employee '{args.name}' already exists")
        except sqlite3.Error as e:
            print(f"Failed to add employee: {e}")
            sys.exit(1)


def add_project(args):
    with connect_db() as conn:
        cur = conn.cursor()
        try:
            _, created = get_or_create(cur, 'projects', args.name)
            if created:
                conn.commit()
                print(f"Project '{args.name}' added")
            else:
                print(f"Project '{args.name}' already exists")
        except sqlite3.Error as e:
            print(f"Failed to add project: {e}")
            sys.exit(1)


def log_time(args):
    # Validate hours value
    if args.hours <= 0 or args.hours > 24:
        print('Hours must be greater than 0 and no more than 24.')
        return
    if args.hours * 2 != int(args.hours * 2):
        print('Hours must be in 0.5 hour increments.')
        return

    # Validate date format and ensure it's not in the future
    try:
        entry_date = datetime.strptime(args.date, '%Y-%m-%d').date()
    except ValueError:
        print('Date must be in YYYY-MM-DD format.')
        return
    if entry_date > date.today():
        print('Date cannot be in the future.')
        return

    remarks = getattr(args, 'remarks', None)

    with connect_db() as conn:
        cur = conn.cursor()
        emp_id, _ = get_or_create(cur, 'employees', args.employee)
        proj_id, _ = get_or_create(cur, 'projects', args.project)
        try:
            cur.execute(
                'INSERT INTO timesheets(employee_id, project_id, entry_date, hours, remarks) '
                'VALUES (?, ?, ?, ?, ?)',
                (emp_id, proj_id, entry_date.isoformat(), args.hours, remarks)
            )
            conn.commit()
            print('Time entry recorded')
        except sqlite3.Error as e:
            print(f"Failed to log time: {e}")
            sys.exit(1)


def report(args):
    with connect_db() as conn:
        cur = conn.cursor()
        summary = getattr(args, 'summary', None)
        params = [args.project]
        if summary == 'employee':
            query = '''SELECT e.name, SUM(t.hours)
                       FROM timesheets t
                       JOIN employees e ON e.id = t.employee_id
                       JOIN projects p ON p.id = t.project_id
                       WHERE p.name = ?'''
        elif summary == 'date':
            query = '''SELECT t.entry_date, SUM(t.hours)
                       FROM timesheets t
                       JOIN employees e ON e.id = t.employee_id
                       JOIN projects p ON p.id = t.project_id
                       WHERE p.name = ?'''
        else:
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
        if summary == 'employee':
            query += ' GROUP BY e.name ORDER BY e.name'
        elif summary == 'date':
            query += ' GROUP BY t.entry_date ORDER BY t.entry_date'
        else:
            query += ' ORDER BY t.entry_date, e.name'
        try:
            cur.execute(query, params)
            rows = cur.fetchall()
        except sqlite3.Error as e:
            print(f"Failed to run report: {e}")
            sys.exit(1)
        if not rows:
            print('No entries found')
            return
        total = 0
        if summary == 'employee':
            for employee, hours in rows:
                print(f"{employee} | {hours}h")
                total += hours
        elif summary == 'date':
            for entry_date, hours in rows:
                print(f"{entry_date} | {hours}h")
                total += hours
        else:
            for project, employee, entry_date, hours in rows:
                print(f"{entry_date} | {employee} | {hours}h")
                total += hours
        print(f"Total hours for {args.project}: {total}")


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
    with connect_db() as conn:
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
    with connect_db() as conn:
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


def summary(args):
    """Print aggregated hours grouped by project or employee."""
    with connect_db() as conn:
        cur = conn.cursor()

        group_fields = []
        selects = []

        if args.by == 'project':
            group_fields.append('p.name')
            selects.append('p.name')
        else:
            group_fields.append('e.name')
            selects.append('e.name')

        if args.period == 'daily':
            group_fields.append('t.entry_date')
            selects.append('t.entry_date')
        elif args.period == 'weekly':
            group_fields.append("strftime('%Y-%W', t.entry_date)")
            selects.append("strftime('%Y-%W', t.entry_date)")
        elif args.period == 'monthly':
            group_fields.append("strftime('%Y-%m', t.entry_date)")
            selects.append("strftime('%Y-%m', t.entry_date)")

        query = f"SELECT {', '.join(selects)}, SUM(t.hours) "
        query += "FROM timesheets t JOIN employees e ON e.id = t.employee_id "
        query += "JOIN projects p ON p.id = t.project_id WHERE 1=1"

        params = []
        if args.start:
            query += ' AND t.entry_date >= ?'
            params.append(args.start)
        if args.end:
            query += ' AND t.entry_date <= ?'
            params.append(args.end)

        if group_fields:
            query += ' GROUP BY ' + ', '.join(group_fields)
            query += ' ORDER BY ' + ', '.join(group_fields)

        try:
            cur.execute(query, params)
            rows = cur.fetchall()
        except sqlite3.Error as e:
            print(f"Failed to run summary: {e}")
            sys.exit(1)

        if not rows:
            print('No entries found')
            return

        for row in rows:
            *labels, hours = row
            print(' | '.join(labels) + f' | {hours}h')


def employee_work_distribution(employee, start=None, end=None):
    """Return list of (project, hours) tuples for the given employee."""
    with connect_db() as conn:
        cur = conn.cursor()
        query = (
            'SELECT p.name, SUM(t.hours) FROM timesheets t '
            'JOIN employees e ON e.id = t.employee_id '
            'JOIN projects p ON p.id = t.project_id '
            'WHERE e.name = ?'
        )
        params = [employee]
        if start:
            query += ' AND t.entry_date >= ?'
            params.append(start)
        if end:
            query += ' AND t.entry_date <= ?'
            params.append(end)
        query += ' GROUP BY p.name ORDER BY p.name'
        cur.execute(query, params)
        return cur.fetchall()


def top_employees(project=None, start=None, end=None, limit=10):
    """Return top employees by hours for the given project."""
    with connect_db() as conn:
        cur = conn.cursor()
        query = (
            'SELECT e.name, SUM(t.hours) as total FROM timesheets t '
            'JOIN employees e ON e.id = t.employee_id '
            'JOIN projects p ON p.id = t.project_id WHERE 1=1'
        )
        params = []
        if project:
            query += ' AND p.name = ?'
            params.append(project)
        if start:
            query += ' AND t.entry_date >= ?'
            params.append(start)
        if end:
            query += ' AND t.entry_date <= ?'
            params.append(end)
        query += ' GROUP BY e.name ORDER BY total DESC LIMIT ?'
        params.append(limit)
        cur.execute(query, params)
        return cur.fetchall()


def overworked_employees(start=None, end=None, threshold=9, days=3):
    """Return list of employees with at least ``days`` entries over threshold."""
    with connect_db() as conn:
        cur = conn.cursor()
        query = (
            'SELECT e.name, t.entry_date, SUM(t.hours) FROM timesheets t '
            'JOIN employees e ON e.id = t.employee_id WHERE 1=1'
        )
        params = []
        if start:
            query += ' AND t.entry_date >= ?'
            params.append(start)
        if end:
            query += ' AND t.entry_date <= ?'
            params.append(end)
        query += ' GROUP BY e.name, t.entry_date HAVING SUM(t.hours) > ?'
        params.append(threshold)
        cur.execute(query, params)
        rows = cur.fetchall()

    counts = {}
    for name, _date, _hours in rows:
        counts[name] = counts.get(name, 0) + 1
    return [name for name, cnt in counts.items() if cnt >= days]


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
    sub_log.add_argument('--remarks', help='Optional remarks')
    sub_log.set_defaults(func=log_time)

    sub_rep = sub.add_parser('report', help='Show hours for a project')
    sub_rep.add_argument('project')
    sub_rep.add_argument('--start')
    sub_rep.add_argument('--end')
    sub_rep.add_argument('--summary', choices=['employee', 'date'],
                         help='Show totals grouped by employee or date')
    sub_rep.set_defaults(func=report)

    sub_sum = sub.add_parser('summary', help='Show aggregated hours')
    sub_sum.add_argument('--by', choices=['project', 'employee'], default='project',
                         help='Group totals by project or employee')
    sub_sum.add_argument('--period', choices=['daily', 'weekly', 'monthly'],
                         help='Break down results by time period')
    sub_sum.add_argument('--start')
    sub_sum.add_argument('--end')
    sub_sum.set_defaults(func=summary)

    sub_dist = sub.add_parser('emp-distribution', help='Employee work distribution')
    sub_dist.add_argument('employee')
    sub_dist.add_argument('--start')
    sub_dist.add_argument('--end')
    sub_dist.set_defaults(func=lambda a: print('\n'.join(f"{p} | {h}h" for p, h in employee_work_distribution(a.employee, a.start, a.end))))

    sub_top = sub.add_parser('top-employees', help='Top employees by hours')
    sub_top.add_argument('--project')
    sub_top.add_argument('--start')
    sub_top.add_argument('--end')
    sub_top.add_argument('--limit', type=int, default=10)
    sub_top.set_defaults(func=lambda a: print('\n'.join(f"{n} | {h}h" for n, h in top_employees(a.project, a.start, a.end, a.limit))))

    sub_over = sub.add_parser('overworked', help='List employees consistently over threshold hours/day')
    sub_over.add_argument('--start')
    sub_over.add_argument('--end')
    sub_over.add_argument('--threshold', type=float, default=9)
    sub_over.add_argument('--days', type=int, default=3)
    sub_over.set_defaults(func=lambda a: print('\n'.join(overworked_employees(a.start, a.end, a.threshold, a.days))))

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
    init_db(args.db)
    if hasattr(args, 'func'):
        args.func(args)
    else:
        print('No command given. Use -h for help.')


if __name__ == '__main__':
    main()
