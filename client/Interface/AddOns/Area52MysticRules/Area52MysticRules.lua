local function Active()
    local realm = GetRealmName()
    return (realm == "Area 52 - Free-Pick" or realm == "Area-52")
        and C_Player and C_Player:IsHero() and C_Config
        and C_Config.GetIntConfig("CONFIG_MAX_RARE_RANDOM_ENCHANTS") == 17
        and C_Config.GetIntConfig("CONFIG_MAX_EPIC_RANDOM_ENCHANTS") == 4
end

local function Capacity(slot)
    return slot == 1 and 5 or slot <= 4 and 4 or 3
end

local function IdentityMap()
    local ids = {}
    for i = 1, 17 do ids[i] = i end
    return ids
end

local function CommitFeedback()
    PlaySound(54128)
    local tab = EnchantCollection and EnchantCollection:GetSlotTab()
    local center = tab and tab.slotIDToButton and tab.slotIDToButton[1]
    if not center or not center:IsVisible() then return end
    local cx, cy = center:GetCenter()
    if not cx then return end
    local scale = center:GetEffectiveScale()
    cx, cy = cx * scale, cy * scale
    local radius = 0
    for _, slot in pairs(tab.slotIDToButton) do
        if slot:IsVisible() then
            local x, y = slot:GetCenter()
            if x then
                local s = slot:GetEffectiveScale()
                local dx, dy = x * s - cx, y * s - cy
                radius = math.max(radius, math.sqrt(dx * dx + dy * dy)
                    + math.max(slot:GetWidth(), slot:GetHeight()) * s / 2)
            end
        end
    end
    local wave = tab.area52CommitWave
    if not wave then
        wave = tab:CreateTexture(nil, "OVERLAY")
        wave:SetTexture("SPELLS\\7fx_alphamask_shockwavesoft_contrast_256")
        wave:SetBlendMode("ADD")
        wave:SetVertexColor(EnchantCollectionUtil.unknownEnchantColor:GetRGBA())
        wave:SetAlpha(0)
        wave.anim = wave:CreateAnimationGroup()
        local appear = wave.anim:CreateAnimation("Alpha")
        appear:SetDuration(0.2)
        appear:SetChange(1)
        appear:SetOrder(1)
        wave.expand = wave.anim:CreateAnimation("Scale")
        wave.expand:SetDuration(1)
        wave.expand:SetSmoothing("OUT")
        wave.expand:SetOrder(1)
        local rotate = wave.anim:CreateAnimation("Rotation")
        rotate:SetDuration(1)
        rotate:SetDegrees(-90)
        rotate:SetOrder(1)
        local fade = wave.anim:CreateAnimation("Alpha")
        fade:SetStartDelay(0.4)
        fade:SetDuration(0.6)
        fade:SetChange(-1)
        fade:SetOrder(1)
        tab.area52CommitWave = wave
    end
    wave.anim:Stop()
    wave:ClearAllPoints()
    wave:SetPoint("CENTER", center, "CENTER")
    wave:SetSize(80, 80)
    local expansion = math.max(1, radius * 2 / tab:GetEffectiveScale() / 80)
    wave.expand:SetScale(expansion, expansion)
    wave.anim:Play()
end

local installed = false
local function Install()
    if installed or not EnchantCollectionUtil or not C_Hook then return end
    installed = true
    local util = EnchantCollectionUtil
    local previousCanApply = util.CanApplyQualityToSlot
    function util:CanApplyQualityToSlot(slot, quality)
        if not Active() then return previousCanApply(self, slot, quality) end
        return slot >= 1 and slot <= 17 and quality >= 2 and quality <= Capacity(slot)
            and self.slotSettings[slot] and not self.slotSettings[slot].hidden
    end

    local previousMap = util.GetSlotMapForEnchants
    function util:GetSlotMapForEnchants(data)
        if not Active() then return previousMap(self, data) end
        return IdentityMap()
    end

    local previousFake = util.GetFakePositionMap
    function util:GetFakePositionMap(data)
        if Active() then return self:GetSlotMapForEnchants(data) end
        return previousFake(self, data)
    end

    local previousInit = util.Init
    function util:Init(...)
        if Active() then
            self.slotMap = IdentityMap()
            MysticEnchantManagerUtil.UpdatePresetSlotMap(MysticEnchantManagerUtil.GetActivePreset(),
                IdentityMap(), self:GetSlotMapLayout())
        end
        return previousInit(self, ...)
    end

    local pending
    local previousApply = util.Apply
    function util:Apply(...)
        if Active() and self:HasStagedChanges() then
            pending = GetTime()
        end
        local result = previousApply(self, ...)
        if not result then pending = nil end
        return result
    end
    local function OnResult(first, second)
        local started = pending
        pending = nil
        if not started or not Active() or GetTime() - started > 30 then return end
        if first == "RE_COLLECTION_REFORGE_OK" or second == "RE_COLLECTION_REFORGE_OK" then
            CommitFeedback()
        end
    end
    C_Hook:Register({}, "MYSTIC_ENCHANT_COLLECTION_REFORGE_RESULT", OnResult)
end

local frame = CreateFrame("Frame")
frame:RegisterEvent("ADDON_LOADED")
frame:SetScript("OnEvent", Install)
Install()
