Area52RuneResets = {}
local rules = Area52RuneResets
local ca = C_CharacterAdvancement

function rules.Enabled()
    return C_Config.GetBoolConfig("CONFIG_AREA52_FLAT_RUNE_RESETS") == true
        and C_Player:IsHero() and not C_GameMode:IsGameModeActive(Enum.GameMode.WildCard)
end

local function Cost(ids)
    if type(ids) ~= "table" then return 250 end
    local seen, count = {}, 0
    for _, id in ipairs(ids) do
        if not seen[id] then seen[id] = true; count = count + 1 end
    end
    return 250 * count
end

local function HasRunes(amount)
    return GetItemCount(375250) >= amount
end

local originalCanUnlearn = ca.CanUnlearnID
function ca.CanUnlearnID(ids, ...)
    if not rules.Enabled() then return originalCanUnlearn(ids, ...) end
    local ok, reason, entry = originalCanUnlearn(ids, ...)
    if not ok then return ok, reason, entry end
    if not HasRunes(Cost(ids)) then return false, "CA_UNLEARN_NO_UNLEARN_ITEM", type(ids) == "number" and ids or 0 end
    return ok, reason, entry
end

local originalConfirmUnlearn = ca.ShouldConfirmUnlearnID
function ca.ShouldConfirmUnlearnID(ids, ...)
    if not rules.Enabled() then return originalConfirmUnlearn(ids, ...) end
    local _, old = originalConfirmUnlearn(ids, ...)
    local reasons = {}
    for _, reason in ipairs(old or {}) do
        if reason.Error == Enum.CAConfirmReason.RemovesMastery or reason.Error == Enum.CAConfirmReason.IncludesMastery then
            reasons[#reasons + 1] = reason
        end
    end
    reasons[#reasons + 1] = {Error = Enum.CAConfirmReason.Marks, Arg1 = Cost(ids), Arg2 = 0}
    return true, reasons
end

local originalUnlearn = ca.UnlearnID
function ca.UnlearnID(ids, ...)
    if rules.Enabled() and not ca.CanUnlearnID(ids) then return false end
    return originalUnlearn(ids, ...)
end

local function BindReset(talents)
    local suffix = talents and "Talents" or "Spells"
    local prefix = talents and "CA_PURGE_TALENTS_" or "CA_PURGE_ABILITIES_"
    local originalCheck = ca["CanUnlearnAll" .. suffix]
    local originalReset = ca["UnlearnAll" .. suffix]
    ca["CanUnlearnAll" .. suffix] = function(...)
        if not rules.Enabled() then return originalCheck(...) end
        local ok, reason = originalCheck(...)
        if not ok and reason ~= prefix .. "NO_PURGE_ITEM" then return ok, reason end
        if UnitIsDeadOrGhost("player") then return false, "CA_LEARN_NOT_WHILE_DEAD" end
        if UnitAffectingCombat("player") then return false, prefix .. "NOT_IN_COMBAT" end
        local spent = talents and ca.GetLearnedTE() or ca.GetLearnedAE()
        if not spent or spent == 0 then
            return false, prefix .. (talents and "NO_KNOWN_TALENTS" or "NO_KNOWN_ABILITIES")
        end
        if not HasRunes(250) then return false, prefix .. "NO_PURGE_ITEM" end
        return true, prefix .. "OK"
    end
    ca["UnlearnAll" .. suffix] = function(...)
        if rules.Enabled() and not ca["CanUnlearnAll" .. suffix]() then return false end
        return originalReset(...)
    end
    local originalConfirm = CharacterAdvancementUtil["ConfirmOrUnlearnAll" .. suffix]
    CharacterAdvancementUtil["ConfirmOrUnlearnAll" .. suffix] = function(...)
        if not rules.Enabled() then return originalConfirm(...) end
        local ok, reason = ca["CanUnlearnAll" .. suffix]()
        if not ok then UIErrorsFrame:AddMessage(_G[reason] or reason, 1, 0, 0); return false end
        local warning = "\nCost: 250 Runes of Ascension.\n\nThis will deactivate your Active Build and turn off automatic learning. Your saved build will remain in the library."
        if C_GameMode:IsGameModeActive(Enum.GameMode.BuildDraft) and UnitLevel("player") > 10 then
            warning = warning .. "\n\nLeaving DRAFT BUILD mode forfeits its max-level reward: Mystic Enchants added to your collection."
        end
        StaticPopup_Show("CONFIRM_UNLEARN_ALL_S", talents and TALENTS or ABILITIES, warning, ca["UnlearnAll" .. suffix])
        return true
    end
end
BindReset(false)
BindReset(true)
