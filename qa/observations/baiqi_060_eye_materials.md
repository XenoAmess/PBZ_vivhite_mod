# 白绮 060 眼部材质状态

这是 059 后的编辑器候选。两套 Blender 工程使用原表情为默认，另可通过 `BaiQi Eye Preview` 的 `pose` 切换半闭眼、闭眼和左右视线。头脸、嘴部、衣装和身体网格保持 059 的版本。

将四个眼部状态烘焙成游戏原生材质的实例。各状态只在已记录的眼区范围改颜色与粗糙度，其余像素与原表情逐像素一致。059 原有 84 张引擎输入完全一致。编辑器在两套 348 骨网格的第 30 号材质槽分别切换了四个状态，再恢复原表情，所有其他材质槽与切换前一致。此检查使用临时骨骼网格组件。 [UE 5.7 骨骼网格组件接口](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/SkeletalMeshComponent?application_version=5.7)

两套形态各比较 33 组动作、197 个姿态，变形指标及服装层接触数据与 059 一致。表情动作已在 Blender 和 UE 材质切换中验证，实机自动驱动留在后续验证阶段。游戏安装版依然是 054。

复现使用 `scripts/bake_baiqi_eye_preview_layers.py` 和 `scripts/build_baiqi_eye_preview.py`，完成两套游戏基础烘焙及 `--surface-finish` 后运行 `scripts/bake_baiqi_eye_materials.py`。`scripts/ue_review_baiqi_surface_finish.py` 自动读入追加的状态并验证切换。
