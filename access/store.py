import hashlib
import re
import secrets
import sqlite3
import time
from contextlib import closing, contextmanager


class UsernameUnavailable(ValueError):
    pass


def digest(value):
    return hashlib.sha256(value.encode('ascii')).hexdigest()


def registration(username, password, salt=None):
    if not isinstance(username, str) or not re.fullmatch(r'[A-Za-z0-9_]{3,16}', username):
        raise ValueError('Username must contain 3–16 letters, numbers or underscores')
    if not isinstance(password, str) or not re.fullmatch(r'[\x21-\x7e]{10,16}', password):
        raise ValueError('Password must contain 10–16 printable ASCII characters without spaces')
    username = username.upper()
    salt = secrets.token_bytes(32) if salt is None else salt
    identity = hashlib.sha1((username + ':' + password.upper()).encode('ascii')).digest()
    exponent = int.from_bytes(hashlib.sha1(salt + identity).digest(), 'little')
    modulus = int('894B645E89E1535BBDAD5B8B290650530801B18EBFBF5E8FAB3C82872A3E9BB7', 16)
    verifier = pow(7, exponent, modulus).to_bytes(32, 'little')
    return username, salt.hex(), verifier.hex()


class Store:
    def __init__(self, path):
        self.path = str(path)
        with closing(self.connect()) as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS invitation (
                    key_hash TEXT PRIMARY KEY, expires INTEGER NOT NULL,
                    revoked INTEGER NOT NULL DEFAULT 0, consumed INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS enrollment (
                    id TEXT PRIMARY KEY, key_hash TEXT UNIQUE NOT NULL,
                    token_hash TEXT UNIQUE NOT NULL, username TEXT NOT NULL,
                    salt TEXT, verifier TEXT, status TEXT NOT NULL DEFAULT 'pending',
                    account_id INTEGER, created INTEGER NOT NULL,
                    FOREIGN KEY(key_hash) REFERENCES invitation(key_hash));
            ''')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        return db

    @contextmanager
    def transaction(self):
        db = self.connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def issue(self, lifetime=604800):
        if not 60 <= lifetime <= 2592000:
            raise ValueError('Invitation lifetime must be between one minute and 30 days')
        key = secrets.token_urlsafe(32)
        with self.transaction() as db:
            db.execute('INSERT INTO invitation(key_hash,expires) VALUES (?,?)',
                       (digest(key), int(time.time()) + lifetime))
        return key

    def revoke(self, key_hash):
        with self.transaction() as db:
            if db.execute('UPDATE invitation SET revoked=1 WHERE key_hash=?', (key_hash,)).rowcount != 1:
                raise ValueError('Invitation not found')

    def enroll(self, key, token, username, password):
        for value in (key, token):
            if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', value):
                raise ValueError('Invalid invitation or request credential')
        username, salt, verifier = registration(username, password)
        with self.transaction() as db:
            invite = db.execute('SELECT * FROM invitation WHERE key_hash=?', (digest(key),)).fetchone()
            if not invite or invite['revoked']:
                raise ValueError('Invitation unavailable')
            existing = db.execute('SELECT * FROM enrollment WHERE key_hash=?', (digest(key),)).fetchone()
            if existing:
                if existing['token_hash'] != digest(token):
                    raise ValueError('Invitation already reserved')
                if existing['status'] == 'username_unavailable':
                    db.execute("UPDATE enrollment SET id=?,username=?,salt=?,verifier=?,status='pending' "
                               'WHERE key_hash=?', (secrets.token_hex(16), username, salt, verifier, digest(key)))
                    return self.public(db.execute('SELECT * FROM enrollment WHERE key_hash=?',
                                                  (digest(key),)).fetchone())
                if existing['username'] != username:
                    raise ValueError('Invitation already reserved')
                return self.public(existing)
            if invite['consumed'] or invite['expires'] <= time.time():
                raise ValueError('Invitation unavailable')
            identity = secrets.token_hex(16)
            db.execute('INSERT INTO enrollment(id,key_hash,token_hash,username,salt,verifier,created) '
                       'VALUES (?,?,?,?,?,?,?)',
                       (identity, digest(key), digest(token), username, salt, verifier, int(time.time())))
            return {'id': identity, 'status': 'pending', 'username': username, 'download_access': False}

    @staticmethod
    def public(row):
        return {'id': row['id'], 'status': row['status'], 'username': row['username'],
                'download_access': row['status'] == 'ready'}

    def status(self, token):
        if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
            raise ValueError('Invalid access credential')
        with closing(self.connect()) as db:
            row = db.execute('SELECT e.*,i.revoked FROM enrollment e JOIN invitation i '
                             'ON i.key_hash=e.key_hash WHERE e.token_hash=?', (digest(token),)).fetchone()
            if not row or row['revoked']:
                raise ValueError('Access unavailable')
            return self.public(row)

    def process_one(self, provision):
        with self.transaction() as db:
            row = db.execute("SELECT e.* FROM enrollment e JOIN invitation i ON i.key_hash=e.key_hash "
                             "WHERE e.status='pending' AND i.revoked=0 ORDER BY e.created LIMIT 1").fetchone()
            if not row:
                return False
            try:
                account_id = provision(dict(row))
            except UsernameUnavailable:
                db.execute("UPDATE enrollment SET status='username_unavailable',salt=NULL,verifier=NULL WHERE id=?",
                           (row['id'],))
                return True
            if type(account_id) is not int or account_id < 1:
                raise ValueError('Worker did not confirm an account')
            db.execute("UPDATE enrollment SET status='ready',account_id=?,salt=NULL,verifier=NULL WHERE id=?",
                       (account_id, row['id']))
            db.execute('UPDATE invitation SET consumed=1 WHERE key_hash=?', (row['key_hash'],))
            return True
