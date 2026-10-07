from pathlib import Path
import os
import sys
sys.path.insert(0, os.environ['AREA52_LUPA_PATH'])
from lupa.lua51 import LuaRuntime
lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute('''
enabled = true; runes = 250; combat = false; dead = false; spent = 1; draft = false; level = 11; sent = 0; hero = true; wildcard = false
C_Config = {GetBoolConfig=function() return enabled end}
C_Player = {IsHero=function() return hero end}
Enum = {GameMode={WildCard=1,BuildDraft=2},CAConfirmReason={Marks="marks",Gold="gold",Token="token",RemovesMastery="mastery",IncludesMastery="include"}}
C_GameMode = {IsGameModeActive=function(self, mode) return mode == 1 and wildcard or mode == 2 and draft end}
function GetItemCount() return runes end
function UnitAffectingCombat() return combat end
function UnitIsDeadOrGhost() return dead end
function UnitLevel() return level end
C_CharacterAdvancement = {
 CanUnlearnID=function() return true, "CA_UNLEARN_OK", 0 end,
 ShouldConfirmUnlearnID=function() return true, {{Error="gold",Arg1=99999},{Error="mastery",Arg1=10}} end,
 UnlearnID=function() sent=sent+1; return true end,
 GetLearnedAE=function() return spent end, GetLearnedTE=function() return spent end
}
for _, suffix in ipairs({"Talents","Spells"}) do
 local prefix = suffix == "Talents" and "CA_PURGE_TALENTS_" or "CA_PURGE_ABILITIES_"
 C_CharacterAdvancement["CanUnlearnAll"..suffix]=function() return false, prefix..(combat and "NOT_IN_COMBAT" or "NO_PURGE_ITEM") end
 C_CharacterAdvancement["UnlearnAll"..suffix]=function() sent=sent+1; return true end
end
CharacterAdvancementUtil={ConfirmOrUnlearnAllTalents=function() return "native" end,ConfirmOrUnlearnAllSpells=function() return "native" end}
Item={CreateFromID=function() return {GetIconTextureMarkup=function() return "ICON" end} end}
TALENTS="talents"; ABILITIES="abilities"; UIErrorsFrame={AddMessage=function() end}
CONFIRM_UNLEARN_ALL_S="Unlearn all %s?%s"
local measure={SetFontObject=function() end,SetWidth=function() end,SetText=function() end,GetStringHeight=function() return 40 end,GetStringWidth=function() return 100 end,Hide=function() end}
frame={text={GetFontObject=function() return "font" end,GetWidth=function() return 290 end,GetFont=function() return "font",12 end},CreateFontString=function() return measure end,HookScript=function() end}
GameTooltip={SetOwner=function() end,SetHyperlink=function(self,link) tooltipLink=link end,Show=function() end,Hide=function() tooltipLink=nil end}
function CreateFrame() return {SetSize=function() end,SetScript=function(self,key,func) self[key]=func end,ClearAllPoints=function() end,SetPoint=function() end,Show=function() end,Hide=function() end} end
function StaticPopup_Show(key, label, warning, callback) popup={key,label,warning,callback};return frame end
''')
lua.execute(Path(os.environ['AREA52_RESET_LUA']).read_text(encoding='utf-8-sig'))
lua.execute('''
for _, suffix in ipairs({"Talents","Spells"}) do
 runes=250; combat=false; spent=1; dead=false
 assert(C_CharacterAdvancement["CanUnlearnAll"..suffix]())
 assert(CharacterAdvancementUtil["ConfirmOrUnlearnAll"..suffix]())
 assert(string.find(popup[3],"Cost:|r 250",1,true))
 assert(string.find(popup[3],"remain selected",1,true))
 assert(string.find(popup[3],"|cffff0000Cost:|r",1,true))
 assert(string.find(popup[3],"|cffffff00Active Build|r",1,true))
 assert(string.find(popup[3],"\\n\\nYour saved",1,true))
 frame.area52RuneIcon:OnEnter(); assert(tooltipLink=="item:375250")
 frame.area52RuneIcon:OnLeave(); assert(tooltipLink==nil)
 local before=sent
 assert(sent==before)
 runes=249; assert(not popup[4]()); assert(sent==before)
 runes=250; assert(popup[4]()); assert(sent==before+1)
 combat=true; assert(not C_CharacterAdvancement["CanUnlearnAll"..suffix]()); combat=false
 spent=0; assert(not C_CharacterAdvancement["CanUnlearnAll"..suffix]()); spent=1
 dead=true; assert(not C_CharacterAdvancement["CanUnlearnAll"..suffix]()); dead=false
 draft=true; level=11; CharacterAdvancementUtil["ConfirmOrUnlearnAll"..suffix](); assert(string.find(popup[3],"forfeits",1,true))
 level=10; CharacterAdvancementUtil["ConfirmOrUnlearnAll"..suffix](); assert(not string.find(popup[3],"forfeits",1,true)); draft=false
end
runes=249; assert(not C_CharacterAdvancement.CanUnlearnID(12))
runes=250; assert(C_CharacterAdvancement.CanUnlearnID(12))
local yes,reasons=C_CharacterAdvancement.ShouldConfirmUnlearnID(12)
assert(yes and #reasons==2 and reasons[1].Error=="mastery" and reasons[2].Error=="marks" and reasons[2].Arg1==250)
runes=499; assert(not C_CharacterAdvancement.CanUnlearnID({12,13}))
runes=500; assert(C_CharacterAdvancement.CanUnlearnID({12,13}))
enabled=false; runes=0; assert(C_CharacterAdvancement.CanUnlearnID(12)); assert(CharacterAdvancementUtil.ConfirmOrUnlearnAllSpells()=="native")
enabled=true; wildcard=true; assert(CharacterAdvancementUtil.ConfirmOrUnlearnAllSpells()=="native")
wildcard=false; hero=false; assert(CharacterAdvancementUtil.ConfirmOrUnlearnAllSpells()=="native")
''')
print('PASS: Lua 5.1 reset affordability, acceptance recheck, confirmation-only cancellation, mode gates, mastery reasons and Draft warning boundary')
