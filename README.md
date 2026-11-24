# PBZ_vivhite_mod

《影之刃零》成年魂替换模型的制作工作区，以及可长期维护的人物 ROM（关节活动范围）测试与离线验收工具。

**当前模型未通过全身形体及动作验收。离线失败项修复、重渲染并复查通过之前，不进入实机验收。**

本阶段只处理用户提供的 Delta Live2D 角色；另一份全身图属于独立角色，不混用。仓库保存用户提供的模型、烘焙包、完整 Blender 工程，以及复现所需的选定游戏骨架、网格与动作。密钥、登录凭据和其他机密信息排除。

## 测试与维护

- [验收流程与维护规则](qa/MAINTENANCE.md)
- [资料依据](qa/sources.json)
- [测试集说明](qa/README.md)
- [全身统一检查、失败项与修复顺序](qa/WHOLE_BODY_REVIEW.md)
- [开放授权女性基模整体重建评估](qa/BASE_MESH_EVALUATION.md)

静态形体检查 v1.1.0 覆盖全身八视角及十三个局部的六视角，灰模/贴图共 172 张。每个部位分别记录结果。完整 Blender 工程与原生输入见 `repro/`，完整图集归档见上述 Release。

v1.0.0 已包含 30 组动作、182 个姿态，其中含 37 个项目自定义颈部组合/隔离姿态。覆盖肩、肘、腕、手指、脊柱、髋、膝、踝、脚掌和组合姿态。全部采样包含三个规定视角与灰模/贴图两种渲染，共 1,092 张图。

本机使用 Blender 5.3 与 Python 3；Blender 负责姿态、蒙皮求值和真实网格渲染，普通 Python/Pillow 负责把采样图整理成对照表。工作文件在本地 `output/` 生成。[首轮完整归档](https://github.com/XenoAmess/PBZ_vivhite_mod/releases/tag/qa-v1.0.0-initial)包含 1,092 张采样、完整测试 Blend 和准确的输入及代码，保留失败状态。更多状态见 [PROJECT_STATE](SOP/PROJECT_STATE.md)。

```powershell
.venv\Scripts\python.exe scripts/blender_task.py artifacts/self_test_suite.log scripts/build_self_test_suite.py
.venv\Scripts\python.exe scripts/assemble_self_test_review.py --output output/live2d_delta/self_test_standard
python -m unittest discover -s qa/tests -v
```

当前命令默认读取本机 `build/shoulder_inputs/Delta_adult.blend`。克隆仓库后可直接使用已上传的完整输入：为渲染命令增加 `--candidate repro/native_inputs/repair_001/Delta_adult.blend`。

数值检查用于定位伸长、压缩和权重突变，不能证明外观自然。必须保留失败记录，并使用同一套动作、角度、镜头、灯光和阈值复测。
