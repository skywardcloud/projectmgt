import sqlite3
import argparse
from datetime import date

DB_FILE = 'timesheet.db'


def init_db():
    with sqlite3.connect(DB_FILE) as conn:
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


def get_or_create(cursor, table, name):
    cursor.execute(f"SELECT id FROM {table} WHERE name = ?", (name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute(f"INSERT INTO {table}(name) VALUES(?)", (name,))
    return cursor.lastrowid


def add_employee(args):
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        try:
            get_or_create(cur, 'employees', args.name)
            conn.commit()
            print(f"Employee '{args.name}' added")
        except sqlite3.IntegrityError:
            print(f"Employee '{args.name}' already exists")


def add_project(args):
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        try:
            get_or_create(cur, 'projects', args.name)
            conn.commit()
            print(f"Project '{args.name}' added")
        except sqlite3.IntegrityError:
            print(f"Project '{args.name}' already exists")


def log_time(args):
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        emp_id = get_or_create(cur, 'employees', args.employee)
        proj_id = get_or_create(cur, 'projects', args.project)
        cur.execute(
            'INSERT INTO timesheets(employee_id, project_id, entry_date, hours) VALUES (?, ?, ?, ?)',
            (emp_id, proj_id, args.date, args.hours)
        )
        conn.commit()
        print('Time entry recorded')


def report(args):
    with sqlite3.connect(DB_FILE) as conn:
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


def parse_args():
    parser = argparse.ArgumentParser(description='Simple timesheet tool')
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

    return parser.parse_args()


def main():
    init_db()
    args = parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        print('No command given. Use -h for help.')


if __name__ == '__main__':
    main()
