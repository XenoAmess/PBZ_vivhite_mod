# 白绮 056 后发与发饰

056 从 055 的两份 Blender 工程生成。原发饰近乎平行于正面机位，侧面只露出一道金边。后发 23 片发束的凸截面在侧面产生等距亮暗条纹。分件渲染还显示，Blender 验收灯下的大块颗粒状暗影来自发饰和刘海的投影。现行游戏包对相应发束、发饰和眼镜网格区段关闭了投影。`--game-hair-shadows` 把这项设置复用于离线验收灯光。 [Blender 材质与投影说明](https://docs.blender.org/manual/en/5.0/render/eevee/material_settings.html)

两套形态都调整了后发横截面和两侧发饰的弧度。后发顶点最大位移 2.53 毫米，发饰外缘最大位移 22.05 毫米。与 055 同灯光、同机位的对照中，侧面的发饰金边和翼面都能辨认，后发起伏更柔和。近看发梢的排列仍较整齐。保留了两套原头部和颈部几何、原嘴部贴图、衣装网格、骨架和 CC0 身体指纹。

按 054 游戏桥接的 `--neck-head-share .35` 复验。穿外套和脱外套各跑 33 组动作、197 个姿态，逐帧变形指标与 054 同参数档案一致。各形态新增数值超限为零，20 项 CC0 继承记录保持原样。颈区最差姿态的边长比 P95 为 1.464，单边最大 1.910。每个形态另渲染了转头、抬低头、头部俯仰、待机、前跑和双刀攻击的 108 张贴图及灰模特写。抽看的颈部接合轮廓连续。

两套游戏用 FBX 均已重新读回。相对同参数导出的 055，只有后发与黑金发饰的顶点坐标改变。两套的区段、三角面数、UV 和骨架一致，056 重烘焙的 66 张引擎纹理与 054 独立外观输入逐张一致。055 的 Blender 皮肤受光仍用于离线观察，当前游戏烘焙流程在引擎中使用自身的材质。

复现先用 `scripts/refine_baiqi_hair_finish.py` 读取 055 工程和 `face_lighting.json`，再用 `scripts/run_baiqi_cc0_motion_review.py` 的 `--face-closeup --game-hair-shadows --neck-head-share .35` 检查上述动作。FBX 导出用 `scripts/export_baiqi_game_forms.py` 的 `--reserve-native-slots --bake-alpha-geometry --support-skirt --separate-coat-material`。056 当前为离线候选，已安装的游戏模型仍为 054。
