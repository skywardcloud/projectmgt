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
from datetime import date, datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import timesheet

app = Flask(__name__)
app.secret_key = 'secret-key'

# Initialize the database when the application starts.  Some minimal
# Flask implementations used in this environment may not implement the
# ``before_first_request`` decorator, so we invoke ``timesheet.init_db``
# directly to ensure the database tables are created.
timesheet.init_db()


def fetch_projects():
    """Return a list of all project names ordered alphabetically."""
    try:
        with timesheet.connect_db() as conn:
            cur = conn.cursor()
            # Include project names from both the legacy ``projects`` table
            # and the newer ``project_master`` table to ensure dropdowns
            # show all available projects.
            cur.execute(
                "SELECT name FROM projects UNION SELECT project_name FROM project_master ORDER BY 1"
            )
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


def fetch_users():
    """Return list of (id, full_name) for active users."""
    try:
        with timesheet.connect_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, full_name FROM users "
                "WHERE status = 'Active' ORDER BY full_name"
            )
            return cur.fetchall()
    except sqlite3.Error:
        return []


def fetch_user_filter_options():
    """Return distinct values for department, role and status from users."""
    try:
        with timesheet.connect_db() as conn:
            cur = conn.cursor()
            cur.execute('SELECT DISTINCT department FROM users ORDER BY department')
            departments = [r[0] for r in cur.fetchall()]
            cur.execute('SELECT DISTINCT role FROM users ORDER BY role')
            roles = [r[0] for r in cur.fetchall()]
            cur.execute('SELECT DISTINCT status FROM users ORDER BY status')
            statuses = [r[0] for r in cur.fetchall()]
        return departments, roles, statuses
    except sqlite3.Error:
        return [], [], []


def fetch_project_filter_options():
    """Return distinct values for status and client from project_master."""
    try:
        with timesheet.connect_db() as conn:
            cur = conn.cursor()
            cur.execute('SELECT DISTINCT status FROM project_master ORDER BY status')
            statuses = [r[0] for r in cur.fetchall()]
            cur.execute(
                'SELECT DISTINCT client_name FROM project_master '
                'WHERE client_name IS NOT NULL ORDER BY client_name'
            )
            clients = [r[0] for r in cur.fetchall()]
        return statuses, clients
    except sqlite3.Error:
        return [], []


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


def authenticate_user(email, password):
    """Return dict with user info if credentials are valid."""
    try:
        with timesheet.connect_db() as conn:
            cur = conn.cursor()
            cur.execute(
                'SELECT full_name, password, role FROM users WHERE email = ?',
                (email,),
            )
            row = cur.fetchone()
            if row and check_password_hash(row[1], password):
                return {'name': row[0], 'role': row[2]}
    except sqlite3.Error:
        pass
    return None


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
            'SELECT p.name, SUM(t.hours) AS total_hours FROM timesheets t '
            'JOIN projects p ON p.id = t.project_id WHERE 1=1'
        )
        params = []
        if start:
            query += ' AND t.entry_date >= ?'
            params.append(start)
        if end:
            query += ' AND t.entry_date <= ?'
            params.append(end)
        query += ' GROUP BY p.name ORDER BY total_hours DESC LIMIT 10'
        cur.execute(query, params)
        return cur.fetchall()


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'employee' not in session:
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    return wrapper







