from pathlib import Path
import os
import sys

sys.path.insert(0, os.environ['AREA52_LUPA_PATH'])
from lupa.lua51 import LuaRuntime

lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute(r'''
realm = "Area 52 - Free-Pick"; hero = true; picking = false; clock = 0
sent = {}; notices = {}; menu = {}; timers = {}; nativeCalls = 0
function GetRealmName() return realm end
function UnitName() return "Tester" end
function GetTime() return clock end
C_Player = { IsHero = function() return hero end }
BuildCreatorUtil = { IsPickingSpells = function() return picking end }
C_Timer = { After = function(_, callback) table.insert(timers, callback) end }
CANCEL = "Cancel"; StaticPopupDialogs = {}; ModTooltipSetSpell = {}
DEFAULT_CHAT_FRAME = { AddMessage = function(_, message) table.insert(notices, message) end }
function SendAddonMessage(prefix, payload, channel, who) table.insert(sent, {prefix,payload,channel,who}) end
function CreateFrame()
    frame = { RegisterEvent = function() end, SetScript = function(self,k,v) self[k] = v end }
    return frame
end
function hooksecurefunc(object, key, after)
    local before = object[key]
    object[key] = function(...) before(...); after(...) end
end
function UIDropDownMenu_CreateInfo() return {} end
function UIDropDownMenu_AddButton(info) table.insert(menu, info) end
function UIDropDownMenu_Initialize(dropdown, callback) dropdown.initialize = callback end
function CloseDropDownMenus() end
function StaticPopup_Show(key, name, _, data) popup = {key=key,name=name,data=data} end
CharacterAdvancement = {
    SpellDropDownMenu = {},
    InitializeSpellDropDown = function() nativeCalls = nativeCalls + 1 end
}
C_CharacterAdvancement = { GetEntryBySpellID = function(id) return {ID=id} end }
function event(...) frame:OnEvent(...) end
function packet(text, sender, channel) event("CHAT_MSG_ADDON", "A52CERT", text, channel or "WHISPER", sender or "Tester") end
function open(id)
    menu = {}
    CharacterAdvancement.SpellDropDownMenu.targetEntry = {ID=id, Name="Test ability"}
    CharacterAdvancement.SpellDropDownMenu.initialize(CharacterAdvancement.SpellDropDownMenu,1)
end
''')
lua.execute((Path(__file__).resolve().parents[1] /
             'client/Interface/AddOns/Area52MysticRules/TesterCertification.lua').read_text())
lua.execute(r'''
event("ADDON_LOADED")
event("PLAYER_LOGIN")
assert(#sent == 1 and sent[1][2] == "SYNC" and sent[1][3] == "WHISPER")
open(10); assert(#menu == 0 and nativeCalls == 1)
packet("BEGIN"); packet("V|10|11"); packet("C|12"); packet("END")
open(10); assert(#menu == 1 and not menu[1].disabled)
menu[1].func(); assert(popup.name == "Test ability")
assert(#sent == 1)
local confirmation = StaticPopupDialogs[popup.key]
assert(confirmation.button1 == "CERTIFY")
assert(confirmation.text:find("Persists through logout and login",1,true))
assert(confirmation.text:find("Is removed from bars if unlearned.",1,true))
confirmation.OnAccept(nil, popup.data)
assert(#sent == 2 and sent[2][2] == "C|10|7")
confirmation.OnAccept(nil,popup.data); assert(#sent == 2)
packet("C|11", "OtherPlayer"); open(11); assert(#menu == 1)
packet("C|11", "Tester", "GUILD"); open(11); assert(#menu == 1)
open(10); assert(menu[1].disabled)
packet("ERROR|Save failed"); open(10); assert(not menu[1].disabled)
menu[1].func(); confirmation.OnAccept(nil,popup.data)
packet("C|10"); packet("OK|10"); open(10); assert(#menu == 0)
local line = {value="Normal\n\nOriginal SHIFT\n\n|cffffff00VERIFIED|r", GetText=function(self) return self.value end, SetText=function(self,v) self.value=v end}
ModTooltipSetSpell.Area52Certification(nil,line,nil,10)
assert(line.value == "Normal\n\nOriginal SHIFT\n\n|cff00ff00CERTIFIED|r")
line.value = "NOT VERIFIED"; ModTooltipSetSpell.Area52Certification(nil,line,nil,10)
assert(line.value == "NOT VERIFIED")
open(99); assert(#menu == 0)
open(12); assert(#menu == 0)
picking = true; open(11); assert(#menu == 0); picking = false
hero = false; open(11); assert(#menu == 0); hero = true
realm = "Other realm"; open(11); assert(#menu == 0); realm = "Area 52 - Free-Pick"
open(11); menu[1].func(); confirmation.OnAccept(nil,popup.data)
timers[#timers](); open(11); assert(not menu[1].disabled)
packet("BEGIN"); open(11); assert(#menu == 0)
packet("C|10|11|12"); packet("END"); open(11); assert(#menu == 0)
''')
print('PASS: Lua 5.1 menu, confirmation/cancel, server acknowledgement, global sync, spoof rejection, timeout and exact SHIFT-text preservation')
