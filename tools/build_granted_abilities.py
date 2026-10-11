import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

GRANTED_MASK = 0x40000000
GRANTS = {'learn', 'override_grant', 'reviewed_script_grant'}


def build(effective, statuses):
    spells = {int(s['id']): s for s in effective['spells'] if s.get('present') == 'true'}
    rows = {(r['kind'], int(r['id'])): r for r in statuses['entries']}
    families = defaultdict(list)
    for sid, spell in spells.items():
        families[int(spell.get('rank_root', sid)) or sid].append(sid)
    by_spell = {}
    for entry in effective['advancement']:
        for sid in entry.get('spells') or []:
            by_spell[int(sid)] = int(entry['entry'])
    grants = defaultdict(set)
    for key, row in rows.items():
        roots = [key[1]] if key[0] == 'mystic' else row.get('spells', [])
        pending = [(int(s), False) for s in roots]
        visited = set()
        while pending:
            sid, granted = pending.pop()
            if (sid, granted) in visited or sid not in spells:
                continue
            visited.add((sid, granted))
            spell = spells[sid]
            if granted and spell.get('passive') == 'false' and not int(spell.get('attributes0', 0)) & 0x80:
                root = int(spell.get('rank_root', sid)) or sid
                grants[root].add(key)
            for edge in spell.get('edges') or []:
                kind = edge['kind']
                if kind in GRANTS or kind == 'next_rank':
                    pending.append((int(edge['target']), granted or kind in GRANTS))
    catalog = []
    for root, sources in sorted(grants.items()):
        ranks = sorted(families[root], key=lambda sid: (int(spells[sid].get('rank', 0)), sid))
        ranks = [sid for sid in ranks if spells[sid].get('passive') == 'false'
                 and not int(spells[sid].get('attributes0', 0)) & 0x80]
        if not ranks:
            continue
        entry = next((by_spell[sid] for sid in ranks if sid in by_spell), 0)
        audited = any(rows[key].get('status') in ('VERIFIED', 'CERTIFIED')
                      and set(ranks).issubset(set(map(int, rows[key].get('spells', [])))) for key in sources)
        catalog.append({'root': root, 'ranks': ranks, 'entry': entry,
                        'name': spells[root]['name'], 'verified': audited,
                        'sources': [{'kind': key[0], 'id': key[1], 'name': rows[key]['name'],
                                     'spell': key[1] if key[0] == 'mystic' else int(rows[key]['spells'][0])}
                                    for key in sorted(sources)]})
    return catalog


def lua_value(value):
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return '{' + ','.join(lua_value(v) for v in value) + '}'
    return '{' + ','.join(k + '=' + lua_value(v) for k, v in value.items()) + '}'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--effective', type=Path, required=True)
    parser.add_argument('--status', type=Path, required=True)
    parser.add_argument('--ledger', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    catalog = build(json.loads(args.effective.read_text()), json.loads(args.status.read_text()))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'GrantedAbilityCatalog.lua').write_text(
        'Area52GrantedAbilityCatalog = ' + lua_value(catalog) + '\n', encoding='utf-8')
    (args.output / 'catalog.json').write_text(json.dumps(catalog, indent=2) + '\n')
    ledger = json.loads(args.ledger.read_text())
    ledger['entries'] = [r for r in ledger['entries'] if r['kind'] != 'granted']
    ledger['entries'].extend({'kind': 'granted', 'id': r['root'], 'ranks': r['ranks'],
                              'status': 'VERIFIED' if r['verified'] else 'NOT VERIFIED', 'certified': False}
                             for r in catalog if not r['entry'])
    ledger['granted_evidence_sha256'] = hashlib.sha256(args.effective.read_bytes() + args.status.read_bytes()).hexdigest()
    (args.output / 'certification-ledger.json').write_text(json.dumps(ledger, indent=2) + '\n')
    print({'families': len(catalog), 'new_certifiable': sum(r['verified'] and not r['entry'] for r in catalog)})


if __name__ == '__main__':
    main()
