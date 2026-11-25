# 白绮项目交接手册

2026-11-26 交接，以 2026-11-25 归档的 103 为制作基准。先选对版本，再决定做离线调优还是正式游戏打包。制作取舍与失败对照见 [白绮制作与验收经验](BaiQi_Production_Notes.md)。

## 接手从这里开始

| 任务 | 起点 |
| --- | --- |
| 继续调模型 | 103 离线候选，模型提交 `ae103ec`。附件含穿外套、脱外套两份完整 Blend、双 FBX、烘焙图和校验清单。综合复查提交 `b2a77a7`。 [103 预发行附件](https://github.com/XenoAmess/PBZ_vivhite_mod/releases/tag/baiqi-model-103) [双形态复查](../qa/observations/baiqi_103_integrated_review.md) |
| 恢复本机复现输入 | 同页的 `BaiQi_103_Handover_Inputs.zip`。含动作供体、CC0 对照、五种眼部烘焙源图、鼻梁基底与两张补充法线、最小 UE 编辑器工程以及骨架桥读回数据。 |
| 安装已实机验证的版本 | 054 独立外观加 054.1 伊芙战斗语音适配器。Steam 参考构建 `26367565`。本机游戏目录为 `Z:/SteamLibrary/steamapps/common/PBZ`，现有 `ProjectPBZ/Content/Paks/~mods` 里有 Framework、白绮外观、伊芙三组 `.pak/.utoc/.ucas`。 [054 外观](https://github.com/XenoAmess/PBZ_vivhite_mod/releases/tag/baiqi-054-standalone) [054.1 语音](https://github.com/XenoAmess/PBZ_vivhite_mod/releases/tag/baiqi-054-eve-combat) |

当前项目只使用 `resources/Delta.zip`，目标是成年魂。外观菜单保留一个「白绮」条目，默认穿外套，在同条目内可脱外套。更早按普通和传承分别占皮肤的方案是历史资料。CC0 身体与静置骨骼位置锁定，头脸用用户确认版本，嘴用原画默认闭口。`ArtMesh53` 乘色和替代嘴型排除在成品之外。`resources/full.jpg` 留作另一份独立角色。 [原始资产和选定游戏参考](../repro/README.md)

## 从干净工作区恢复

在仓库根目录运行。工具基线为 Blender 5.3.0、UE 5.7.4、Python 3.13 与 NumPy/Pillow。Unreal 模块编译还需要本机 Visual Studio C++ 工具链。默认 Blender 和 UE 路径见命令，换机器时替换可执行文件路径。

```powershell
git clone https://github.com/h4lfheart/UEFormat.git vendor/UEFormat
git -C vendor/UEFormat checkout e618c6891a70a3c335f231cb22dde331ab88036f
py -3 -m pip install numpy==2.5.2 pillow==12.3.0
gh release download baiqi-model-103 --pattern 'BaiQi_103_*.zip' --dir output/model_archives --skip-existing
Get-FileHash output/model_archives/BaiQi_103_Model_Archive.zip,output/model_archives/BaiQi_103_Handover_Inputs.zip
Expand-Archive output/model_archives/BaiQi_103_Model_Archive.zip build/handover/BaiQi103
Expand-Archive output/model_archives/BaiQi_103_Handover_Inputs.zip .
```

| 文件 | SHA-256 |
| --- | --- |
| `BaiQi_103_Model_Archive.zip` | `6fcf2de87bf6ad3b91fe37e649ef4ee4a160e704a2116ab019ef0df32675847d` |
| `BaiQi_103_Handover_Inputs.zip` | `719e9017176ce62497324efd422c75bb70ae62e1436f15ba65c39b2ef8e58264` |

模型清单在 `build/handover/BaiQi103/manifest.json`，补充输入清单在 `artifacts/baiqi_103_handover/input_manifest.json`。补充包按仓库相对路径解压。在已有工作区，把附件先解压到单独目录并核对路径和哈希，再补入缺少的文件。最小编辑器工程面向离线读回和出图，UE 安装、编译缓存、凭据和零售游戏容器由各机器自行管理。 [补充输入清单](../repro/baselines/baiqi_103_handover.json)

## 重跑验证与烘焙

日常迭代从 `build/handover/BaiQi103/blender` 的工程另存新候选。用以下命令生成全套数值报告。`--render full` 可输出动作全量图片，`--render triage --case neck_pitch` 可抽查指定用例。动作供体的 `sampling_report.json` 要与 `.blend` 同目录，脚本会核对套组哈希与采样点。

```powershell
$blender = 'C:/Program Files/Blender Foundation/Blender 5.3/blender.exe'
$models = 'build/handover/BaiQi103/blender'
foreach ($form in @('coat_on','coat_off')) {
    & $blender -b -t 4 --disable-autoexec --python-exit-code 1 --python scripts/run_baiqi_cc0_motion_review.py -- --candidate "$models/BaiQi_CC0_$form.blend" --donor artifacts/baiqi_cc0_047_rom_donor/Delta_SelfTest.blend --out "artifacts/handover_motion/$form" --render none --neck-head-share .35 --wardrobe-layer-contacts --neckline-contacts --waist-seam-contacts --fringe-contacts --rear-lock-contacts --crown-contacts --temple-contacts
    if ($LASTEXITCODE) { throw "Motion review failed for $form" }
}
py -3 scripts/run_baiqi_remote_review.py --mode auto --models $models --out artifacts/handover_render --case neck_pitch --case Hun_BaiShanDual_Attack_A
py -3 -m unittest discover -s qa/tests -q
```

核对每形态 33 组、197 姿态，20 项 CC0 继承记录和 0 项新增标记。远端 6000D 是可选后端，`auto` 在拒接、校验失败、排队超限或无进展时用本机跑同一配置。`--mode local` 可主动选本机，`run.json` 记录实际后端。服务地址支持 `PBZ_RENDER_SERVICE_URL`，认证使用本机环境变量 `PBZ_RENDER_SERVICE_TOKEN`。 [维护规则和已接入接口](../qa/MAINTENANCE.md#6000d-统一服务调用)

交接验证使用独立 Git 工作树及两份归档重跑。双形态动作结果逐项一致，两个 FBX 的逐区段位置、UV 和面一致，103 张原生 PNG 的 SHA-256 全部与归档一致。

直接回看 103 可以使用归档内的 `baked`。修改模型后，导出到独立目录并按以下顺序重烘焙。某步失败时先处理日志中的首个错误，再继续后续步骤。103 的目标是 103 张原生 PNG，另检查纹理绑定和两个 FBX 的材料区段。

```powershell
$stage = 'build/handover/103-rebake'
$generated = 'build/handover/103-bake-support'
$poses = 'artifacts/baiqi_098_underjaw_edge/poses'
& $blender -b -t 6 --disable-autoexec --python-exit-code 1 --python scripts/export_baiqi_game_forms.py -- --candidate $models --out $stage --reserve-native-slots --bake-alpha-geometry --conform-fringe-edges --conform-frame-edges --refine-fringe-tip --support-skirt --separate-coat-material
py -3 scripts/bake_baiqi_game_materials.py --inputs $stage
py -3 scripts/bake_baiqi_native_material_inputs.py $stage output/live2d_delta/baiqi_cc0_054/skin_tone_report.json --surface-finish --frame-roughness .46 --frame-metallic .45 --frame-pad-finish --neck-normal output/live2d_delta/baiqi_084_neck_normals/T_BaiQiNative_NeckBridge.png --crown-normal output/live2d_delta/baiqi_095_crown_relief/T_BaiQiNative_CrownRelief.png
py -3 scripts/bake_baiqi_eye_materials.py --inputs $stage --poses $poses
py -3 scripts/bake_baiqi_face_relief.py --out "$generated/base_normal" --game-inputs $stage --nasal-strength .65 --nose-basis output/live2d_delta/baiqi_096_nose_ridge/nose_basis.npz --nose-lift .40 --nose-ridge .65
py -3 scripts/bake_baiqi_iris_roughness.py --inputs $stage --poses $poses
py -3 scripts/bake_baiqi_iris_relief.py --inputs $stage --poses $poses --out "$generated/iris_maps"
py -3 scripts/bake_baiqi_fringe_relief.py --inputs $stage --out "$generated/fringe" --attach-native
py -3 scripts/bake_baiqi_frame_relief.py --inputs $stage --out "$generated/frame" --attach-native
py -3 scripts/bake_baiqi_frame_padding.py --inputs $stage
py -3 scripts/bake_baiqi_frame_padding.py --inputs $stage --target fringe --radius 8 --report "$generated/front_hair_padding.json"
```

## Unreal 离线读回

先编译恢复出来的工程，使用独立命名空间跑读回。编辑器脚手架带有成年驱动骨架和原路径的最小材质参照，两个材质实例依赖本地占位母材质 `M_DeltaDummyMaster`。`PBZModTools` 为本工程的编辑器 C++ 工具，包含骨架对照、材质读回和分区投影接口。离线出图从烘焙 PNG 构建会话着色器，正式 Cook 使用有完整作者资产的工程。

```powershell
$project = (Resolve-Path 'build/UE/ProjectPBZ/ProjectPBZ.uproject').Path
$ueRoot = 'E:/UE_5.7'
$editor = "$ueRoot/Engine/Binaries/Win64/UnrealEditor-Cmd.exe"
& "$ueRoot/Engine/Build/BatchFiles/Build.bat" ProjectPBZEditor Win64 Development "-Project=$project" -WaitMutex -NoHotReloadFromIDE -NoUBA -MaxParallelActions=4
$env:PBZ_BAIQI_EDITOR_INPUTS = 'build/handover/BaiQi103/baked'
$env:PBZ_BAIQI_NATIVE_PREFIX = '/HuaShira/Mods/BaiQi103Handover/Native'
$reader = (Resolve-Path 'scripts/ue_review_baiqi_surface_finish.py').Path
& $editor $project -unattended -nop4 -stdout -FullStdOutLogOutput -nullrhi -NoShaderCompile -run=pythonscript "-script=$reader"

$preview = (Resolve-Path 'scripts/ue_render_baiqi_offline_preview.py').Path
$env:PBZ_BAIQI_PREVIEW_SHADOWS = 'package'
$env:PBZ_BAIQI_PREVIEW_SHOT_SET = 'regression'
$env:PBZ_BAIQI_PREVIEW_PASS = 'lit'
$env:PBZ_BAIQI_PREVIEW_STATES = 'neutral,half_blink,closed,look_left,look_right'
$env:PBZ_BAIQI_PREVIEW_OUT = 'artifacts/handover_unreal/regression'
& $editor $project -unattended -nop4 -stdout -FullStdOutLogOutput -RenderOffscreen -AllowCommandletRendering -d3d12 -NoAsyncAssetCompilation -run=pythonscript "-script=$preview"
```

读回成功标记为 `BAIQI_SURFACE_FINISH_EDITOR_READBACK`。检查每份网格的 348 骨与四种眼部切换，以及穿外套网格的四个外套区段。归档自带的 `surface_finish_readback.json` 记录此前的 UE 对象路径，迁移后应先生成新报告。嘴部图把 `PBZ_BAIQI_PREVIEW_SHOT_SET` 设为 `mouth`，`PBZ_BAIQI_PREVIEW_STATES` 设为 `neutral`，`PBZ_BAIQI_PREVIEW_PASS` 分别用 `lit` 和 `albedo`，两组使用不同输出目录。 [离线渲染参数](../repro/baiqi_unreal_offline_preview.md)

交接用恢复出的 C++ 工程完成了编译和读回，也复现了 50 张常规图和 32 张嘴部图。本机初次编译卡在 UBA，以上命令沿用成功重试的 `-NoUBA` 参数。

## 正式发行与回退

1. 以当前 054 发行包和模型存根做对照，用工作机已有的完整编辑器工程恢复正式装配。`scripts/prepare_baiqi_outfit_data.py`、`scripts/prepare_baiqi_outfit_editor.py`、`scripts/ue_stage_baiqi_standalone.py` 保存 054 的流程。独立外观占 Outfit Framework `7351`。装配入口有 054 固定产物路径和缓存判断。升级时为新版本明确设定输入与安装目标，核对外观表、选项表、四个外套槽与原生动画桥。正式 Cook 还需要当前最小复现包之外的 `PA_Hun`、`Hun_Head_New`、桥接校准资产、Framework 选项结构和外观数据。 [054 发行记录](../qa/releases/baiqi_054_standalone.md)
2. 退出游戏并备份现有白绮三个容器和 `ProjectPBZ/PBZModLoader/mods/baiqi-voice`。备份可放到 `ProjectPBZ/Saved/BaiQiModBackups`。保持原生白绮条目和外套开关，复查菜单预览是否走正确待机，以及退出菜单后动画桥、IK 和布料能否接回。正式验收需要两种形态的切换、移动、受击、武器和出招，记录 Steam 构建及包哈希。
3. 语音沿用 054.1 的独立路由。适配器读取 limbic7 的 **SoulFemaleVoice CombatOnly V1.3**，配合 `retoc 0.1.5` 本机生成。路由只作用于中文配音下本地玩家的白绮战斗事件。已读回 39 项，旧实机抽查覆盖出招与长刀收招，受击和其余武器需要随正式发行补查。发布说明继续保留作者和来源。 [伊芙安装及出处](../qa/releases/baiqi_054_eve.md)
4. 需要回退时先退出游戏，再把本次替换的白绮三件套与脚本恢复为备份版本。模型离线归档继续用 `scripts/archive_baiqi_model_version.py`，新标签须指向对应候选提交。正式安装附件与离线模型档分开发行。

## 接手时需要知道的遗留项

- 103 已完成离线回归。近乎纯侧面和特定低位光仍能看到头顶原发峰的窄暗边，几何和局部法线试验均已有对照。 [头顶试验记录](../qa/observations/baiqi_103_crown_profile_review.md)
- 本机工作区原有一批早期组件迁移草稿和未提交测试，其中对 `ArtMesh53` 的启用条件与当前决策冲突。接手从公开 `main` 和归档输入开始，若需要这些草稿，再逐项核对并独立合并。
