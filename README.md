# projectmgt

Simple project management tools for small teams.

## Timesheet CLI

Employees can log hours for projects using the `timesheet.py` script. The
script uses a local SQLite database called `timesheet.db`.

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

### Commands

Below is a summary of the available commands. Use `-h` with any command for
help on its options.

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

Records hours for an employee on a project. The date defaults to today and can
be overridden with the `--date` option (format: `YYYY-MM-DD`).

```bash
python timesheet.py log <employee> "<project>" <hours> [--date YYYY-MM-DD]
```

#### `report`

Displays all recorded entries for a project. Use `--start` and `--end` to limit
the date range.

```bash
python timesheet.py report "<project>" [--start YYYY-MM-DD] [--end YYYY-MM-DD]
```

### Database location

By default the CLI stores data in a file named `timesheet.db` located in the
current working directory. You can change this location by either setting the
`TIMESHEET_DB` environment variable or using the global `--db` option:

```bash
# Use an environment variable
export TIMESHEET_DB=/path/to/my.db

# Or pass the path for a single invocation
python timesheet.py --db /path/to/my.db add-employee Alice
```

### Troubleshooting

* **Employee or project already exists** – The CLI prints an error if you try to
  add a duplicate entry. Use a different name or remove the existing record
  directly from the database.
* **"No command given" message** – Make sure you specify one of the commands
  (`add-employee`, `add-project`, `log`, or `report`). Run `python timesheet.py
  -h` to see available options.
* **"No entries found" when generating a report** – Check that you logged time
  for the correct project and date range.
