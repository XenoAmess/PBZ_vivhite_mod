# PBZ_vivhite_mod

《影之刃零》成年魂替换模型的制作工作区，以及可长期维护的人物 ROM（关节活动范围）测试与离线验收工具。

**103 是当前离线模型候选，两种形态已复核。已实机验证的安装版本为 054 独立外观与 054.1 伊芙战斗语音。** [103 模型和复现输入](https://github.com/XenoAmess/PBZ_vivhite_mod/releases/tag/baiqi-model-103) [054.1 发行](https://github.com/XenoAmess/PBZ_vivhite_mod/releases/tag/baiqi-054-eve-combat)

本阶段只处理用户提供的白绮（`Delta.zip`）Live2D 角色；另一份全身图属于独立角色，不混用。仓库保存用户提供的模型、烘焙包、完整 Blender 工程，以及复现所需的选定游戏骨架、网格与动作。密钥、登录凭据和其他机密信息排除。

[白绮女性基模迁移记录](characters/baiqi/MIGRATION.md)保存原始组件与状态的三维映射。早期迁移样件及其失败记录保留为历史对照。

## 测试与维护

- [白绮项目交接手册](docs/BaiQi_Handover.md)
- [白绮制作与验收经验](docs/BaiQi_Production_Notes.md)
- [模型版本存档](repro/baiqi_model_versions.md)
- [验收流程与维护规则](qa/MAINTENANCE.md)
- [资料依据](qa/sources.json)
- [测试集说明](qa/README.md)
- [早期全身检查、失败项与修复顺序](qa/WHOLE_BODY_REVIEW.md)
- [开放授权女性基模整体重建评估](qa/BASE_MESH_EVALUATION.md)

103 每种形态有 33 组动作、197 个姿态的离线报告，以及 UE 的 50 张常规和 32 张嘴部回归图。历史静态形体检查 v1.1.0 覆盖全身八视角及十三个局部的六视角，灰模与贴图共 172 张。 [103 双形态复查](qa/observations/baiqi_103_integrated_review.md)

v1.0.0 已包含 30 组动作、182 个姿态，其中含 37 个项目自定义颈部组合/隔离姿态。覆盖肩、肘、腕、手指、脊柱、髋、膝、踝、脚掌和组合姿态。全部采样包含三个规定视角与灰模/贴图两种渲染，共 1,092 张图。

本机使用 Blender 5.3 与 Python 3；Blender 负责姿态、蒙皮求值和真实网格渲染，普通 Python/Pillow 负责把采样图整理成对照表。工作文件在本地 `output/` 生成。[首轮完整归档](https://github.com/XenoAmess/PBZ_vivhite_mod/releases/tag/qa-v1.0.0-initial)包含 1,092 张采样、完整测试 Blend 和准确的输入及代码，保留失败状态。更多状态见 [PROJECT_STATE](SOP/PROJECT_STATE.md)。

```powershell
.venv\Scripts\python.exe scripts/blender_task.py artifacts/self_test_suite.log scripts/build_self_test_suite.py
.venv\Scripts\python.exe scripts/assemble_self_test_review.py --output output/live2d_delta/self_test_standard
python -m unittest discover -s qa/tests -v
```

这组历史命令默认读取本机 `build/shoulder_inputs/Delta_adult.blend`。复现 `repair_001` 时为渲染命令增加 `--candidate repro/native_inputs/repair_001/Delta_adult.blend`。103 的复现走交接手册中的命令。

数值检查用于定位伸长、压缩和权重突变，不能证明外观自然。必须保留失败记录，并使用同一套动作、角度、镜头、灯光和阈值复测。
