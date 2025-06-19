# Application Navigation

This document outlines the planned navigation structure for the project management web interface. Page URLs are subject to change as the application evolves.

## Navigation Menu

The application groups menu links by user role. A sidebar or top bar can surface these options once the user logs in.

### For All Users
- **Dashboard** → `/dashboard`
- **Timesheet Entry** → `/timesheet-entry`
- **Timesheet History** → `/timesheet-history`

### For Admin / HR
- **User Master** → `/user-master` (includes a link to the User List page)
- **Project Master** → `/project-master`
- **Project Assignment** → `/project-assignment` (optional)
- **Settings** → `/settings`

### For Project Manager
- **Timesheet Review** → `/timesheet-approval`
- **Project Overview** → `/project-overview`
- **Team Utilization** → `/team-utilization`

## Page by Page Summary

| Page URL | Description |
|----------|-------------|
| `/dashboard` | Entry point after login, varies by role. |
| `/timesheet-entry` | Employees log hours; add rows and submit. |
| `/timesheet-history` | Employee view of past time entries. |
| `/user-master` | Admins add or edit users and project allocations. |
| `/users` | List of all users with filters and search. |
| `/projects` | List of projects with filters and search. |
| `/project-master` | Admins and PMs define projects. |
| `/project-overview` | PM view of project timelines and assignments. |
| `/timesheet-approval` | PMs approve or reject submitted timesheets. |
| `/team-utilization` | PMs review team workload. |
| `/reports/summary` | Project hours chart. |
| `/reports/productivity` | Employee productivity charts. |
| `/settings` | Configure cutoffs, working hours, and holidays. |

## Breadcrumbs and Tabs

Breadcrumbs should display the path like `Dashboard > Timesheet > Entry`. Tabs can help switch views such as **Today**, **This Week**, and **Pending Approvals** where appropriate.

