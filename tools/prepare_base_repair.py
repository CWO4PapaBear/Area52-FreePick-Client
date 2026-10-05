from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]
LAUNCHER=ROOT.parent/'Bear-Cave-Launcher'
sys.path[:0]=[str(LAUNCHER),str(LAUNCHER/'tools')]
from package import build,sha
from launcher import baseline,updater

def main():
    client=Path(sys.argv[1]).resolve()
    previous=json.loads((ROOT/'dist/area52-0.1.0-alpha.2/manifest.json').read_text())
    version='0.1.0-alpha.3'
    config=dict(channel='area52',version=version,repository=updater.repository('area52'),
        server_build='75cf732a123cdead7ad71f08669587afc16d12359b1c604860d743f823aea37a',
        components=[dict(id=c['id'],paths=[f['path'] for f in c['files']]) for c in previous['components']])
    config['components'].append(dict(id='area52-base-repair',paths=['Ascension.ok','Data/patch-M.MPQ','Data/patch-S.MPQ']))
    output=ROOT/'dist'/('area52-'+version)
    manifest=build(client,config,output,'Area 52 client repair update\n\nRequires Bear Cave Launcher 0.3.6. Repairs the tested patch-M, patch-S and Ascension product manifest, and includes current Area 52 overlays. Existing managed files are backed up; personal settings and caches are excluded. Other base-client differences remain blocked for review.\n')
    records={r['path'].lower():dict(r) for r in previous['baseline']}
    for c in manifest['components']:
        for r in c['files']:
            if baseline.path_allowed(r['path']):records[r['path'].lower()]=dict(r)
    manifest.update(schema=3,minimum_launcher_build=306,baseline=list(records.values()))
    updater.validate_manifest(manifest,'area52')
    mismatches,_=baseline.compare(client,manifest['baseline'])
    (output/'baseline-review.json').write_text(json.dumps(mismatches,indent=2))
    if mismatches:raise RuntimeError('Unmanaged baseline differences require review: '+repr(mismatches))
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    names=['manifest.json','PATCH-NOTES.md']+[c['asset'] for c in manifest['components']]
    (output/'SHA256SUMS').write_text(''.join(sha(output/n)+'  '+n+'\n' for n in sorted(names)))
    print('Validated package:',output,flush=True)

if __name__=='__main__':main()
