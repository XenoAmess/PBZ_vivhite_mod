"use strict";

const UE = require("ue");
const puerts = require("puerts");

const OUTFIT = "pbz_outfit_baiqi";
const ACTION = "/SGameCombatSystem/Weapon/Action/GAA_PlaySound_Opt.GAA_PlaySound_Opt_C";
const SOURCE_ROOT = "/game/wwise/events/vo/int/hun/battle/";
const TARGET_ROOT = "/Game/Wwise/Events/VO/Int/Eve/BaiQiX/";
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

function isChineseVoice() {
    const language = String(UE.AkGameplayStatics.GetCurrentAudioCulture()).trim().toLowerCase();
    return language.startsWith("chinese") || language === "mandarin" || /^zh(?:[-_]|$)/.test(language);
}

function outfitFor(actor) {
    const context = puerts.argv.getByName("GameInstance");
    if (!valid(context) || actor !== UE.GameplayStatics.GetPlayerPawn(context, 0)) return "";
    const appearance = UE.PBZAppearanceComponent.GetPBZAppearanceComponent(actor);
    return valid(appearance) ? String(appearance.GetCurrentOutfit()).toLowerCase() : "";
}

function install() {
    const routes = require("./eve-combat-data");
    const sources = new Map();
    for (const [stem, target] of Object.entries(routes)) {
        const path = target.object;
        if (!/^sfx_combat_vo_hun_[a-z0-9_]+$/.test(stem) || !Number.isInteger(target.id) ||
            !(target.id > 0 && target.id <= 0xffffffff) || typeof path !== "string" ||
            path.toLowerCase() !== TARGET_ROOT.toLowerCase() + stem + "." + stem) {
            throw new Error("Invalid EVE combat event table");
        }
        sources.set(SOURCE_ROOT + stem + "." + stem, target);
    }
    if (!sources.size) throw new Error("Empty EVE combat event table");
    // Keep one Blueprint binding per game process, including during loader hot reload.
    let binding = globalThis[globalSlot];
    if (!binding) {
        const actionClass = UE.Class.Load(ACTION);
        if (!valid(actionClass)) throw new Error("BaiQi combat audio action is unavailable");
        const original = UE.LGAAction_PlaySoundDefault.prototype.OnPrePostEvent;
        if (typeof original !== "function") throw new Error("BaiQi combat audio original filter is unavailable");
        binding = { route: undefined, ended: undefined };
        binding.callback = puerts.toManualReleaseDelegate((type, info) => {
            if (type === UE.EAkCallbackType.EndOfEvent && valid(info) && binding.ended) binding.ended(info.PlayingID);
        });
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

    const reported = new Set();
    const cache = new Map();
    let current;
    let watchdog;

    function clearClip(stop) {
        const previous = current;
        current = undefined;
        if (watchdog !== undefined) {
            clearInterval(watchdog);
            watchdog = undefined;
        }
        if (stop && previous && valid(previous.sound)) previous.sound.PBZStopPlayingID(previous.id, 0.05);
    }
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
            if (!isChineseVoice()) return true;
            let event = cache.get(target.id);
            if (!valid(event)) {
                reportOnce("load:" + target.id, "LOAD_EVENT " + target.object);
                event = UE.Object.Load(target.object);
                if (!valid(event) || (event.GetWwiseShortID() >>> 0) !== target.id) {
                    reportOnce("missing:" + target.id, "MEDIA_UNAVAILABLE " + target.object);
                    return true;
                }
                reportOnce("found:" + target.id, "EVENT_RESOLVED " + target.id);
                event.LoadData();
                cache.set(target.id, event);
            }
            const sound = UE.SubsystemBlueprintLibrary.GetWorldSubsystem(actor, UE.PBZSoundFXSubsystem.StaticClass());
            if (!valid(sound)) return true;
            const id = sound.PBZPostEventOnAkComponent(event, component, binding.callback, true, false, 0);
            if (!Number.isInteger(id) || !id) {
                reportOnce("failed:" + target.id, "POST_FAILED " + target.object);
                return true;
            }
            clearClip(true);
            current = { owner: actor, id, sound, until: Date.now() + 6000 };
            watchdog = setInterval(() => {
                if (current && (outfitFor(current.owner) !== OUTFIT || !isChineseVoice())) {
                    clearClip(true);
                } else if (current && Date.now() >= current.until) {
                    clearClip(false);
                }
            }, 180);
            reportOnce(path, "EVE_ROUTED " + path.split("/").pop() + " " + (id >>> 0));
            return false;
        } catch (error) {
            reportOnce("route-error", "ROUTE_ERROR " + String(error));
            return true;
        }
    };
    binding.ended = id => {
        if (current && (id >>> 0) === (current.id >>> 0)) clearClip(false);
    };
    log("EVE_READY " + OUTFIT + " sources=" + sources.size + " language=Chinese");
    const context = puerts.argv.getByName("GameInstance");
    const pawn = valid(context) && UE.GameplayStatics.GetPlayerPawn(context, 0);
    if (valid(pawn)) log("ACTIVE_OUTFIT " + outfitFor(pawn));
    return () => {
        binding.route = undefined;
        binding.ended = undefined;
        clearClip(true);
        cache.clear();
    };
}

let stopVoice;
try {
    stopVoice = install();
} catch (error) {
    log("VOICE_SETUP_FAILED " + String(error));
}
const stopPreview = require("./preview").monitor(log);
exports.stop = function stop() {
    if (stopVoice) stopVoice();
    stopPreview();
};
