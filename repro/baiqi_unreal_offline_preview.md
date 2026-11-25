# 白绮 Unreal 离线彩色验收

这个预览用 UE 编辑器导入的两套骨骼网格和同一版本的烘焙 PNG 出图。灯位、机位与曝光参数固定，支持正面左右光、斜视和斜后视。用本地预览材质读取颜色、AO、粗糙度、金属度和切线法线。游戏正式版会继承原游戏材质，发行时还需要核对游戏内的灯光和换装效果。 [Unreal 材质输入](https://dev.epicgames.com/documentation/en-us/unreal-engine/material-inputs-in-unreal-engine)

复用已有的 `build/UE/ProjectPBZ` 编辑器工程。先按版本的验收流程生成 `surface_finish_readback.json`，准备 `native_textures`、`engine_materials.json`、`surface_finish.json` 和 `eye_palette.json`。在仓库根目录运行以下命令。每次从原 PNG 导入会话纹理，避免渲染复跑丢失色图。程序在首张正视图检查脸与发饰颜色，随后按形态、状态和机位写 PNG 和 `preview_manifest.json`。

```powershell
$env:PBZ_BAIQI_EDITOR_INPUTS = 'build/baiqi_081_game_inputs'
$env:PBZ_BAIQI_PREVIEW_OUT = 'artifacts/baiqi_081_unreal_preview'
$env:PBZ_BAIQI_PREVIEW_STATES = 'neutral,half_blink,closed,look_left,look_right'
$project = (Resolve-Path 'build/UE/ProjectPBZ/ProjectPBZ.uproject').Path
$script = (Resolve-Path 'scripts/ue_render_baiqi_offline_preview.py').Path
& 'E:/UE_5.7/Engine/Binaries/Win64/UnrealEditor-Cmd.exe' $project -unattended -nop4 -stdout -FullStdOutLogOutput -RenderOffscreen -AllowCommandletRendering -d3d12 -run=pythonscript "-script=$script"
```

默认 `neutral` 输出两形态各四张。上面的五状态命令输出 40 张。这个预览检查静止形态和材质切换，动作范围继续用 Git 库里的白绮动作套组复验。

![081 两种形态和眼部切换示例](../qa/figures/baiqi_unreal_preview_081/contact_sheet.jpg)
