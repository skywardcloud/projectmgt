import sqlite3
from functools import wraps
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
)
from datetime import date, datetime
from werkzeug.security import generate_password_hash
import timesheet

app = Flask(__name__)
app.secret_key = 'secret-key'

# Initialize the database when the application starts.  Some minimal
# Flask implementations used in this environment may not implement the
# ``before_first_request`` decorator, so we invoke ``timesheet.init_db``
# directly to ensure the database tables are created.
timesheet.init_db()


def add_employee(name):
    try:
        with timesheet.connect_db() as conn:
            cur = conn.cursor()
            _, created = timesheet.get_or_create(cur, 'employees', name)
            if created:
                conn.commit()
                return True, f"Employee '{name}' added"
            return False, f"Employee '{name}' already exists"
    except sqlite3.Error as e:
        return False, f"Failed to add employee: {e}"


def add_project(name):
    try:
        with timesheet.connect_db() as conn:
            cur = conn.cursor()
            _, created = timesheet.get_or_create(cur, 'projects', name)
            if created:
                conn.commit()
                return True, f"Project '{name}' added"
            return False, f"Project '{name}' already exists"
    except sqlite3.Error as e:
        return False, f"Failed to add project: {e}"


def fetch_projects():
    """Return a list of all project names ordered alphabetically."""
    try:
        with timesheet.connect_db() as conn:
            cur = conn.cursor()
            cur.execute('SELECT name FROM projects ORDER BY name')
            return [row[0] for row in cur.fetchall()]
    except sqlite3.Error:
        return []


def fetch_managers():
    """Return list of (id, full_name) for active manager users."""
    try:
        with timesheet.connect_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, full_name FROM users "
                "WHERE role IN ('Admin', 'Project Manager') "
                "AND status = 'Active' ORDER BY full_name"
            )
            return cur.fetchall()
    except sqlite3.Error:
        return []


def fetch_employees():
    """Return list of (id, name) for all employees."""
    try:
        with timesheet.connect_db() as conn:
            cur = conn.cursor()
            cur.execute('SELECT id, name FROM employees ORDER BY name')
            return cur.fetchall()
    except sqlite3.Error:
        return []


def add_project_master(data):
    """Insert a project_master record."""
    try:
        with timesheet.connect_db() as conn:
            cur = conn.cursor()
            cur.execute(
                'SELECT 1 FROM project_master WHERE project_name = ?',
                (data['project_name'],),
            )
            if cur.fetchone():
                return False, 'Project name already exists'
            cur.execute(
                'SELECT 1 FROM project_master WHERE project_code = ?',
                (data['project_code'],),
            )
            if cur.fetchone():
                return False, 'Project code already exists'
            cur.execute(
                '''INSERT INTO project_master(
                       project_name, project_code, client_name,
                       start_date, end_date, description, manager_id,
                       estimated_hours, status, billing_type,
                       created_by, created_date
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    data['project_name'],
                    data['project_code'],
                    data.get('client_name'),
                    data.get('start_date'),
                    data.get('end_date'),
                    data.get('description'),
                    data.get('manager_id'),
                    data.get('estimated_hours'),
                    data.get('status'),
                    data.get('billing_type'),
                    data.get('created_by'),
                    datetime.utcnow().isoformat(timespec='seconds'),
                ),
            )
            pid = cur.lastrowid
            cur.execute(
                'UPDATE project_master SET project_id = ? WHERE id = ?',
                (f"PROJ{pid:03d}", pid),
            )
            conn.commit()
            return True, pid
    except sqlite3.Error as e:
        return False, f'Failed to add project: {e}'


def add_user(data):
    """Insert a user record and return (success, message)."""
    try:
        with timesheet.connect_db() as conn:
            cur = conn.cursor()
            cur.execute('SELECT 1 FROM users WHERE email = ?', (data['email'],))
            if cur.fetchone():
                return False, 'Email already exists'
            cur.execute(
                'SELECT 1 FROM users WHERE username = ?', (data['username'],)
            )
            if cur.fetchone():
                return False, 'Username already exists'
            cur.execute(
                '''INSERT INTO users(
                    full_name, email, phone, username, password,
                    department, designation, role, date_of_joining,
                    status, reporting_manager
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    data['full_name'],
                    data['email'],
                    data.get('phone'),
                    data['username'],
                    generate_password_hash(data['password']),
                    data['department'],
                    data.get('designation'),
                    data['role'],
                    data.get('date_of_joining'),
                    data['status'],
                    data.get('reporting_manager'),
                ),
            )
            user_id = cur.lastrowid
            cur.execute(
                'UPDATE users SET user_id = ? WHERE id = ?',
                (f"USR{user_id:03d}", user_id),
            )
            conn.commit()
            return True, 'User created'
    except sqlite3.Error as e:
        return False, f'Failed to add user: {e}'


