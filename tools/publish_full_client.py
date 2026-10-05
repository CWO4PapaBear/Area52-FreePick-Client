"""Upload a full-client draft and verify GitHub asset digests before promotion."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import argparse,hashlib,json,subprocess,time,sys,threading
ROOT=Path(__file__).resolve().parents[1]
REPO='CWO4PapaBear/Area52-FreePick-Client'
GH='C:/Program Files/GitHub CLI/gh.exe'
sys.path[:0]=[str(ROOT.parent/'Bear-Cave-Launcher'),str(ROOT.parent/'Bear-Cave-Launcher/tools')]
from launcher import fullclient

def run(*args):return subprocess.check_output([GH,*args],text=True,encoding='utf-8')
def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def releases():return [r for page in json.loads(run('api','--paginate','--slurp',f'repos/{REPO}/releases')) for r in page]
def assets(release):return {a['name']:a for page in json.loads(run('api','--paginate','--slurp',f'repos/{REPO}/releases/{release["id"]}/assets?per_page=100')) for a in page}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['upload','verify']);args=parser.parse_args()
    package=ROOT/'dist/area52-0.1.0-alpha.4';m=json.loads((package/'manifest.json').read_text());tag=m['tag']
    fullclient.validate(m,REPO)
    chunks=[x for c in m['components'] for x in c['chunks']]
    assert len(chunks)+3<=1000
    existing=[r for r in releases() if r['tag_name']==tag]
    if not existing:
        assert args.action=='upload'
        revision=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
        run('release','create',tag,'--repo',REPO,'--target',revision,'--draft','--prerelease','--latest=false','--title','Area 52 complete client repair alpha.4','--notes-file',str(package/'PATCH-NOTES.md'))
        existing=[r for r in releases() if r['tag_name']==tag]
    assert len(existing)==1
    release=existing[0];remote=assets(release)
    if args.action=='upload':
        assert release['draft'],'Do not modify published releases'
        throttle=threading.Lock();last_request=[0.0]
        def upload(chunk):
            name=chunk['asset'];old=remote.get(name)
            if old:
                if old['state']=='uploaded' and old['size']==chunk['bytes'] and old.get('digest') in (None,'sha256:'+chunk['sha256']):return name
                raise RuntimeError('Existing remote asset differs: '+name)
            for attempt in range(3):
                try:
                    with throttle:
                        time.sleep(max(0,1-(time.monotonic()-last_request[0])));last_request[0]=time.monotonic()
                    run('release','upload',tag,str(package/name),'--repo',REPO);return name
                except subprocess.CalledProcessError:
                    current=assets(release).get(name)
                    if current and current['state']=='uploaded' and current.get('digest')=='sha256:'+chunk['sha256']:return name
                    if current and current['state']=='starter':run('api','--method','DELETE',f'repos/{REPO}/releases/assets/{current["id"]}')
                    if attempt==2:raise
                    time.sleep(3)
        count=0
        with ThreadPoolExecutor(max_workers=3) as pool:
            for future in as_completed([pool.submit(upload,c) for c in chunks]):
                future.result();count+=1
                if count%10==0 or count==len(chunks):print(f'Uploaded {count}/{len(chunks)} chunks',flush=True)
        return
    test=json.loads((package/'install-verification.json').read_text());assert test['result']=='passed'
    for name in ('manifest.json','PATCH-NOTES.md','SHA256SUMS'):
        if name not in remote:run('release','upload',tag,str(package/name),'--repo',REPO)
    remote=assets(release);download=ROOT/'local/remote-full-verification';download.mkdir(exist_ok=True)
    records=[dict(asset=n,bytes=(package/n).stat().st_size,sha256=sha(package/n)) for n in ('manifest.json','PATCH-NOTES.md','SHA256SUMS')]+chunks
    samples={min(chunks,key=lambda c:c['bytes'])['asset'],max(chunks,key=lambda c:c['bytes'])['asset'],'manifest.json'}
    for record in records:
        name=record['asset'];asset=remote.get(name)
        if not asset or asset['state']!='uploaded' or asset['size']!=record['bytes']:raise RuntimeError('Missing/incomplete remote asset: '+name)
        digest=asset.get('digest')
        if digest and digest!='sha256:'+record['sha256']:raise RuntimeError('Remote digest mismatch: '+name)
        if not digest or name in samples:
            path=download/name
            if not path.exists():run('release','download',tag,'--repo',REPO,'--pattern',name,'--dir',str(download))
            if sha(path)!=record['sha256']:raise RuntimeError('Downloaded asset mismatch: '+name)
    (package/'remote-verification.json').write_text(json.dumps(dict(result='passed',assets=len(records),all_remote_digests_checked=True,downloaded_samples=sorted(samples)),indent=2))
    print('All remote assets verified. Draft is ready for promotion.',flush=True)

if __name__=='__main__':main()
