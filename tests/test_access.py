from concurrent.futures import ThreadPoolExecutor
import io
import json
from pathlib import Path
import secrets
import shutil
import uuid
from contextlib import closing
import unittest
from access.api import Application
from access.store import Store, UsernameUnavailable, digest, registration


class AccessTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1] / 'local/test-runs'
        base.mkdir(parents=True, exist_ok=True)
        folder = base / uuid.uuid4().hex
        folder.mkdir()
        def cleanup():
            assert folder.resolve().parent == base.resolve()
            shutil.rmtree(folder)
        self.addCleanup(cleanup)
        self.store = Store(folder / 'access.db')
        self.key = self.store.issue()
        self.token = secrets.token_urlsafe(32)

    def enroll(self, token=None):
        return self.store.enroll(self.key, token or self.token, 'Tester', 'Example12345')

    def test_single_use_and_retry(self):
        first = self.enroll()
        self.assertEqual(first, self.enroll())
        with self.assertRaises(ValueError):
            self.enroll(secrets.token_urlsafe(32))
        calls = []
        self.store.process_one(lambda job: calls.append(job) or 42)
        self.assertFalse(self.store.process_one(lambda job: self.fail('Duplicate provisioning')))
        self.assertTrue(self.store.status(self.token)['download_access'])
        self.assertEqual(len(calls), 1)
        with closing(self.store.connect()) as db:
            row = db.execute('SELECT * FROM enrollment').fetchone()
            self.assertIsNone(row['verifier'])
            self.assertIsNone(row['salt'])
            self.assertNotIn('Example12345', str(dict(row)))

    def test_failed_worker_does_not_consume(self):
        self.enroll()
        def failure(job):
            raise RuntimeError('Lost worker response')
        with self.assertRaises(RuntimeError):
            self.store.process_one(failure)
        self.assertEqual(self.store.status(self.token)['status'], 'pending')
        with closing(self.store.connect()) as db:
            self.assertEqual(db.execute('SELECT consumed FROM invitation').fetchone()[0], 0)
        self.store.process_one(lambda job: 42)
        self.assertTrue(self.store.status(self.token)['download_access'])

    def test_concurrent_redemption_only_one_owner(self):
        def attempt(_):
            try:
                self.enroll(secrets.token_urlsafe(32))
                return 1
            except ValueError:
                return 0
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(attempt, range(8))), 1)

    def test_revocation_blocks_worker_and_downloads(self):
        self.enroll()
        self.store.revoke(digest(self.key))
        self.assertFalse(self.store.process_one(lambda job: self.fail('Revoked request')))
        with self.assertRaises(ValueError):
            self.store.status(self.token)

    def test_taken_name_can_retry_without_blocking_other_jobs(self):
        first = self.enroll()
        def unavailable(job):
            raise UsernameUnavailable()
        self.store.process_one(unavailable)
        self.assertFalse(self.store.process_one(lambda job: self.fail('Blocked job selected')))
        second = self.store.enroll(self.key, self.token, 'Another', 'Example12345')
        self.assertNotEqual(first['id'], second['id'])
        self.store.process_one(lambda job: 42)
        self.assertEqual(self.store.status(self.token)['username'], 'ANOTHER')

    def test_expired_invitation_and_unknown_token(self):
        with closing(self.store.connect()) as db:
            db.execute('UPDATE invitation SET expires=0')
            db.commit()
        with self.assertRaises(ValueError):
            self.enroll()
        with self.assertRaises(ValueError):
            self.store.status(self.token)

    def test_credentials_case_matches_core(self):
        salt = bytes(range(32))
        self.assertEqual(registration('Tester', 'Example12345', salt),
                         registration('TESTER', 'EXAMPLE12345', salt))
        for name, password in [('a', 'Example12345'), ('Tester', 'short'), ('Test;er', 'Example12345')]:
            with self.assertRaises(ValueError):
                registration(name, password)

    def test_api_https_and_no_secret_echo(self):
        app = Application(self.store)
        body = json.dumps(dict(invitation=self.key, request_token=self.token,
                               username='Tester', password='Example12345')).encode()
        env = {'wsgi.url_scheme': 'http', 'REQUEST_METHOD': 'POST', 'PATH_INFO': '/v1/area52/enroll',
               'CONTENT_LENGTH': str(len(body)), 'CONTENT_TYPE': 'application/json',
               'wsgi.input': io.BytesIO(body)}
        status = []
        app(env, lambda code, headers: status.append(code))
        self.assertEqual(status[-1], '403 Forbidden')
        env['wsgi.url_scheme'] = 'https'
        response = b''.join(app(env, lambda code, headers: status.append(code))).decode()
        self.assertEqual(status[-1], '200 OK')
        for secret in (self.key, self.token, 'Example12345'):
            self.assertNotIn(secret, response)


if __name__ == '__main__':
    unittest.main()
