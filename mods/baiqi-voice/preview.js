"use strict";

const UE = require("ue");
const { argv } = require("puerts");

const MESH = "/HuaShira/Mods/BaiQi054/Standalone/SK_BaiQi.SK_BaiQi";
const IDLE = "/HuaShira/Characters/Hero/Hero_Hun/Animation/Locomotion/Unarmed/Idle/Hun_Unarmed_Idle_Loop.Hun_Unarmed_Idle_Loop";
const valid = value => Boolean(value && UE.KismetSystemLibrary.IsValid(value));

function armDrop(mesh, shoulder, wrist) {
    return mesh.GetSocketLocation(shoulder).Z - mesh.GetSocketLocation(wrist).Z;
}

exports.monitor = function monitor(log) {
    let current;
    let attempts = 0;
    let idle;
    let restoredSetting;
    function releasePreview() {
        if (restoredSetting !== undefined && valid(current)) {
            current.SetDisablePostProcessBlueprint(restoredSetting);
        }
        restoredSetting = undefined;
        current = undefined;
    }
    const timer = setInterval(() => {
        try {
            const context = argv.getByName("GameInstance");
            if (!valid(context)) return;
            const mode = UE.GameplayStatics.GetGameMode(context);
            const doll = valid(mode) && mode.getActivePreviewDoll && mode.getActivePreviewDoll();
            const mesh = valid(doll) && doll.Mesh;
            const asset = valid(mesh) && mesh.GetSkeletalMeshAsset();
            if (!valid(asset) || UE.KismetSystemLibrary.GetPathName(asset) !== MESH) {
                releasePreview();
                return;
            }
            if (mesh !== current) {
                releasePreview();
                current = mesh;
                attempts = 0;
            }
            if (attempts > 1) return;
            const driver = armDrop(mesh, "upperarm_l", "hand_l");
            const visible = armDrop(mesh, "BaiQi_J_Bip_L_UpperArm", "BaiQi_J_Bip_L_Hand");
            if (attempts === 1 || visible > 19) {
                log("PREVIEW_POSE driver=" + driver.toFixed(1) + " visible=" + visible.toFixed(1));
                attempts = 2;
                return;
            }
            idle = valid(idle) ? idle : UE.Object.Load(IDLE);
            if (!valid(idle)) return;
            restoredSetting = mesh.GetDisablePostProcessBlueprint();
            log("PREVIEW_IDLE_RESET driver=" + driver.toFixed(1) + " visible=" + visible.toFixed(1) +
                " disabled=" + restoredSetting);
            mesh.SetDisablePostProcessBlueprint(false);
            mesh.PlayAnimation(idle, true);
            mesh.SetPosition(Math.max(0.05, mesh.GetPosition()), false);
            attempts = 1;
        } catch (error) {
            clearInterval(timer);
            releasePreview();
            log("PREVIEW_ERROR " + String(error));
        }
    }, 180);
    return () => {
        clearInterval(timer);
        releasePreview();
    };
};
