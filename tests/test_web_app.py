import unittest
from web_app import app
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

if __name__ == '__main__':
    unittest.main()
