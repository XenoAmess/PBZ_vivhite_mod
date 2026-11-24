"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");

const script = fs.readFileSync(path.join(__dirname, "../../mods/baiqi-voice/preview.js"), "utf8");

test("restores animation post-processing for the BaiQi preview and releases the setting on exit", () => {
    const baiqi = "/HuaShira/Mods/BaiQi054/Standalone/SK_BaiQi.SK_BaiQi";
    let selected = "/HuaShira/Hun";
    let disabled = true;
    let playCount = 0;
    let pending;
    const evidence = [];
    const writes = [];
    const mesh = {
        GetSkeletalMeshAsset: () => ({ path: selected }),
        GetSocketLocation: name => ({
            Z: name.endsWith("Hand") ? (disabled ? 49 : 10) : name === "hand_l" ? 0 : 50,
        }),
        GetDisablePostProcessBlueprint: () => disabled,
        SetDisablePostProcessBlueprint: value => {
            writes.push(value);
            disabled = value;
        },
        PlayAnimation: () => { playCount += 1; },
        GetPosition: () => 0,
        SetPosition() {},
    };
    const ue = {
        GameplayStatics: { GetGameMode: () => ({ getActivePreviewDoll: () => ({ Mesh: mesh }) }) },
        KismetSystemLibrary: { IsValid: Boolean, GetPathName: asset => asset.path },
        Object: { Load: () => ({}) },
    };
    const context = {
        exports: {},
        require: id => id === "ue" ? ue : { argv: { getByName: () => ({}) } },
        setInterval: callback => { pending = callback; return 1; },
        clearInterval: () => { pending = undefined; },
    };
    vm.runInNewContext(script, context);
    const stop = context.exports.monitor(line => evidence.push(line));
    pending();
    assert.deepEqual(writes, []);
    selected = baiqi;
    pending();
    pending();
    assert.deepEqual(writes, [false]);
    assert.deepEqual(evidence, [
        "PREVIEW_IDLE_RESET driver=50.0 visible=1.0 disabled=true",
        "PREVIEW_POSE driver=50.0 visible=40.0",
    ]);
    assert.equal(playCount, 1);
    selected = "/HuaShira/Hun";
    pending();
    assert.deepEqual(writes, [false, true]);
    stop();
    assert.equal(pending, undefined);
});
