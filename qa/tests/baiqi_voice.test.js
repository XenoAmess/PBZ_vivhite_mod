"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");

const script = "(function (require, exports) {" +
    fs.readFileSync(path.join(__dirname, "../../mods/baiqi-voice/main.js"), "utf8") +
    "\n})(require, exports)";

test("EVE audio plays only for mapped Chinese combat events on local BaiQi", () => {
    const player = {};
    const npc = {};
    const actionClass = {};
    const posts = [];
    let outfit = "PBZ_OutFit_BaiQi";
    let originalAllowed = true;
    let playSucceeded = true;
    let language = "Chinese";
    let stops = 0;
    let watchdog;
    let mixinCount = 0;
    let installed;
    const ue = {
        Class: { Load: () => actionClass },
        KismetSystemLibrary: { IsValid: Boolean, GetPathName: asset => asset.path },
        GameplayStatics: { GetPlayerPawn: () => player },
        PBZAppearanceComponent: { GetPBZAppearanceComponent: () => ({ GetCurrentOutfit: () => outfit }) },
        PBZSoundFXSubsystem: { StaticClass: () => ({}) },
        SubsystemBlueprintLibrary: { GetWorldSubsystem: () => ({
            PBZPostEventOnAkComponent: event => {
                posts.push(event.path);
                return playSucceeded ? 16 + posts.length : 0;
            },
            PBZStopPlayingID: () => { stops += 1; },
        }) },
        AkGameplayStatics: { GetCurrentAudioCulture: () => language },
        EAkCallbackType: { EndOfEvent: 1 },
        LGAAction_PlaySoundDefault: class { OnPrePostEvent() { return originalAllowed; } },
        Object: { Load: path => ({ path, LoadData() {}, GetWwiseShortID: () => path.includes("Heavy") ? 2 : 1 }) },
    };
    const puerts = {
        argv: { getByName: () => ({}) },
        blueprint: { tojs: cls => cls, mixin: (_, cls) => { installed = cls; mixinCount += 1; } },
        toManualReleaseDelegate: callback => callback,
    };
    const light = "SFX_Combat_VO_Hun_Attack_Short";
    const heavy = "SFX_Combat_VO_Hun_Heavy_Release";
    const bank = "/Game/Wwise/Events/VO/Int/Eve/BaiQiX/";
    const data = {
        sfx_combat_vo_hun_attack_short: { object: bank + light + "." + light, id: 1 },
        sfx_combat_vo_hun_heavy_release: { object: bank + heavy + "." + heavy, id: 2 },
    };
    const context = vm.createContext({ exports: {}, console: { log() {}, warn() {} },
        setInterval: callback => { watchdog = callback; return 1; },
        clearInterval: () => { watchdog = undefined; },
        require: id => ({ ue, puerts, "./preview": { monitor: () => () => {} }, "./eve-combat-data": data })[id] });
    vm.runInContext(script, context);
    const action = new installed();
    action.GetClass = () => actionClass;
    function play(source, actor = player, root = "/Game/Wwise/Events/VO/Int/Hun/Battle/") {
        action.GetAvatarActor = () => actor;
        action.AkEvent = { path: root + source + "." + source };
        return action.OnPrePostEvent({}, actor);
    }
    const attack = "SFX_Combat_VO_Hun_Attack_Short";
    assert.equal(play(attack), false);
    assert.ok(posts.at(-1).endsWith(light + "." + light));
    assert.equal(play("SFX_Combat_VO_Hun_Heavy_Release"), false);
    assert.ok(posts.at(-1).endsWith(heavy + "." + heavy));
    assert.equal(stops, 1);
    assert.equal(play(attack, npc), true);
    assert.equal(play("Opening_Line"), true);
    assert.equal(play(attack, player, "/Game/Other/"), true);
    outfit = "Hun_MoTian";
    assert.equal(play(attack), true);
    watchdog();
    assert.equal(stops, 2);
    assert.equal(watchdog, undefined);
    assert.equal(posts.length, 2);
    outfit = "PBZ_OutFit_BaiQi";
    originalAllowed = false;
    assert.equal(play(attack), false);
    assert.equal(posts.length, 2);
    originalAllowed = true;
    language = "English(US)";
    assert.equal(play(attack), true);
    assert.equal(posts.length, 2);
    language = "zh_CN";
    playSucceeded = false;
    assert.equal(play(attack), true);
    playSucceeded = true;
    context.exports.stop();
    assert.equal(play(attack), true);
    context.exports = {};
    vm.runInContext(script, context);
    assert.equal(mixinCount, 1);
    assert.equal(play(attack), false);
    assert.equal(posts.length, 4);
});
