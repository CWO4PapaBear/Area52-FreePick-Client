from pathlib import Path
import unittest
from lupa.lua51 import LuaRuntime

SOURCE=Path(__file__).resolve().parents[1]/'client/Interface/AddOns/Area52MysticRules/TesterCertification.lua'

class LeaderboardTests(unittest.TestCase):
    def test_hover_minimize_restore_and_saved_preference(self):
        lua=LuaRuntime()
        lua.execute('''
SlashCmdList={}; C_Player={IsHero=function() return true end}; UIParent={}
C_Timer={After=function() end}; hovered=false
function GetRealmName() return "Area 52 - Free-Pick" end
function UnitName() return "Tester" end
function SendAddonMessage() end
function MouseIsOver() return hovered end
local methods={}
function methods:SetScript(k,v) self.scripts[k]=v end
function methods:SetSize(w,h) self.width=w;self.height=h end
function methods:SetBackdropColor(r,g,b,a) self.alpha=a end
function methods:GetRegions() return unpack(self.regions) end
function methods:GetChildren() return unpack(self.children) end
function methods:GetObjectType() return self.kind end
function methods:Show() self.shown=true end
function methods:Hide() self.shown=false end
function methods:Click() self.scripts.OnClick(self) end
function methods:CreateTexture() local r=CreateFrame("Texture");table.insert(self.regions,r);return r end
function methods:CreateFontString() local r=CreateFrame("FontString");table.insert(self.regions,r);return r end
setmetatable(methods,{__index=function(_,key) if key:match("^[A-Z]") then return function() end end end})
function CreateFrame(kind,name,parent)
 local f=setmetatable({kind=kind,scripts={},regions={},children={},shown=true},{__index=methods})
 if parent and parent.children then table.insert(parent.children,f) end
 if name then _G[name]=f end
 return f
end
GameTooltip=CreateFrame("Tooltip")
''')
        lua.execute(SOURCE.read_text().split('StaticPopupDialogs["AREA52_CERTIFY_ABILITY"]')[0])
        lua.execute('''
Area52LeaderboardMinimized=true
SlashCmdList.AREA52CERTLEADERBOARD()
local b=Area52CertificationLeaderboard
local icon=b.children[1]
assert(b.width==56 and b.minimized and Area52LeaderboardMinimized)
assert(icon.shown and not b.rows[1].name.shown and not b.children[2].shown)
b.scripts.OnUpdate(b,0.11);assert(b.alpha==0.25)
hovered=true;b.scripts.OnUpdate(b,0.11);assert(b.alpha==1)
hovered=false;b.scripts.OnUpdate(b,0.11);assert(b.alpha==0.25)
icon:Click();assert(b.width==245 and b.height==365 and not Area52LeaderboardMinimized)
assert(b.rows[1].name.shown and b.children[2].shown and b.divider.shown)
icon:Click();SlashCmdList.AREA52CERTLEADERBOARD()
assert(b.minimized and b.width==56 and not b.divider.shown)
''')

if __name__=='__main__':unittest.main()
