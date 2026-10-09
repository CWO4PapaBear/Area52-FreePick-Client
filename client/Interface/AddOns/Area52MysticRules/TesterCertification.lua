local prefix = "A52CERT"
local status = {}
local receiving
local ready = false
local pending
local frame = CreateFrame("Frame")

local function Active()
    return GetRealmName() == "Area 52 - Free-Pick" and C_Player and C_Player:IsHero()
end

local function Print(message)
    DEFAULT_CHAT_FRAME:AddMessage("|cff00ccffArea 52:|r " .. message)
end

local function Send(message)
    if Active() then
        SendAddonMessage(prefix, message, "WHISPER", UnitName("player"))
    end
end

StaticPopupDialogs["AREA52_CERTIFY_ABILITY"] = {
    text = "%s\n\nHave you confirmed that this ability:\n\n1. Functions as expected\n2. Persists through logout and login\n3. Is removed from bars if unlearned.",
    button1 = "CERTIFY",
    button2 = CANCEL,
    timeout = 0,
    whileDead = true,
    hideOnEscape = true,
    preferredIndex = 3,
    OnAccept = function(self, data)
        if not data or not ready or status[data.id] ~= "V" or pending then return end
        pending = { id = data.id, sent = GetTime() }
        local request = pending
        Send("C|" .. data.id .. "|7")
        Print("Saving certification...")
        C_Timer.After(15, function()
            if pending == request then
                pending = nil
                Print("No certification response received. Please try again.")
            end
        end)
    end,
}

local function AddCertification(self, dropdown, level)
    if not Active() or not ready or level and level ~= 1 then return end
    if BuildCreatorUtil and BuildCreatorUtil.IsPickingSpells() then return end
    local entry = dropdown.targetEntry
    if not entry or status[entry.ID] ~= "V" then return end
    local id, name = entry.ID, entry.Name
    local info = UIDropDownMenu_CreateInfo()
    info.notCheckable = true
    info.text = "Mark as |cff00ff00CERTIFIED|r"
    info.disabled = pending ~= nil
    info.func = function()
        CloseDropDownMenus()
        StaticPopup_Show("AREA52_CERTIFY_ABILITY", name, nil, { id = id })
    end
    UIDropDownMenu_AddButton(info, level)
end

local function InstallMenu()
    if CharacterAdvancement and not CharacterAdvancement.area52CertificationMenu then
        CharacterAdvancement.area52CertificationMenu = true
        hooksecurefunc(CharacterAdvancement, "InitializeSpellDropDown", AddCertification)
        UIDropDownMenu_Initialize(CharacterAdvancement.SpellDropDownMenu, function(...)
            CharacterAdvancement:InitializeSpellDropDown(...)
        end, "MENU")
    end
end

local function ReplaceStatus(tooltip, left, right, spellID)
    if not Active() or not ready or not C_CharacterAdvancement then return end
    local entry = C_CharacterAdvancement.GetEntryBySpellID(spellID)
    if not entry or status[entry.ID] ~= "C" then return end
    local text = left:GetText()
    if text then
        local updated = text:gsub("|c[fF][fF][fF][fF][fF][fF]00VERIFIED|r", "|cff00ff00CERTIFIED|r")
        if updated ~= text then left:SetText(updated) end
    end
end

local function InstallTooltip()
    if ModTooltipSetSpell and not ModTooltipSetSpell.Area52Certification then
        ModTooltipSetSpell.Area52Certification = ReplaceStatus
    end
end

frame:RegisterEvent("PLAYER_LOGIN")
frame:RegisterEvent("ADDON_LOADED")
frame:RegisterEvent("CHAT_MSG_ADDON")
frame:SetScript("OnEvent", function(self, event, incomingPrefix, message, channel, sender)
    if event == "ADDON_LOADED" then
        InstallMenu()
        InstallTooltip()
    elseif event == "PLAYER_LOGIN" then
        InstallMenu()
        InstallTooltip()
        Send("SYNC")
    elseif incomingPrefix == prefix and channel == "WHISPER" and sender == UnitName("player") and Active() then
        if message == "BEGIN" then
            receiving = {}
            ready = false
        elseif message == "END" and receiving then
            status = receiving
            receiving = nil
            ready = true
        elseif message:match("^[VC]|") then
            local target = receiving or status
            local value = message:sub(1, 1)
            for id in message:gmatch("|(%d+)") do target[tonumber(id)] = value end
        elseif message:match("^OK|") then
            local id = tonumber(message:sub(4))
            status[id] = "C"
            if pending and pending.id == id then
                pending = nil
                Print("|cff00ff00CERTIFIED|r — thank you for testing. Updated for everyone.")
            end
        elseif message:match("^ERROR|") then
            pending = nil
            Print(message:sub(7))
        end
    end
end)
