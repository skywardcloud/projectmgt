import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash
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


if __name__ == '__main__':
    app.run(debug=True)
