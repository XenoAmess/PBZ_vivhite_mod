# PBZ_vivhite_mod

《影之刃零》成年魂替换模型的制作工作区，以及可长期维护的人物 ROM（关节活动范围）测试与离线验收工具。

**当前模型未通过肩颈验收。离线失败项修复、重渲染并复查通过之前，不进入实机验收。**

本阶段只处理用户提供的 Delta Live2D 角色；另一份全身图属于独立角色，不混用。仓库保存用户提供的模型、烘焙包、完整 Blender 工程，以及复现所需的选定游戏骨架、网格与动作。密钥、登录凭据和其他机密信息排除。

## 测试与维护

- [验收流程与维护规则](qa/MAINTENANCE.md)
- [资料依据](qa/sources.json)
- [测试集说明](qa/README.md)

初始诊断工具已覆盖颈部三轴、头骨隔离、肩臂、屈肘及组合动作。正在扩展为参数化的全身验收配置。

本机使用 Blender 5.3 与 Python 3；Blender 负责姿态、蒙皮求值和真实网格渲染，普通 Python/Pillow 负责把采样图整理成对照表。工作文件在本地 `output/` 生成，完整可复现快照整理后上传。

```powershell
.venv\Scripts\python.exe scripts/blender_task.py artifacts/self_test_suite.log scripts/build_self_test_suite.py
.venv\Scripts\python.exe scripts/assemble_self_test_review.py
```

当前命令默认读取本机 `build/shoulder_inputs/Delta_adult.blend`。其他机器需要自行准备模型和骨骼输入；公开仓库中的代码不包含这些资源。

数值检查用于定位伸长、压缩和权重突变，不能证明外观自然。必须保留失败记录，并使用同一套动作、角度、镜头、灯光和阈值复测。
