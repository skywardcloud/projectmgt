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