@app.route('/project-master', methods=['GET', 'POST'])
def project_master():
    managers = fetch_managers()
    employees = fetch_users()
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
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        if not email or not password:
            flash('Email and password are required', 'error')
        else:
            user = authenticate_user(email, password)
            if user:
                session['employee'] = user['name']
                session['role'] = user['role']
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid credentials', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Clear the current session and return to the login page."""
    session.clear()
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    role = session.get('role', 'Employee')
    today = date.today().isoformat()
    with timesheet.connect_db() as conn:
        cur = conn.cursor()

        if role == 'Admin':
            cur.execute('SELECT COUNT(*) FROM projects')
            projects = cur.fetchone()[0]
            cur.execute('SELECT COUNT(*) FROM users')
            employees = cur.fetchone()[0]
            cur.execute('SELECT COUNT(*) FROM timesheets WHERE entry_date = ?', (today,))
            today_entries = cur.fetchone()[0]
            totals = dict(projects=projects, employees=employees,
                          today_entries=today_entries, pending_approvals=0)
            context = dict(totals=totals)

        elif role == 'Project Manager':
            cur.execute('SELECT COUNT(*) FROM project_master')
            projects_managed = cur.fetchone()[0]
            cur.execute('SELECT COUNT(*) FROM timesheets WHERE entry_date = ?', (today,))
            employee_submissions = cur.fetchone()[0]
            cur.execute('SELECT COUNT(*) FROM timesheets WHERE hours > 8 AND entry_date = ?', (today,))
            review_alerts = cur.fetchone()[0]
            chart_data = project_summary()
            context = dict(manager=dict(projects_managed=projects_managed,
                                       employee_submissions=employee_submissions,
                                       review_alerts=review_alerts,
                                       chart_data=chart_data))
        else:
            cur.execute('SELECT name FROM projects ORDER BY name')
            assigned_projects = [r[0] for r in cur.fetchall()]
            start_week = date.today() - timedelta(days=date.today().weekday())
            cur.execute('''SELECT t.entry_date, SUM(t.hours)
                           FROM timesheets t JOIN employees e ON e.id = t.employee_id
                           WHERE e.name = ? AND t.entry_date >= ?
                           GROUP BY t.entry_date ORDER BY t.entry_date''',
                        (session['employee'], start_week.isoformat()))
            week_entries = cur.fetchall()
            cur.execute('''SELECT 1 FROM timesheets t JOIN employees e ON e.id = t.employee_id
                           WHERE e.name = ? AND t.entry_date = ?''',
                        (session['employee'], today))
            submitted_today = cur.fetchone() is not None
            context = dict(employee_view=dict(assigned_projects=assigned_projects,
                                              week_entries=week_entries,
                                              submitted_today=submitted_today))

    return render_template('dashboard.html', employee=session['employee'], role=role, **context)


@app.route('/reports')
def reports_home():
    """Landing page listing available reports."""
    return render_template('reports.html')


@app.route('/manager/summary')
@app.route('/reports/summary')
def manager_summary():
    start = request.args.get('start')
    end = request.args.get('end')
    data = project_summary(start, end)
    labels = [row[0] for row in data]
    hours = [row[1] for row in data]
    return render_template(
        'manager_summary.html',
        data=data,
        labels=labels,
        hours=hours,
        start=start,
        end=end,
    )


@app.route('/reports/productivity')
def productivity_reports():
    start = request.args.get('start')
    end = request.args.get('end')
    employee = request.args.get('employee')
    project = request.args.get('project')

    employees = fetch_users()
    projects = fetch_projects()

    dist_labels, dist_hours = [], []
    if employee:
        data = timesheet.employee_work_distribution(employee, start, end)
        dist_labels = [d[0] for d in data]
        dist_hours = [d[1] for d in data]

    top_labels, top_hours = [], []
    data = timesheet.top_employees(project, start, end)
    top_labels = [d[0] for d in data]
    top_hours = [d[1] for d in data]

    overworked = timesheet.overworked_employees(start, end)

    return render_template(
        'productivity_reports.html',
        employees=employees,
        projects=projects,
        employee_selected=employee,
        project_selected=project,
        start=start,
        end=end,
        dist_labels=dist_labels,
        dist_hours=dist_hours,
        top_labels=top_labels,
        top_hours=top_hours,
        overworked=overworked,
    )


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


