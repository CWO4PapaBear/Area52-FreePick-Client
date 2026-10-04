import argparse
import json
from pathlib import Path
import re
import subprocess
from .store import Store, UsernameUnavailable


def provision(job, config):
    if config.get('enabled') is not True or config.get('channel') != 'area52':
        raise ValueError('Area 52 worker is not enabled')
    identity, username, salt, verifier = (job[key] for key in ('id', 'username', 'salt', 'verifier'))
    if not re.fullmatch(r'[0-9a-f]{32}', identity) or not re.fullmatch(r'[A-Z0-9_]{3,16}', username):
        raise ValueError('Invalid enrollment identity')
    if any(not re.fullmatch(r'[0-9a-f]{64}', value) for value in (salt, verifier)):
        raise ValueError('Invalid verifier')
    database = config['database']
    if not re.fullmatch(r'[A-Za-z0-9_]+', database):
        raise ValueError('Invalid database')
    realm = config['realm_id']
    if type(realm) is not int or realm < 1:
        raise ValueError('Invalid realm')
    sql = f'''
START TRANSACTION;
INSERT IGNORE INTO area52_enrollment_receipt(request_id,username) VALUES ('{identity}','{username}');
SELECT account_id INTO @existing FROM area52_enrollment_receipt WHERE request_id='{identity}' FOR UPDATE;
INSERT INTO account(username,salt,verifier,expansion,reg_mail,email,joindate)
SELECT '{username}',UNHEX('{salt}'),UNHEX('{verifier}'),2,'','',NOW() WHERE @existing IS NULL;
UPDATE area52_enrollment_receipt SET account_id=LAST_INSERT_ID()
WHERE request_id='{identity}' AND account_id IS NULL;
INSERT IGNORE INTO realmcharacters(realmid,acctid,numchars)
SELECT {realm},account_id,0 FROM area52_enrollment_receipt WHERE request_id='{identity}';
COMMIT;
SELECT account_id FROM area52_enrollment_receipt WHERE request_id='{identity}' AND username='{username}';
'''
    result = subprocess.run([config.get('mysql', 'mysql'),
                             '--defaults-extra-file=' + str(Path(config['mysql_config']).resolve(strict=True)),
                             '--batch', '--skip-column-names', '--connect-timeout=5', database],
                            input=sql, text=True, capture_output=True, timeout=8)
    if result.returncode:
        if 'ERROR 1062 ' in result.stderr and 'idx_username' in result.stderr:
            raise UsernameUnavailable('Choose another username using the same invitation')
        raise RuntimeError('Account provisioning failed; invitation remains reserved for retry')
    value = result.stdout.strip()
    if not value.isdecimal() or int(value) < 1:
        raise RuntimeError('Account receipt missing; retry safely before consuming invitation')
    return int(value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--store', required=True)
    parser.add_argument('--config', required=True, type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    processed = Store(args.store).process_one(lambda job: provision(job, config))
    print('Enrollment completed' if processed else 'No pending enrollment')


if __name__ == '__main__':
    main()