def log_time_entry(employee, project, hours, entry_date, remarks=None):
    """Insert a timesheet entry and return (success, message)."""
    # Validation copied from timesheet.log_time
    if hours <= 0 or hours > 24:
        return False, 'Hours must be greater than 0 and no more than 24.'
    if hours * 2 != int(hours * 2):
        return False, 'Hours must be in 0.5 hour increments.'
    try:
        entry = datetime.strptime(entry_date, '%Y-%m-%d').date()
    except ValueError:
        return False, 'Date must be in YYYY-MM-DD format.'
    if entry > date.today():
        return False, 'Date cannot be in the future.'
    try:
        with timesheet.connect_db() as conn:
            cur = conn.cursor()
            emp_id, _ = timesheet.get_or_create(cur, 'employees', employee)
            proj_id, _ = timesheet.get_or_create(cur, 'projects', project)
            cur.execute(
                'INSERT INTO timesheets(employee_id, project_id, entry_date, hours, remarks) '
                'VALUES (?, ?, ?, ?, ?)',
                (emp_id, proj_id, entry.isoformat(), hours, remarks),
            )
            conn.commit()
            return True, 'Time entry recorded'
    except sqlite3.Error as e:
        return False, f'Failed to log time: {e}'


def project_summary(start=None, end=None):
    """Return list of (project, total_hours) tuples."""
    with timesheet.connect_db() as conn:
        cur = conn.cursor()
        query = (
            'SELECT p.name, SUM(t.hours) FROM timesheets t '
            'JOIN projects p ON p.id = t.project_id WHERE 1=1'
        )
        params = []
        if start:
            query += ' AND t.entry_date >= ?'
            params.append(start)
        if end:
            query += ' AND t.entry_date <= ?'
            params.append(end)
        query += ' GROUP BY p.name ORDER BY p.name'
        cur.execute(query, params)
        return cur.fetchall()


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'employee' not in session:
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    return wrapper


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/employee', methods=['GET', 'POST'])
def employee():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Employee name is required', 'error')
        else:
            ok, msg = add_employee(name)
            flash(msg, 'success' if ok else 'error')
            if ok:
                return redirect(url_for('employee'))
    return render_template('employee_form.html')


@app.route('/project', methods=['GET', 'POST'])
def project():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Project name is required', 'error')
        else:
            ok, msg = add_project(name)
            flash(msg, 'success' if ok else 'error')
            if ok:
                return redirect(url_for('project'))
    return render_template('project_form.html')


