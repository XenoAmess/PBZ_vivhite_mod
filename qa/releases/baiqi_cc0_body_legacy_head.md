# 白绮 047 离线试装

两份 Blender 工程分别保存穿外套和脱外套形态。身体使用旧版 VRoid Project 的 CC0 `Base_Female.vrm`。服装模型独立制作，两份工程共用身体、脸和原始 CC0 身体骨架。身体的工厂服装、头皮和基模脸通过显示设置隐藏。交界处的过渡网格和材质位于白绮头部件。

头脸从 039 的 `BaiQi_Assembly.blend` 恢复。两份工程载入后均校验了 9,516 个原脸部三角面的位置和 UV，并校验原脸部贴图的 SHA-256。脸部整体统一缩放及定位，保留 039 的默认嘴型、粉色眼睛、短发、发饰和眼镜。

## 渲染复核

两种形态各输出 13 张渲染，包含正面、背面、侧面、斜前方和上半身近景。近景覆盖放松站姿、展臂、前伸、左右转头各 41°、抬头 25°、低头 27° 和侧倾 18°。

047 使用连续颈部网格连接旧版头部与 CC0 身体。原身体渲染时按静置高度遮蔽连接处重叠的边缘。对照 045 的正面和侧面，接缝毛边及转头时的暗点已消除。两套原始肤色在颈部渐变衔接，侧面仍可看出色调差异。外套前片和裙腰还需随整套动作复查。

状态为 `pending_review`。此轮动作使用 CC0 骨架。成年魂的动画重定向、完整动作集验收和游戏打包仍待完成。

## 复现入口

1. `scripts/lock_baiqi_cc0_body.py` 在已导入 Blender 的 CC0 `Base_Female.blend` 上生成带身体指纹的试装文件。
2. `scripts/fit_baiqi_cc0_wardrobe.py` 使用 `--locked` 指定试装文件，`--head-from` 指定 039 的输入，并通过 `--output` 指定输出目录。服装贴图来自 `scripts/bake_baiqi_body_source_layers.py` 的输出。
3. `scripts/verify_baiqi_cc0_restoration.py` 使用 `--base`、`--head-from` 和 `--fitting` 复查源模型、039 头脸和两份试装工程。
4. `scripts/render_baiqi_cc0_fitting.py` 对两个 `--form` 值 `coat_on` 和 `coat_off` 分别渲染，使用 `--fitting` 指定工程目录。
