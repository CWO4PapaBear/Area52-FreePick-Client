from pathlib import Path
from lupa import LuaRuntime

source = Path(__file__).resolve().parents[1] / 'client/Interface/AddOns/Area52MysticRules/Area52MysticRules.lua'
lua = LuaRuntime()
lua.execute('''
realm = 'Area 52 - Free-Pick'; now = 10; sounds = 0; plays = 0
function GetRealmName() return realm end
function GetTime() return now end
function PlaySound(id) assert(id == 54128); sounds = sounds + 1 end
C_Player = {IsHero = function() return true end}
C_Config = {GetIntConfig = function(k) return k == 'CONFIG_MAX_RARE_RANDOM_ENCHANTS' and 17 or 4 end}
function CreateFrame() return {RegisterEvent=function() end, SetScript=function() end} end
C_Hook = {Register=function(_, ref, event, callback) resultCallback = callback end}
MysticEnchantManagerUtil = {
 GetActivePreset=function() return 1 end,
 UpdatePresetSlotMap=function(_, map) savedMap=map end
}
staged=true; accepted=true
EnchantCollectionUtil = {
 slotSettings={}, unknownEnchantColor={GetRGBA=function() return 1, 1, 1, 1 end},
 CanApplyQualityToSlot=function() return 'original' end,
 GetSlotMapForEnchants=function() return 'original' end,
 GetFakePositionMap=function() return 'original' end,
 GetSlotMapLayout=function() return 17 end,
 Init=function(self) self.slotMap=savedMap end,
 HasStagedChanges=function() return staged end,
 Apply=function() return accepted end
}
for i=1,17 do EnchantCollectionUtil.slotSettings[i]={} end
local function noop() end
local function animation()
 return setmetatable({SetScale=function(_, x, y) expansion=x; assert(x==y) end},
 {__index=function() return noop end})
end
local function texture()
 return setmetatable({CreateAnimationGroup=function()
  return {Stop=noop, Play=function() plays=plays+1 end, CreateAnimation=animation}
 end}, {__index=function() return noop end})
end
tab={slotIDToButton={},GetEffectiveScale=function() return 1 end,CreateTexture=texture}
for i=1,17 do
 local x = i == 1 and 0 or 200
 tab.slotIDToButton[i]={IsVisible=function() return true end,
 GetCenter=function() return x,0 end, GetEffectiveScale=function() return 1 end,
 GetWidth=function() return 80 end,GetHeight=function() return 80 end}
end
EnchantCollection={GetSlotTab=function() return tab end}
''')
lua.execute(source.read_text())
lua.execute('''
local u=EnchantCollectionUtil
for _, data in ipairs({{0,0,0,0,17}, {0,11,0,22}, {11,11,11}}) do
 local m=u:GetSlotMapForEnchants(data)
 for i=1,17 do assert(m[i]==i) end
end
savedMap={5,4,3,2,1};u:Init()
for i=1,17 do assert(u.slotMap[i]==i and savedMap[i]==i) end
for slot=1,17 do
 for quality=2,5 do
  if u:CanApplyQualityToSlot(slot,quality) then
   local data={}; for i=1,17 do data[i]=0 end; data[slot]=1000+quality
   for repeatIndex=1,3 do
    local map=u:GetSlotMapForEnchants(data)
    local preview=u:GetFakePositionMap(data)
    u:Init()
    for i=1,17 do assert(map[i]==i and preview[i]==i and u.slotMap[i]==i) end
   end
  end
 end
end
assert(u:CanApplyQualityToSlot(1,4))
assert(not u:CanApplyQualityToSlot(5,4))
resultCallback('RE_COLLECTION_REFORGE_OK'); assert(sounds==0)
u:Apply(); assert(sounds==0)
resultCallback('RE_COLLECTION_REFORGE_NO_MONEY'); assert(sounds==0)
u:Apply();resultCallback('RE_COLLECTION_REFORGE_OK')
assert(sounds==1 and plays==1 and expansion==6)
resultCallback('RE_COLLECTION_REFORGE_OK');assert(sounds==1)
accepted=false;u:Apply();resultCallback('RE_COLLECTION_REFORGE_OK');assert(sounds==1)
accepted=true;staged=false;u:Apply();resultCallback('RE_COLLECTION_REFORGE_OK');assert(sounds==1)
staged=true;u:Apply();now=41;resultCallback('RE_COLLECTION_REFORGE_OK');assert(sounds==1)
u:Apply();resultCallback(true,'RE_COLLECTION_REFORGE_OK');assert(sounds==2 and plays==2)
realm='Bear Cave PTR';u:Apply();resultCallback('RE_COLLECTION_REFORGE_OK');assert(sounds==2)
assert(u:GetSlotMapForEnchants({})=='original')
assert(u:GetFakePositionMap({})=='original')
assert(u:CanApplyQualityToSlot(1,5)=='original')
''')
print('PASS: fixed slots, saved-map normalization, capacity, commit success/failure/duplicates/timeout, wave bounds, realm gate')
