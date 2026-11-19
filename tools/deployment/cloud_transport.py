import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('manifest',type=Path)
    parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args()
    manifest=args.manifest.resolve()
    package=json.loads(manifest.read_text())
    if package.get('target')!='cloud' or not re.fullmatch(r'area52-[a-z0-9-]+',package['id']):
        raise ValueError('Invalid Cloud package')
    runner=Path(__file__).with_name('cloud_activation.py')
    expected=hashlib.sha256(runner.read_bytes()).hexdigest()
    if package.get('runner_sha256')!=expected:
        raise ValueError('Cloud runner changed; requalify package')
    root='/srv/area52-staging/releases/'+package['id']
    code=('import hashlib, pathlib, subprocess; '
          'p=pathlib.Path('+repr(root)+'); '
          'assert hashlib.sha256((p/"package.json").read_bytes()).hexdigest()=='+repr(hashlib.sha256(manifest.read_bytes()).hexdigest())+'; '
          'assert hashlib.sha256((p/"cloud_activation.py").read_bytes()).hexdigest()=='+repr(expected)+'; '
          'subprocess.run(["python3",str(p/"cloud_activation.py"),str(p/"package.json")'+(',"--check-only"' if args.check_only else '')+'],check=True)')
    ssh=Path('C:/Windows/System32/OpenSSH/ssh.exe')
    result=subprocess.run([str(ssh),'-i',str(Path.home()/'.ssh/area52_bluehost_staging'),'-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15','root@129.121.172.245','python3 -'],input=code.encode())
    raise SystemExit(result.returncode)


if __name__=='__main__':main()
