import unittest
from web_app import app
import timesheet
from flask import session

class LogoutTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

    def test_logout_clears_session_and_redirects(self):
        # Set session values to simulate logged in user
        with self.client.session_transaction() as sess:
            sess['employee'] = 'Alice'
            sess['role'] = 'Admin'

        response = self.client.get('/logout')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.headers['Location'])

        with self.client.session_transaction() as sess:
            self.assertNotIn('employee', sess)
            self.assertNotIn('role', sess)


class UsersPageTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

        # add a sample user
        with app.app_context():
            with timesheet.connect_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO users (full_name, email, username, password, department, role, status) "
                    "VALUES ('Test User', 'test@example.com', 'testuser', 'x', 'IT', 'Employee', 'Active')"
                )
                conn.commit()

    def test_users_page_loads(self):
        with self.client.session_transaction() as sess:
            sess['employee'] = 'Admin'
            sess['role'] = 'Admin'

        response = self.client.get('/users')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Test User', response.data)


class ProjectsPageTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

        with app.app_context():
            with timesheet.connect_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO users (full_name, email, username, password, department, role, status) "
                    "VALUES ('Manager', 'mgr@example.com', 'manager', 'x', 'IT', 'Project Manager', 'Active')"
                )
                manager_id = cur.lastrowid
                cur.execute(
                    "INSERT INTO project_master (project_name, project_code, manager_id, status) "
                    "VALUES ('Sample Project', 'SP001', ?, 'Active')",
                    (manager_id,),
                )
                conn.commit()

    def test_projects_page_loads(self):
        with self.client.session_transaction() as sess:
            sess['employee'] = 'Manager'
            sess['role'] = 'Project Manager'

        response = self.client.get('/projects')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Sample Project', response.data)

if __name__ == '__main__':
    unittest.main()