@app.route('/users')
@login_required
def users():
    """Display a paginated list of users with filter and search options."""
    page = int(request.args.get('page', 1))
    search = request.args.get('q', '').strip()
    department = request.args.get('department', '')
    role = request.args.get('role', '')
    status = request.args.get('status', '')

    departments, roles, statuses = fetch_user_filter_options()

    base = 'FROM users WHERE 1=1'
    params = []
    if department:
        base += ' AND department = ?'
        params.append(department)
    if role:
        base += ' AND role = ?'
        params.append(role)
    if status:
        base += ' AND status = ?'
        params.append(status)
    if search:
        base += ' AND (full_name LIKE ? OR email LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%'])

    per_page = 10
    with timesheet.connect_db() as conn:
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) ' + base, params)
        total = cur.fetchone()[0]

        cur.execute(
            'SELECT id, full_name, email, department, role, status ' + base +
            ' ORDER BY full_name LIMIT ? OFFSET ?',
            params + [per_page, (page - 1) * per_page]
        )
        rows = [
            dict(id=r[0], full_name=r[1], email=r[2], department=r[3], role=r[4], status=r[5])
            for r in cur.fetchall()
        ]

    total_pages = (total + per_page - 1) // per_page
    return render_template(
        'user_list.html',
        users=rows,
        page=page,
        total_pages=total_pages,
        search=search,
        departments=departments,
        roles=roles,
        statuses=statuses,
        selected_department=department,
        selected_role=role,
        selected_status=status,
    )


@app.route('/projects')
@login_required
def projects():
    """Display a paginated list of projects with filters and search."""
    page = int(request.args.get('page', 1))
    search = request.args.get('q', '').strip()
    status = request.args.get('status', '')
    manager = request.args.get('manager', '')
    client = request.args.get('client', '')

    statuses, clients = fetch_project_filter_options()
    managers = fetch_managers()

    base = (
        'FROM project_master pm LEFT JOIN users u ON pm.manager_id = u.id WHERE 1=1'
    )
    params = []
    if status:
        base += ' AND pm.status = ?'
        params.append(status)
    if manager:
        base += ' AND pm.manager_id = ?'
        params.append(manager)
    if client:
        base += ' AND pm.client_name = ?'
        params.append(client)
    if search:
        base += ' AND (pm.project_name LIKE ? OR pm.project_code LIKE ?)'
        params.extend([f"%{search}%", f"%{search}%"])

    per_page = 10
    with timesheet.connect_db() as conn:
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) ' + base, params)
        total = cur.fetchone()[0]

        cur.execute(
            'SELECT pm.id, pm.project_name, pm.project_code, '
            'u.full_name, pm.start_date, pm.end_date, pm.status, pm.estimated_hours '
            + base +
            ' ORDER BY pm.project_name LIMIT ? OFFSET ?',
            params + [per_page, (page - 1) * per_page],
        )
        rows = [
            dict(
                id=r[0],
                project_name=r[1],
                project_code=r[2],
                manager=r[3],
                start_date=r[4],
                end_date=r[5],
                status=r[6],
                estimated_hours=r[7],
            )
            for r in cur.fetchall()
        ]

    total_pages = (total + per_page - 1) // per_page
    return render_template(
        'project_list.html',
        projects=rows,
        page=page,
        total_pages=total_pages,
        search=search,
        statuses=statuses,
        managers=managers,
        clients=clients,
        selected_status=status,
        selected_manager=int(manager) if manager else '',
        selected_client=client,
    )


@app.route('/user/<int:user_id>/deactivate')
@login_required
def deactivate_user(user_id):
    """Mark a user record as inactive."""
    with timesheet.connect_db() as conn:
        cur = conn.cursor()
        cur.execute('UPDATE users SET status = ? WHERE id = ?', ('Inactive', user_id))
        conn.commit()
    flash('User deactivated', 'success')
    return redirect(url_for('users'))


@app.route('/user/<int:user_id>/profile')
@login_required
def view_profile(user_id):
    """Simple profile page placeholder."""
    with timesheet.connect_db() as conn:
        cur = conn.cursor()
        cur.execute(
            'SELECT full_name, email, department, role, status FROM users WHERE id = ?',
            (user_id,)
        )
        row = cur.fetchone()
    if not row:
        flash('User not found', 'error')
        return redirect(url_for('users'))
    user = dict(full_name=row[0], email=row[1], department=row[2], role=row[3], status=row[4])
    return render_template('user_profile.html', user=user)


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
