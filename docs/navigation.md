# Application Navigation

This document outlines the planned navigation structure for the project management web interface. Page URLs are subject to change as the application evolves.

## Navigation Menu

The application groups menu links by user role. A sidebar or top bar can surface these options once the user logs in.

### For All Users
- **Dashboard** → `/dashboard`
- **Timesheet Entry** → `/timesheet-entry`
- **Timesheet History** → `/timesheet-history`

### For Admin / HR
- **User Master** → `/user-master`
- **Project Master** → `/project-master`
- **Project Assignment** → `/project-assignment` (optional)
- **Reports** → `/reports`
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
| `/project-master` | Admins and PMs define projects. |
| `/project-overview` | PM view of project timelines and assignments. |
| `/timesheet-approval` | PMs approve or reject submitted timesheets. |
| `/team-utilization` | PMs review team workload. |
| `/reports` | Admins generate or export reports. |
| `/settings` | Configure cutoffs, working hours, and holidays. |

## Breadcrumbs and Tabs

Breadcrumbs should display the path like `Dashboard > Timesheet > Entry`. Tabs can help switch views such as **Today**, **This Week**, and **Pending Approvals** where appropriate.

