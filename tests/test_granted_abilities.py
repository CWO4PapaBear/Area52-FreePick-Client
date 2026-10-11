from pathlib import Path
import importlib.util
import unittest
from lupa.lua51 import LuaRuntime

ROOT=Path(__file__).resolve().parents[1]
ADDON=ROOT/'client/Interface/AddOns/Area52MysticRules'
spec=importlib.util.spec_from_file_location('builder',ROOT/'tools/build_granted_abilities.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)

class GrantedAbilitiesTests(unittest.TestCase):
    def setUp(self):
        self.lua=LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute('''
known={}; native={}; shift=false; realm="Area 52 - Free-Pick"; picking=false; states={}
function GetRealmName() return realm end
C_Player={IsHero=function() return true end}
BuildCreatorUtil={IsPickingSpells=function() return picking end}
function IsSpellKnown(id) return known[id] or false end
function IsShiftKeyDown() return shift end
function GetSpellInfo(id) return "Spell "..id,"Rank "..id,"icon" end
function CreateFrame() return {RegisterEvent=function() end,SetScript=function() end} end
C_CharacterAdvancement={GetNumFilteredEntries=function() return #native end,
 GetFilteredEntryAtIndex=function(i) return native[i] end, GetClassInfo=function() return "WARRIOR" end,
 GetEntryBySpellID=function() return nil end}
ModTooltipSetSpell={}
function Area52GetCertificationStatus(id) return states[id] end
Area52GrantedAbilityCatalog={{root=100,ranks={100,101},entry=0,name="Granted",verified=true,
 sources={{kind="mystic",id=400,name="Hoplite",spell=400},{kind="advancement",id=9,name="Mastery",spell=900}}}}
''')
        self.lua.execute((ADDON/'GrantedAbilities.lua').read_text(encoding='utf-8-sig'))

    def test_known_unknown_search_highest_rank_and_removal(self):
        self.lua.execute('''
local M=Area52GrantedAbilities
M.Rebuild("",{FILTER_KNOWN=true});assert(M.Count()==0)
M.Rebuild("",{FILTER_UNKNOWN=true});assert(M.Count()==1)
known[100]=true;known[101]=true
M.Rebuild("hoplite",{FILTER_KNOWN=true});assert(M.Count()==1 and M.Known(M.rows[1])==101)
assert(M.CurrentSpell(100)==101)
M.Rebuild("absent",{});assert(M.Count()==0)
M.Rebuild("",{FILTER_UNKNOWN=true});assert(M.Count()==0)
known[101]=nil;assert(M.Known(Area52GrantedAbilityCatalog[1])==100)
known[100]=nil;M.Rebuild("",{FILTER_KNOWN=true});assert(M.Count()==0)
''')

    def test_deduplication_and_filters_and_other_realms(self):
        self.lua.execute('''
local M=Area52GrantedAbilities
known[101]=true;native={{ID=9,Spells={100}}}
M.Rebuild("",{});assert(M.Count()==1 and #M.rows==0)
native={}
for _,filter in ipairs({{FILTER_CAN_LEARN=true},{FILTER_CAN_UNLEARN=true},{FILTER_TYPE_TALENT=true},
 {FILTER_CLASS_MAGE=true},{FILTER_QUALITY_LEGENDARY=true}}) do M.Rebuild("",filter);assert(M.Count()==0) end
M.Rebuild("",{FILTER_TYPE_ABILITY=true,FILTER_CLASS_WARRIOR=true,FILTER_QUALITY_NORMAL=true});assert(M.Count()==1)
picking=true;M.Rebuild("",{});assert(M.Count()==0)
picking=false;realm="Other";M.Rebuild("",{});assert(M.Count()==0)
''')

    def test_tooltip_preserves_existing_shift_text_and_spacing(self):
        self.lua.execute('''
local M=Area52GrantedAbilities
local text="Original SHIFT text\\n\\n|cffffff00VERIFIED|r"
local line={GetText=function() return text end,SetText=function(_,v) text=v end}
M.Tooltip({},line,{},101);assert(text=="Original SHIFT text\\n\\n|cffffff00VERIFIED|r")
shift=true;states[1073741924]="C"
M.Tooltip({},line,{},101)
assert(text=="Original SHIFT text\\n\\nLearned from Mystic Enchant: Hoplite\\nLearned from Ability or Talent: Mastery\\n\\n|cff00ff00CERTIFIED|r")
local previous=text;M.Tooltip({},line,{},101);assert(text==previous)
''')

    def test_certification_identity_and_click_safety(self):
        self.lua.execute('''
local M=Area52GrantedAbilities;local r=Area52GrantedAbilityCatalog[1]
assert(M.CertificationID(r)==1073741924)
r.entry=55;assert(M.CertificationID(r)==55)
clicks=0;CharacterAdvancement={ShowSpellDropDownMenu=function() clicks=clicks+1 end}
function CloseDropDownMenus() end
function IsModifiedClick() return false end
local button={area52Grant=r,GetNormalTexture=function() end}
assert(M.Click(button,"LeftButton") and clicks==0)
assert(M.Click(button,"RightButton") and clicks==1)
''')

    def test_recycled_row_restores_drag_and_clears_grant_controls(self):
        self.lua.execute('''
local M=Area52GrantedAbilities
local hidden={Hide=function() end}
local icon={Rank=hidden,RankBorder=hidden,SetIcon=function() end,SetIconDesaturated=function() end,
 SetIconColor=function() end,EnableDrag=function() end,SetScript=function(self,k,v) self[k]=v end,
 GetScript=function(self,k) return self[k] end}
local b={index=1,Icon=icon,Text={SetTextColor=function() end},TalentEssence=hidden,AbilityEssence=hidden,
 EssenceText=hidden,RarityGemText=hidden,ClassPoints=hidden,LockButton=hidden,ExpandedContent=hidden,
 RarityGemContainer={SetNumGems=function() end},SetText=function() end,UnlockHighlight=function() end,
 Collapse=function() end}
M.Rebuild("",{});assert(M.UpdateRow(b) and not b.known and b.spellID==100)
known[101]=true;assert(M.UpdateRow(b) and b.known and b.spellID==101)
local picked;function PickupSpell(id) picked=id end
icon.OnDragStart();assert(picked==101)
M.rows={};assert(not M.UpdateRow(b) and b.area52Grant==nil and icon.OnDragStart==nil)
local original=function() end;icon.OnDragStart=original
M.Rebuild("",{});assert(M.UpdateRow(b))
M.rows={};assert(not M.UpdateRow(b) and icon.OnDragStart==original)
''')

    def test_generator_only_follows_grants_not_damage_triggers(self):
        effective={'advancement':[], 'spells':[
            {'id':'400','present':'true','name':'ME','rank_root':'400','passive':'true',
             'edges':[{'target':'100','kind':'reviewed_script_grant'},{'target':'200','kind':'trigger'}]},
            {'id':'100','present':'true','name':'Visible','rank_root':'100','passive':'false','rank':'1',
             'edges':[{'target':'101','kind':'next_rank'}]},
            {'id':'101','present':'true','name':'Visible','rank_root':'100','passive':'false','rank':'2'},
            {'id':'200','present':'true','name':'Damage','rank_root':'200','passive':'false'}]}
        statuses={'entries':[{'kind':'mystic','id':400,'name':'ME','status':'VERIFIED','spells':[400,100,101]}]}
        rows=builder.build(effective,statuses)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['ranks'],[100,101]);self.assertTrue(rows[0]['verified'])
        statuses['entries'][0]['spells']=[400,100]
        self.assertFalse(builder.build(effective,statuses)[0]['verified'])
        effective['spells'][1]['attributes0']='128'
        effective['spells'][2]['attributes0']='128'
        self.assertEqual(builder.build(effective,statuses),[])

if __name__=='__main__':unittest.main()
