# projectmgt

Simple project management tools for small teams.

## Timesheet CLI

Employees can log hours for projects using the `timesheet.py` script. The
script uses a local SQLite database called `timesheet.db` in the script
directory by default. You can specify a different path with the `--db`
option.

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

The report lists each entry and totals the hours for the selected period.
