"use strict";

const UE = require("ue");
const puerts = require("puerts");

const OUTFIT = "pbz_outfit_baiqi";
const ACTION = "/SGameCombatSystem/Weapon/Action/GAA_PlaySound_Opt.GAA_PlaySound_Opt_C";
const SOURCE_ROOT = "/game/wwise/events/vo/int/hun/battle/";
const TARGET_ROOT = "/Game/Wwise/Events/SFX/Combat/VO/Monster_Vo/BaiChiLian/";
// Stock Bai Chilian recordings, using the same combat voice source as QOutlaw's playable character.
const ROUTES = {
    BaiChiLian_Attack_BiXian: [1339064079, [
        "Attack_Short", "ChuZhao_01_DuanCu", "ShouZhao_DoubleBlade", "ShouZhao_LongBlade", "ShouZhao_TangBlade",
        "Charge_Release_Light",
    ]],
    BaiChiLian_Attack_Heavy_BiXian: [3362275343, [
        "ChuZhao_02", "Charge_Release_Heavy", "Execute_Attack_Heavy", "Heavy_Release", "ZhongZhuan", "ZhongZhuan_01",
    ]],
    BaiChiLian_Charge: [2254013653, [
        "Charge_Short", "Charge_Long", "Charge_Heavy_Short", "Charge_Heavy_Long", "Charge_SuperLong",
        "BiQi_01_DuanCu", "BiQi_02_Long",
    ]],
    BaiChiLian_Battle_Hurt: [44283577, ["Hurt", "Hurt_BiXian"]],
    BaiChiLianP2_Hurt: [2357963452, ["Hurt_Heavy", "Hurt_Heavy_Mix", "Break", "Weapon_Break"]],
};
const prefix = "[BaiQiVoice]";
const valid = value => Boolean(value && UE.KismetSystemLibrary.IsValid(value));
const globalSlot = Symbol.for("PBZ.BaiQi.CombatVoice");

const evidence = [];
function log(message) {
    const line = prefix + " " + message;
    console.warn(line);
    evidence.push(line);
    if (evidence.length > 64) evidence.shift();
    if (UE.BlueprintPathsLibrary && UE.EasyCsv) {
        try {
            const saved = UE.BlueprintPathsLibrary.ConvertRelativePathToFull(
                UE.BlueprintPathsLibrary.ProjectSavedDir(), "");
            UE.EasyCsv.SaveStringToFileWithFullPath(evidence.join("\n") + "\n", saved + "BaiQiVoice.log");
        } catch (_) {}
    }
}

function loadEvents() {
    const sources = new Map();
    for (const [target, [id, sourceNames]] of Object.entries(ROUTES)) {
        const name = "SFX_Combat_VO_" + target;
        const path = TARGET_ROOT + name + "." + name;
        try {
            const event = UE.Object.Load(path);
            if (!valid(event) || (event.GetWwiseShortID() >>> 0) !== id) {
                throw new Error("audio event ID mismatch");
            }
            event.LoadData();
            for (const source of sourceNames) {
                const stem = "sfx_combat_vo_hun_" + source.toLowerCase();
                sources.set(SOURCE_ROOT + stem + "." + stem, { event, name });
            }
            log("MEDIA " + name + " " + id);
        } catch (error) {
            log("MEDIA_UNAVAILABLE " + name + " " + String(error));
        }
    }
    return sources;
}

function outfitFor(actor) {
    const context = puerts.argv.getByName("GameInstance");
    if (!valid(context) || actor !== UE.GameplayStatics.GetPlayerPawn(context, 0)) return "";
    const appearance = UE.PBZAppearanceComponent.GetPBZAppearanceComponent(actor);
    return valid(appearance) ? String(appearance.GetCurrentOutfit()).toLowerCase() : "";
}

function install() {
    // Keep one Blueprint binding per game process, including during loader hot reload.
    let binding = globalThis[globalSlot];
    if (!binding) {
        const actionClass = UE.Class.Load(ACTION);
        if (!valid(actionClass)) throw new Error("BaiQi combat audio action is unavailable");
        const original = UE.LGAAction_PlaySoundDefault.prototype.OnPrePostEvent;
        if (typeof original !== "function") throw new Error("BaiQi combat audio original filter is unavailable");
        binding = {
            route: undefined,
            end: puerts.toManualReleaseDelegate(() => {}),
        };
        let observed = false;
        class CombatVoice {
            OnPrePostEvent(component, actor) {
                if (binding.route && !observed) {
                    observed = true;
                    log("COMBAT_ACTION_ENTERED");
                }
                let allowed;
                try {
                    allowed = original.call(this, component, actor);
                } catch (error) {
                    if (binding.route) log("ORIGINAL_FAILED " + String(error));
                    binding.route = undefined;
                    return true;
                }
                if (allowed !== true || !binding.route || this.GetClass() !== actionClass) return allowed;
                return binding.route(this, component, actor);
            }
        }
        puerts.blueprint.mixin(puerts.blueprint.tojs(actionClass), CombatVoice,
            { inherit: false, objectTakeByNative: true });
        globalThis[globalSlot] = binding;
    }

    const sources = loadEvents();
    if (!sources.size) throw new Error("BaiQi combat voice could not load any source route");
    const reported = new Set();
    function reportOnce(key, message) {
        if (reported.has(key)) return;
        log(message);
        reported.add(key);
    }

    binding.route = (action, component, actor) => {
        try {
            if (!valid(actor) || !valid(component) || !valid(action.AkEvent)) return true;
            const path = String(UE.KismetSystemLibrary.GetPathName(action.AkEvent)).toLowerCase();
            if (!path.startsWith(SOURCE_ROOT)) return true;
            const target = sources.get(path);
            const outfit = outfitFor(actor);
            if (outfit !== OUTFIT) {
                if (outfit && target) reportOnce("stock", "ORIGINAL " + outfit);
                return true;
            }
            if (!target || action.GetAvatarActor() !== actor) {
                reportOnce(path, "UNMAPPED " + path.split("/").pop());
                return true;
            }
            const sound = UE.SubsystemBlueprintLibrary.GetWorldSubsystem(actor, UE.PBZSoundFXSubsystem.StaticClass());
            if (!valid(sound) || !valid(target.event)) return true;
            const playing = sound.PBZPostEventOnAkComponent(target.event, component, binding.end, true, false, 0);
            if (!Number.isInteger(playing) || playing === 0) {
                reportOnce("failed:" + target.name, "POST_FAILED " + target.name);
                return true;
            }
            reportOnce(path, "ROUTED " + path.split("/").pop() + " " + target.name + " " + (playing >>> 0));
            return false;
        } catch (error) {
            reportOnce("route-error", "ROUTE_ERROR " + String(error));
            return true;
        }
    };
    log("READY " + OUTFIT + " sources=" + sources.size);
    const context = puerts.argv.getByName("GameInstance");
    const pawn = valid(context) && UE.GameplayStatics.GetPlayerPawn(context, 0);
    if (valid(pawn)) log("ACTIVE_OUTFIT " + outfitFor(pawn));
    return binding;
}

let binding;
try {
    binding = install();
} catch (error) {
    log("VOICE_SETUP_FAILED " + String(error));
}
const stopPreview = require("./preview").monitor(log);
exports.stop = function stop() {
    if (binding) binding.route = undefined;
    stopPreview();
};
