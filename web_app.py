import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash
import timesheet

app = Flask(__name__)
app.secret_key = 'secret-key'

@app.before_first_request
def setup_db():
    timesheet.init_db()


def add_employee(name):
    try:
        with timesheet.connect_db() as conn:
            cur = conn.cursor()
            timesheet.get_or_create(cur, 'employees', name)
            conn.commit()
        return True, f"Employee '{name}' added"
    except sqlite3.IntegrityError:
        return False, f"Employee '{name}' already exists"
    except sqlite3.Error as e:
        return False, f"Failed to add employee: {e}"


def add_project(name):
    try:
        with timesheet.connect_db() as conn:
            cur = conn.cursor()
            timesheet.get_or_create(cur, 'projects', name)
            conn.commit()
        return True, f"Project '{name}' added"
    except sqlite3.IntegrityError:
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
