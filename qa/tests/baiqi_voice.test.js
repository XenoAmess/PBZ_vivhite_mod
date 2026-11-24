"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");

const script = "(function (require, exports) {" +
    fs.readFileSync(path.join(__dirname, "../../mods/baiqi-voice/main.js"), "utf8") +
    "\n})(require, exports)";

test("BaiQi only redirects mapped combat audio for the local player", () => {
    const player = {};
    const npc = {};
    const actionClass = {};
    const posts = [];
    let outfit = "PBZ_OutFit_BaiQi";
    let originalAllowed = true;
    let playing = 12;
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
                return playing;
            },
        }) },
        LGAAction_PlaySoundDefault: class { OnPrePostEvent() { return originalAllowed; } },
        Object: { Load: path => ({ path, LoadData() {}, GetWwiseShortID: () => {
            const name = path.split(".SFX_Combat_VO_")[1];
            return { BaiChiLian_Attack_BiXian: 1339064079, BaiChiLian_Attack_Heavy_BiXian: 3362275343,
                BaiChiLian_Charge: 2254013653, BaiChiLian_Battle_Hurt: 44283577, BaiChiLianP2_Hurt: 2357963452 }[name];
        } }) },
    };
    const puerts = {
        argv: { getByName: () => ({}) },
        blueprint: { tojs: cls => cls, mixin: (_, cls) => { installed = cls; mixinCount += 1; } },
        toManualReleaseDelegate: callback => callback,
    };
    const context = vm.createContext({ exports: {}, console: { log() {}, warn() {} },
        require: id => ({ ue, puerts, "./preview": { monitor: () => () => {} } })[id] });
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
    assert.match(posts.at(-1), /BaiChiLian_Attack_BiXian\.SFX_Combat_VO_BaiChiLian_Attack_BiXian$/);
    assert.equal(play("SFX_Combat_VO_Hun_Heavy_Release"), false);
    assert.match(posts.at(-1), /BaiChiLian_Attack_Heavy_BiXian\.SFX_Combat_VO_BaiChiLian_Attack_Heavy_BiXian$/);
    assert.equal(play(attack, npc), true);
    assert.equal(play("Opening_Line"), true);
    assert.equal(play(attack, player, "/Game/Other/"), true);
    outfit = "Hun_MoTian";
    assert.equal(play(attack), true);
    assert.equal(posts.length, 2);
    outfit = "PBZ_OutFit_BaiQi";
    originalAllowed = false;
    assert.equal(play(attack), false);
    assert.equal(posts.length, 2);
    originalAllowed = true;
    playing = 0;
    assert.equal(play(attack), true);
    playing = 12;
    context.exports.stop();
    assert.equal(play(attack), true);
    context.exports = {};
    vm.runInContext(script, context);
    assert.equal(mixinCount, 1);
    assert.equal(play(attack), false);
    assert.equal(posts.length, 4);
});
