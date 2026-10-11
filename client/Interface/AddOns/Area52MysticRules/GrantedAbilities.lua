local M = { rows = {}, bySpell = {}, nativeCount = 0 }
Area52GrantedAbilities = M
local grantedMask = 1073741824

function M.Active()
    return GetRealmName() == "Area 52 - Free-Pick" and C_Player and C_Player:IsHero()
        and not (BuildCreatorUtil and BuildCreatorUtil.IsPickingSpells())
end

function M.Known(record)
    for i = #record.ranks, 1, -1 do
        local id = record.ranks[i]
        if IsSpellKnown(id) then return id end
    end
end

function M.CertificationID(record)
    return record.entry ~= 0 and record.entry or grantedMask + record.root
end

function M.SourceText(record)
    local result = {}
    for _, source in ipairs(record.sources) do
        local kind = source.kind == "mystic" and "Mystic Enchant" or "Ability or Talent"
        local entry = source.kind == "advancement" and C_CharacterAdvancement.GetEntryBySpellID(source.spell)
        if entry then kind = entry.Type == "Talent" and "Talent" or "Ability" end
        result[#result + 1] = "Learned from " .. kind .. ": " .. source.name
    end
    return table.concat(result, "\n")
end

function M.Matches(record, text, filter)
    local known = M.Known(record) ~= nil
    if filter.FILTER_KNOWN and not filter.FILTER_UNKNOWN and not known then return false end
    if filter.FILTER_UNKNOWN and not filter.FILTER_KNOWN and known then return false end
    if filter.FILTER_CAN_LEARN or filter.FILTER_CAN_UNLEARN or filter.FILTER_CAN_ADD
        or filter.FILTER_CAN_REMOVE then return false end
    if (filter.FILTER_TYPE_TALENT or filter.FILTER_TYPE_TRAIT) and not filter.FILTER_TYPE_ABILITY then return false end
    local class = C_CharacterAdvancement.GetClassInfo(record.root)
    class = (class or "GENERAL"):upper():gsub("DEATHKNIGHT", "DEATH_KNIGHT")
    local hasClass, matchesClass, hasQuality, normalQuality = false, false, false, false
    for key, value in pairs(filter) do
        if value and key:match("^FILTER_CLASS_") then
            hasClass = true
            matchesClass = matchesClass or key == "FILTER_CLASS_" .. class
        elseif value and key:match("^FILTER_QUALITY_") then
            hasQuality = true
            normalQuality = normalQuality or key == "FILTER_QUALITY_NORMAL"
        elseif value and key:match("^FILTER_SPELLTAG_") then
            return false
        end
    end
    if hasClass and not matchesClass or hasQuality and not normalQuality then return false end
    local name = GetSpellInfo(record.root) or record.name
    return text == "" or name:lower():find(text, 1, true) ~= nil
        or M.SourceText(record):lower():find(text, 1, true) ~= nil
end

function M.Rebuild(text, filter)
    M.rows = {}
    M.nativeCount = C_CharacterAdvancement.GetNumFilteredEntries()
    if not M.Active() then return end
    text, filter = (text or ""):lower(), filter or {}
    local present = {}
    for i = 1, M.nativeCount do
        local entry = C_CharacterAdvancement.GetFilteredEntryAtIndex(i)
        if entry then
            for _, id in ipairs(entry.Spells or {}) do
                local record = M.bySpell[id]
                if record then present[record.root] = true end
            end
        end
    end
    for _, record in ipairs(Area52GrantedAbilityCatalog or {}) do
        if not present[record.root] and M.Matches(record, text, filter) then
            M.rows[#M.rows + 1] = record
            present[record.root] = true
        end
    end
    table.sort(M.rows, function(a, b)
        local left, right = GetSpellInfo(a.root) or a.name, GetSpellInfo(b.root) or b.name
        return left == right and a.root < b.root or left < right
    end)
end

function M.Count()
    return C_CharacterAdvancement.GetNumFilteredEntries() + (M.Active() and #M.rows or 0)
end

function M.UpdateRow(button)
    if button.area52Grant then
        button.Icon:SetScript("OnDragStart", button.area52OriginalDrag)
    end
    button.area52Grant = nil
    if not M.Active() then return false end
    local record = M.rows[button.index - M.nativeCount]
    if not record then return false end
    button.area52Grant = record
    button.spellID = M.Known(record) or record.root
    button.known = M.Known(record) ~= nil
    button.rank, button.maxRank, button.cannotLearn, button.cannotUnlearn = nil, nil, nil, nil
    local name, rank, icon = GetSpellInfo(button.spellID)
    button.entry = {ID = M.CertificationID(record), Name = name or record.name, Spells = record.ranks,
        Area52Granted = true, Type = "Ability"}
    button:SetText((name or record.name) .. (rank and rank ~= "" and " (" .. rank .. ")" or ""))
    button.Text:SetTextColor(button.known and 1 or 0.5, button.known and 0.82 or 0.5, button.known and 0 or 0.5)
    button.Icon:SetIcon(icon)
    button.Icon:SetIconDesaturated(not button.known)
    button.Icon:SetIconColor(1, 1, 1)
    button.area52OriginalDrag = button.Icon:GetScript("OnDragStart")
    button.Icon.spellID = button.spellID
    button.Icon:SetScript("OnDragStart", function() if button.known then PickupSpell(button.spellID) end end)
    button.Icon:EnableDrag()
    for _, element in ipairs({button.Icon.Rank, button.Icon.RankBorder, button.TalentEssence,
        button.AbilityEssence, button.EssenceText, button.RarityGemText, button.ClassPoints, button.LockButton}) do
        element:Hide()
    end
    if button.Icon.RankUp then button.Icon.RankUp:Hide() end
    if button.Icon.PendingChange then button.Icon.PendingChange:Hide() end
    button.RarityGemContainer:SetNumGems(0, 0)
    button:UnlockHighlight()
    button:Collapse()
    button.ExpandedContent:Hide()
    if GameTooltip and GameTooltip:IsOwned(button) then button:OnEnter() end
    return true
end

function M.Click(button, mouse)
    if not button.area52Grant or not M.Active() then return false end
    CloseDropDownMenus()
    if IsModifiedClick("CHATLINK") then
        ChatEdit_InsertLink(LinkUtil:GetSpellLink(button.spellID))
    elseif mouse == "RightButton" then
        CharacterAdvancement:ShowSpellDropDownMenu(button, button:GetNormalTexture())
    end
    return true
end

function M.Dropdown(dropdown, level)
    if not M.Active() or not dropdown.targetEntry or not dropdown.targetEntry.Area52Granted then return false end
    if level and level ~= 1 then return true end
    local info = UIDropDownMenu_CreateInfo()
    info.text, info.isTitle, info.notCheckable = dropdown.targetEntry.Name, true, true
    UIDropDownMenu_AddButton(info, level)
    info = UIDropDownMenu_CreateInfo()
    info.text, info.disabled, info.notCheckable = "Granted by its source", true, true
    UIDropDownMenu_AddButton(info, level)
    return true
end

function M.Status(record)
    return Area52GetCertificationStatus and Area52GetCertificationStatus(M.CertificationID(record))
end

function M.Tooltip(tooltip, left, right, spellID)
    if not M.Active() or not IsShiftKeyDown() then return end
    local record = M.bySpell[spellID]
    if not record then return end
    local text = left:GetText()
    if not text or text:find("Learned from ", 1, true) then return end
    local tag = text:match("|c%x%x%x%x%x%x%x%xNOT VERIFIED|r")
        or text:match("|c%x%x%x%x%x%x%x%xVERIFIED|r") or text:match("|c%x%x%x%x%x%x%x%xCERTIFIED|r")
    if not tag then return end
    local state = M.Status(record)
    local label = state == "C" and "|cff00ff00CERTIFIED|r"
        or state == "V" and "|cffffff00VERIFIED|r" or "|cffff0000NOT VERIFIED|r"
    local start = text:find(tag, 1, true)
    local before = text:sub(1, start - 1):gsub("%s+$", "")
    local after = text:sub(start + #tag)
    left:SetText(before .. (before ~= "" and "\n\n" or "") .. M.SourceText(record) .. "\n\n" .. label .. after)
end

function M.AppendTooltip(tooltip, spellID)
    if not M.Active() then return end
    local record = M.bySpell[spellID]
    if not record then return end
    if not IsShiftKeyDown() then return end
    for i = 1, tooltip:NumLines() do
        local line = _G[tooltip:GetName() .. "TextLeft" .. i]
        if line and (line:GetText() or ""):find("Learned from ", 1, true) then return end
    end
    tooltip:AddLine(" ")
    tooltip:AddLine(M.SourceText(record), 1, 0.82, 0, true)
    tooltip:AddLine(" ")
    local state = M.Status(record)
    tooltip:AddLine(state == "C" and "|cff00ff00CERTIFIED|r"
        or state == "V" and "|cffffff00VERIFIED|r" or "|cffff0000NOT VERIFIED|r")
end

local frame = CreateFrame("Frame")
local refreshQueued
local function Install()
    for _, record in ipairs(Area52GrantedAbilityCatalog or {}) do
        for _, id in ipairs(record.ranks) do M.bySpell[id] = record end
    end
    if ModTooltipSetSpell then ModTooltipSetSpell.Area52GrantedSources = M.Tooltip end
end
frame:RegisterEvent("ADDON_LOADED")
frame:RegisterEvent("PLAYER_LOGIN")
frame:RegisterEvent("SPELLS_CHANGED")
frame:SetScript("OnEvent", function(_, event)
    Install()
    if event == "SPELLS_CHANGED" and M.Active() and not refreshQueued then
        refreshQueued = true
        C_Timer.After(0.1, function()
            refreshQueued = nil
            if CharacterAdvancement and CharacterAdvancement:IsShown() then CharacterAdvancement:Search() end
        end)
    end
end)
Install()

function Area52GrantedAbilities.CurrentSpell(id)
    local record = Area52GrantedAbilities.bySpell[id]
    if Area52GrantedAbilities.Active() and record then return Area52GrantedAbilities.Known(record) or id end
    return id
end
