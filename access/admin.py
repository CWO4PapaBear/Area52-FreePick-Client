import argparse
import os
from pathlib import Path
from .store import Store, digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--store', required=True, type=Path)
    sub = parser.add_subparsers(dest='action', required=True)
    issue = sub.add_parser('issue')
    issue.add_argument('--output', required=True, type=Path)
    issue.add_argument('--days', type=int, default=7)
    revoke = sub.add_parser('revoke')
    revoke.add_argument('--key-hash', required=True)
    args = parser.parse_args()
    args.store.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    store = Store(args.store)
    if os.name != 'nt':
        args.store.chmod(0o600)
    if args.action == 'issue':
        with args.output.open('x', encoding='ascii') as file:
            if os.name != 'nt':
                args.output.chmod(0o600)
            key = store.issue(args.days * 86400)
            file.write(key + '\n')
        print('Invitation written to private file. Revocation identifier:', digest(key))
    else:
        store.revoke(args.key_hash)
        print('Invitation and associated download access revoked. Game account remains unchanged.')


if __name__ == '__main__':
    main()
