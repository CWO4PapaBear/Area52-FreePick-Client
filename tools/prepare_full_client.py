"""Package the tested client into bounded, independently hashed release chunks."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1]
LAUNCHER=ROOT.parent/'Bear-Cave-Launcher'
sys.path[:0]=[str(LAUNCHER),str(LAUNCHER/'tools')]
from launcher import baseline,fullclient
from package import safe_file,sha

def main():
    client=Path(sys.argv[1]).resolve()
    old=json.loads((ROOT/'dist/area52-0.1.0-alpha.3/manifest.json').read_text())
    expected={r['path']:r for r in old['baseline']}
    paths=set(expected)
    for folder in ('Data/Content','Data/enUS/Interface/Cinematics','Interface/GLUES','Interface/AddOns'):
        for p in (client/folder).rglob('*'):
            if p.is_file() and baseline.path_allowed(p.relative_to(client).as_posix()):paths.add(p.relative_to(client).as_posix())
    version='0.1.0-alpha.4';tag='area52-'+version
    output=ROOT/'dist'/tag;output.mkdir(exist_ok=False)
    prefix=f'https://github.com/CWO4PapaBear/Area52-FreePick-Client/releases/download/{tag}/'
    m=dict(schema=4,channel='area52',version=version,tag=tag,minimum_launcher_build=307,
           server_build=old['server_build'],notes_url=prefix+'PATCH-NOTES.md',baseline=[],components=[])
    stats={name:(safe_file(client,name).stat().st_size,safe_file(client,name).stat().st_mtime_ns) for name in paths}
    for number,name in enumerate(sorted(paths),1):
        path=safe_file(client,name);cid='file-'+hashlib.sha256(name.encode()).hexdigest()[:20]
        digest=hashlib.sha256();chunks=[];size=0
        with path.open('rb') as source:
            while block:=source.read(fullclient.CHUNK_LIMIT):
                asset=f'{cid}-{len(chunks):03d}.bin';chunk_hash=hashlib.sha256(block).hexdigest()
                (output/asset).write_bytes(block)
                chunks.append(dict(asset=asset,url=prefix+asset,bytes=len(block),sha256=chunk_hash))
                digest.update(block);size+=len(block)
        record=dict(path=name,bytes=size,sha256=digest.hexdigest())
        if name in expected and record!=expected[name]:raise RuntimeError('Tested baseline changed: '+name)
        m['baseline'].append(record)
        m['components'].append(dict(id=cid,bytes=size,files=[record],chunks=chunks))
        print(f'{number}/{len(paths)} packaged {name} ({size} bytes)',flush=True)
    for name,before in stats.items():
        p=safe_file(client,name)
        if (p.stat().st_size,p.stat().st_mtime_ns)!=before:raise RuntimeError('Source changed during packaging: '+name)
    fullclient.validate(m,'CWO4PapaBear/Area52-FreePick-Client')
    for c in m['components']:
        for chunk in c['chunks']:
            if sha(output/chunk['asset'])!=chunk['sha256']:raise RuntimeError('Staged chunk mismatch')
    (output/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    (output/'PATCH-NOTES.md').write_text('Area 52 full client repair\n\nRequires launcher 0.3.7. Every tested baseline file has repair downloads, including runtime, game archives, content data, cinematics, required UI assets and Area 52 addons. Only mismatched files are downloaded. Verified chunks are reused after interrupted downloads. Personal settings, account data, caches, screenshots and optional addons are excluded. Extra MPQs are quarantined with verified backups so they cannot override tested data. Existing files are backed up before installation. The footer progress bar tracks download, installation and final verification.\n')
    records=[(c['asset'],c['sha256']) for component in m['components'] for c in component['chunks']]
    records += [(n,sha(output/n)) for n in ('manifest.json','PATCH-NOTES.md')]
    (output/'SHA256SUMS').write_text(''.join(f'{digest}  {name}\n' for name,digest in sorted(records)))
    print('FULL PACKAGE VERIFIED',len(paths),'files;',sum(r['bytes'] for r in m['baseline']),'bytes',flush=True)

if __name__=='__main__':main()
