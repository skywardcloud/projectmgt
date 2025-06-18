# List of Users Page

This document captures key requirements for an Admin page that lists all user accounts.

## Core Features
- **View all users** with basic info such as full name, email, department, role and status.
- **Filtering** options for department, role and status drop-downs.
- **Search** by name or email. Results update as the user types.
- **Pagination** to handle large numbers of users.
- **Row actions** including Edit, Deactivate and View Profile.

## Enhanced Capabilities
- **AJAX search** so filters and search fields update the table without a full page reload.
- **Export** buttons to download the list in Excel or PDF format.
- **Bulk actions** to deactivate or delete multiple users at once.
- **Invite new user** button that opens the existing user creation form.

These features provide a base specification. Additional design work is required to map database fields and integrate with existing authentication logic.
