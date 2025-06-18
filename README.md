# projectmgt

Simple project management tools for small teams.

## Web Interface

A minimal Flask application provides HTML forms for managing users, employees
and projects. Install Flask and run the app with `python web_app.py` then open
`http://localhost:5000` in your browser.

The home page links to a **User Master** form where administrators can create
user accounts with details like email, department and role. Passwords are stored
hashed for security.

Project managers can view project hours using the **Reports** menu. The Project
Summary at `/reports/summary` shows a bar chart of the top 10 projects by total
time with an optional date range filter. The **Productivity Reports** page at
`/reports/productivity` visualizes how employees spend time across projects and
highlights top contributors. Overworked employees (more than 9 hours logged per
day on multiple occasions) are flagged in a separate list. Access both pages
from the landing page at `/reports`.

```bash
pip install flask
python web_app.py
```

## Timesheet CLI

Employees can log hours for projects using the `timesheet.py` script. The script uses a local SQLite database called `timesheet.db` in the script directory by default. You can specify a different path with the `--db` option.

### Setup

No external dependencies are required. Ensure you have Python 3 installed.

### Usage

Initialize the database and add employees or projects:

```bash
python timesheet.py add-employee Alice
python timesheet.py add-project "Awesome Project"
```

Log hours for a project (date defaults to today):

```bash
python timesheet.py log Alice "Awesome Project" 3.5
```

Generate a report for a project:

```bash
python timesheet.py report "Awesome Project" --start 2023-01-01 --end 2023-01-31
```

The report lists each entry and totals the hours for the selected period. Use `--summary` to group totals by employee or date:

```bash
python timesheet.py report "Awesome Project" --summary employee
python timesheet.py report "Awesome Project" --summary date --start 2023-01-01 --end 2023-01-31
```

Update or delete a time entry:

```bash
# update by id
python timesheet.py update --id 1 --new-hours 4

# or locate by employee, project and date
python timesheet.py update --employee Alice --project "Awesome Project" \
  --entry-date 2023-02-01 --new-date 2023-02-02

# delete an entry
python timesheet.py delete --id 1
```

### Commands

Below is a summary of the available commands. Use `-h` with any command for help on its options.

#### `add-employee`

Adds a new employee to the database.

```bash
python timesheet.py add-employee <name>
```

#### `add-project`

Registers a project so employees can log time against it.

```bash
python timesheet.py add-project "<project name>"
```

#### `log`

Records hours for an employee on a project. The date defaults to today and can be overridden with the `--date` option (format: `YYYY-MM-DD`).

```bash
python timesheet.py log <employee> "<project>" <hours> [--date YYYY-MM-DD]
```

#### `report`

Displays recorded entries for a project. Use `--start` and `--end` to limit the date range. Totals can be grouped with `--summary employee` or `--summary date`.

```bash
python timesheet.py report "<project>" [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--summary employee|date]
```

#### `summary`

Displays aggregated hours grouped by project or employee. Optional `--period`
can break down results daily, weekly or monthly.

```bash
python timesheet.py summary --by project --period monthly --start 2023-01-01
```

#### `update`

Updates an existing entry. Identify the entry by `--id` or by employee, project and date.

```bash
python timesheet.py update --id <entry id> --new-hours <hours>
```

#### `delete`

Deletes a time entry by `--id` or by employee/project/date.

```bash
python timesheet.py delete --id <entry id>
```

### Database location

By default the CLI stores data in a file named `timesheet.db` located in the current working directory. You can change this location by either setting the `TIMESHEET_DB` environment variable or using the global `--db` option:

```bash
# Use an environment variable
export TIMESHEET_DB=/path/to/my.db

# Or pass the path for a single invocation
python timesheet.py --db /path/to/my.db add-employee Alice
```

### Troubleshooting

* **Employee or project already exists** – The CLI prints an error if you try to add a duplicate entry. Use a different name or remove the existing record directly from the database.
* **"No command given" message** – Make sure you specify one of the commands (`add-employee`, `add-project`, `log`, `report`, `summary`, `update`, or `delete`). Run `python timesheet.py -h` to see available options.
* **"No entries found" when generating a report** – Check that you logged time for the correct project and date range.
* **"table timesheets has no column named remarks" error** – If you see this message, your database was created with an older version of the tool. Running any command will upgrade the database schema automatically.