@app.route('/project-master', methods=['GET', 'POST'])
def project_master():
    managers = fetch_managers()
    employees = fetch_employees()
    if request.method == 'POST':
        form = request.form
        data = {
            'project_name': form.get('project_name', '').strip(),
            'project_code': form.get('project_code', '').strip(),
            'client_name': form.get('client_name', '').strip() or None,
            'start_date': form.get('start_date') or None,
            'end_date': form.get('end_date') or None,
            'description': form.get('description', '').strip() or None,
            'manager_id': form.get('manager_id') or None,
            'estimated_hours': form.get('estimated_hours') or None,
            'status': form.get('status', '').strip(),
            'billing_type': form.get('billing_type', '').strip() or None,
        }
        errors = []
        if not data['project_name']:
            errors.append('Project name is required')
        if not data['project_code']:
            errors.append('Project code is required')
        if (
            data['start_date']
            and data['end_date']
            and data['start_date'] > data['end_date']
        ):
            errors.append('Start date must be before end date')
        if not data['manager_id']:
            errors.append('Project manager is required')
        if not data['status']:
            errors.append('Status is required')
        if errors:
            for e in errors:
                flash(e, 'error')
        else:
            ok, result = add_project_master(data)
            if ok:
                project_id = result
                assignees = request.form.getlist('assigned_employees')
                with timesheet.connect_db() as conn:
                    cur = conn.cursor()
                    for uid in assignees:
                        cur.execute(
                            'INSERT OR IGNORE INTO project_assignments(project_id, user_id) VALUES (?, ?)',
                            (project_id, uid),
                        )
                    conn.commit()
                flash('Project created', 'success')
                return redirect(url_for('project_master'))
            else:
                flash(result, 'error')
    return render_template(
        'project_master_form.html', managers=managers, employees=employees
    )


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Name is required', 'error')
        else:
            # Ensure employee exists
            ok, msg = add_employee(name)
            if not ok and 'already exists' not in msg:
                flash(msg, 'error')
                return render_template('login.html')
            session['employee'] = name
            return redirect(url_for('dashboard'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('employee', None)
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', employee=session['employee'])


@app.route('/manager/summary')
def manager_summary():
    start = request.args.get('start')
    end = request.args.get('end')
    data = project_summary(start, end)
    return render_template('manager_summary.html', data=data, start=start, end=end)


@app.route('/api/payroll')
def payroll_api():
    """Return timesheet entries in JSON for payroll systems."""
    with timesheet.connect_db() as conn:
        cur = conn.cursor()
        cur.execute(
            'SELECT e.name, p.name, t.entry_date, t.hours, t.remarks '
            'FROM timesheets t '
            'JOIN employees e ON e.id = t.employee_id '
            'JOIN projects p ON p.id = t.project_id '
            'ORDER BY t.entry_date'
        )
        rows = [
            dict(employee=r[0], project=r[1], date=r[2], hours=r[3], remarks=r[4])
            for r in cur.fetchall()
        ]
    return {'entries': rows}


@app.route('/user', methods=['GET', 'POST'])
def user_master():
    managers = fetch_managers()
    if request.method == 'POST':
        form = request.form
        data = {
            'full_name': form.get('full_name', '').strip(),
            'email': form.get('email', '').strip(),
            'phone': form.get('phone', '').strip() or None,
            'username': form.get('username', '').strip(),
            'password': form.get('password', ''),
            'department': form.get('department', '').strip(),
            'designation': form.get('designation', '').strip() or None,
            'role': form.get('role', '').strip(),
            'date_of_joining': form.get('date_of_joining') or None,
            'status': form.get('status', 'Active'),
            'reporting_manager': form.get('reporting_manager') or None,
        }
        errors = []
        if not data['full_name']:
            errors.append('Full name is required')
        if not data['email']:
            errors.append('Email is required')
        if not data['username']:
            errors.append('Username is required')
        if not data['password']:
            errors.append('Password is required')
        if not data['department']:
            errors.append('Department is required')
        if not data['role']:
            errors.append('Role is required')
        if errors:
            for e in errors:
                flash(e, 'error')
        else:
            ok, msg = add_user(data)
            flash(msg, 'success' if ok else 'error')
            if ok:
                return redirect(url_for('user_master'))
    return render_template('user_form.html', managers=managers)


@app.route('/timesheet', methods=['GET', 'POST'])
@login_required
def timesheet_entry():
    if request.method == 'POST':
        projects = request.form.getlist('project[]')
        hours_list = request.form.getlist('hours[]')
        dates = request.form.getlist('entry_date[]')
        remarks_list = request.form.getlist('remarks[]')
        ok_all = True
        for proj, hrs_str, dt, rem in zip(projects, hours_list, dates, remarks_list):
            proj = proj.strip()
            if not proj:
                flash('Project name is required', 'error')
                ok_all = False
                continue
            try:
                hrs = float(hrs_str)
            except (TypeError, ValueError):
                flash('Invalid hours value', 'error')
                ok_all = False
                continue
            ok, msg = log_time_entry(session['employee'], proj, hrs, dt, rem)
            flash(msg, 'success' if ok else 'error')
            if not ok:
                ok_all = False
        if ok_all:
            return redirect(url_for('timesheet_entry'))
    return render_template('timesheet_form.html', projects=fetch_projects(), today=date.today().isoformat())


if __name__ == '__main__':
    app.run(debug=True)
