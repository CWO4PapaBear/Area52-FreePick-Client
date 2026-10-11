import argparse
import hashlib
import json
from pathlib import Path
import sys


def patch_sources(files):
    changed = dict(files)
    for addon in ('Ascension_CharacterAdvancement', 'Ascension_CharacterAdvancementSeason9'):
        name = 'Interface\\AddOns\\' + addon + '\\CharacterAdvancement.lua'
        source = files[name].decode('utf-8-sig').replace('\r\n', '\n')
        if 'Area52GrantedAbilities.Rebuild' in source:
            continue
        for call, arguments in [('C_CharacterAdvancement.SetFilteredEntries("", OnlyKnownFilter)', '"", OnlyKnownFilter'),
                                ('C_CharacterAdvancement.SetFilteredEntries(text, header.Filter:GetFilter())',
                                 'text, header.Filter:GetFilter()')]:
            if source.count(call) != 1:
                raise ValueError('Unexpected Advancement search definition: ' + name)
            source = source.replace(call, call + '\n            if Area52GrantedAbilities then Area52GrantedAbilities.Rebuild(' + arguments + ') end')
        source = source.replace('SetGetNumResultsFunction(C_CharacterAdvancement.GetNumFilteredEntries)',
                                'SetGetNumResultsFunction(function() return Area52GrantedAbilities and Area52GrantedAbilities.Count() or C_CharacterAdvancement.GetNumFilteredEntries() end)')
        changed[name] = source.encode('utf-8')
    name = 'Interface\\FrameXML\\SpellListItem.lua'
    source = files[name].decode('utf-8-sig').replace('\r\n', '\n')
    if 'Area52GrantedAbilities.UpdateRow' not in source:
        def inject(signature, body):
            nonlocal source
            if source.count(signature) != 1:
                raise ValueError('Unexpected SpellListItem definition: ' + signature)
            source = source.replace(signature, signature + '\n' + body)
        inject('function SpellListItemMixin:Update()',
               '    if Area52GrantedAbilities and Area52GrantedAbilities.UpdateRow(self) then return end')
        for signature in ['OnClick(button)', 'OnDoubleClick(button)']:
            inject('function SpellListItemMixin:' + signature,
                   '    if Area52GrantedAbilities and Area52GrantedAbilities.Click(self, button) then return end')
        for signature in ['Learn()', 'Unlearn()', 'ToggleLocked()', 'OnSelected()', 'UpdateExpandedContent()']:
            inject('function SpellListItemMixin:' + signature, '    if self.area52Grant then return end')
        inject('function SpellListItemMixin:OnDragStart()',
               '    if self.area52Grant then if self.known then PickupSpell(self.spellID) end; return end')
        call='    GameTooltip:SetHyperlink(LinkUtil:GetSpellLink(self.spellID))'
        if source.count(call) != 1:
            raise ValueError('Unexpected spell tooltip definition')
        source=source.replace(call,call+'\n    if Area52GrantedAbilities then Area52GrantedAbilities.AppendTooltip(GameTooltip, self.spellID) end')
        anchor='    self.Icon.OnClickHandler = GenerateClosure(self.OnClick, self)'
        if 'local originalIconClick' not in source:
            source=source.replace(anchor,anchor+'''
    self.Icon:RegisterForClicks("LeftButtonUp", "RightButtonUp")
    local originalIconClick = self.Icon:GetScript("OnClick")
    self.Icon:SetScript("OnClick", function(icon, button, ...)
        if Area52GrantedAbilities and Area52GrantedAbilities.Click(self, button) then return end
        if button == "RightButton" and GetRealmName() == "Area 52 - Free-Pick" then
            self:OnRightClick()
        elseif originalIconClick then
            originalIconClick(icon, button, ...)
        end
    end)''')
        source=source.replace('self:SetSpell(self.entry.Spells[1])',
                              'self:SetSpell(Area52GrantedAbilities and Area52GrantedAbilities.CurrentSpell(self.entry.Spells[1]) or self.entry.Spells[1])')
        changed[name]=source.encode('utf-8')
    return changed


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--mpq-tools',type=Path,required=True)
    args=parser.parse_args()
    if args.archive.resolve()==args.output.resolve():
        raise ValueError('Stage to a separate output file')
    sys.path.insert(0,str(args.mpq_tools))
    from lib.mpq import MPQArchive,write_archive
    with MPQArchive(args.archive) as archive:
        files={n:archive.read_file(n) for n in archive.read_file('(listfile)').decode().splitlines()
               if n and n.lower() not in ('(listfile)','(attributes)','(signature)')}
    changed=patch_sources(files)
    write_archive(args.output,changed)
    with MPQArchive(args.output) as archive:
        for name,value in changed.items():
            if archive.read_file(name)!=value:
                raise ValueError('Archive readback mismatch: '+name)
    print(json.dumps({'baseline_sha256':hashlib.sha256(args.archive.read_bytes()).hexdigest(),
                      'candidate_sha256':hashlib.sha256(args.output.read_bytes()).hexdigest(),
                      'changed':[n for n in files if files[n]!=changed[n]],'verified_members':len(changed)}))


if __name__=='__main__':
    main()
