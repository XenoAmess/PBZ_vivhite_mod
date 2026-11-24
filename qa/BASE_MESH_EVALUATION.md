# 女性基础模型整体重建评估

结论：有必要以结构完整、许可明确的女性基模整体重建人体，保留 Delta 的角色设计、原生成年魂骨架、已验证的导入/材质/烘焙流程和验收工具。当前问题跨越十三个形体部位，继续局部补洞难以建立一致的比例、拓扑和变形基础。

## 已做的可行性验证

- 下载旧版 VRoid Project `Base_Female.vrm`，检查嵌入元数据中的作者和 CC0 标记，导入 Blender。
- 分离身体皮肤与服装，确认底层包含完整躯干、四肢、手指及头部结构，不依赖衣服遮住缺失部位。
- 制作 `anatomy_foundation_002` 灰模样件：映射 52 个源骨骼组到成年魂的原生骨架，保留全部 264 骨、父子关系和参考矩阵，使用线性蒙皮。
- 对固定 ROM 的 182 个姿态运行数值定位，14 项超限均在颈部，尚未完成该样件的全量渲染和目检。需要重新处理源单段颈部与目标双段颈部的权重分配。此结果不能当作验收通过，也不能仅按超限数量给不同拓扑模型排名。
- 已从本地游戏选择性导出玉儿、沐小葵的身体和头部，完成 24 张灰模参考渲染。她们分别包含 1000/1090 根身体骨骼，不能直接替换成年魂的 264 骨架；用于观察女性颅骨、颈肩、胸廓、骨盆和肢体结构。

## 候选对比

| 基础资源 | 当前证据 | 用途与待做工作 |
| --- | --- | --- |
| 旧版 VRoid CC0 女性基模 | 已下载、导入、分离皮肤、完成成年魂骨架接入及数值定位 | 优先验证路线。风格接近 Delta，已有完整手指和人体拓扑；需重绑颈部，校正比例、足底与服装，再重做 Delta 头发、服装和 UV。 |
| Blender Human Base Meshes v1.4.1 | 已从官方地址下载，包含女性写实和风格化网格，CC0 | 第二组结构参考与重建备选。官方定位是雕刻基础；不能未经检查称为游戏动画成品，需要独立绑定、拓扑和变形验证。 |
| MakeHuman / MPFB 核心资产 | 官方确认基础网格、目标和核心资产为 CC0，尚未做本机样件 | 适合参数化人体比例和写实女性体积对照；匹配 Delta 的二次元脸型和服装仍需定制。 |

VRoid 软件和当前全部预设不等于开源或 CC0。本次使用的是明确标注 CC0 的旧版具体模型；不把该许可推及其他资源。

## 重建边界与验收

人体基础网格负责连续的颅骨、躯干与四肢结构；玉儿和沐小葵提供用户指定的女性结构对照；Delta Live2D 决定角色外观、发型、服装和风格化比例。full.jpg 属于另一位角色，不参与。

需要重新制作人体比例、肩颈和手脚连接、服装及头发几何、UV 和蒙皮。原生骨架、材质兼容方案、烘焙读回检查、安装工具和版本化测试套件可以复用。

先通过 172 张静态全身检查，再完成 1,092 张 ROM 采样及逐项复查；随后检查真实游戏动作和烘焙读回，最后进入实机。任一基础网格样件均不意味着完成 Mod。

## 来源

- [VRoid 旧版基础/样例许可说明](https://vroid.pixiv.help/hc/en-us/articles/4402614652569)
- [VRoid 当前指南](https://vroid.com/en/studio/guidelines)
- [Blender 官方基础网格目录](https://download.blender.org/demo/asset-bundles/human-base-meshes/)
- [Blender 官方资产说明](https://archive.blender.org/wiki/2024/wiki/Source/Architecture/Asset_System/Asset_Bundles/Human_Base_Meshes.html)
- [MakeHuman / MPFB 许可](https://www.makehumancommunity.org/about/license.html)
- [玉儿——王琛作品页](https://wangchen-cg.artstation.com/projects/nd4NoK)
- [沐小葵——王琛作品页](https://wangchen-cg.artstation.com/projects/RqLdJX)
