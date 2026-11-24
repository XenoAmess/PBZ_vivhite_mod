# 复现资产与工程

这些文件按用户要求直接保存在 Git 仓库中，普通克隆即可获取完整内容。本次单文件均小于 100 MiB；更大的渲染归档将保存在仓库 Release。账户的 LFS 配额当前不可用，因此本仓库未依赖 LFS 指针。

- `../resources/Delta.zip`：第一份 Live2D 原始模型。
- `../resources/full.jpg`：另一个独立角色的参考图；本次 Delta 模型没有使用它。
- `models/rejected_v02/`、`baked/rejected_v02/`：历史模型和烘焙包。**用户已否定肩颈形体，不能作为验收通过版本。**
- `models/repair_001/`：第一次由 ROM 测试定位后修复权重的模型，仍有失败项。
- `native_inputs/repair_001/`：完整厘米制原生骨骼 Blender 工程与 FBX。
- `tests/`：带全部自编测试动作的 Blender 工程与参数/指标报告。
- `game_reference/`：选择性保存成年身体参考网格、参考骨架和三段动作，用于原骨骼适配与回归。其他零售游戏包与引擎安装文件没有纳入复现集。
- `textures/`：Blender 工程同时打包了这些贴图，单独保存便于检查。

准确文件大小和 SHA256 见 `manifest.json`。本机密钥、账号凭据与其他机密信息不上传。
