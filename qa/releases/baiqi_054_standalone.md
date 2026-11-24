# 白绮独立外观 054

适用于 Steam 版《影之刃零》构建号 26367565。在「角色 → 外观」选择「白绮」，右侧开关控制外套。首次选择默认穿外套。两种形态沿用同一份白绮身体、头部和内搭，外套开关只影响外套、翻领和两个袖口材质槽。

## 来源

- 白绮的战斗语音采用《影之刃零》原版白赤练录音。声音和按外观切换的方式参考 QOutlaw 的 **Playable Bai Chilian - Outfits and Voice**。白绮通过游戏已安装的 Wwise 事件调用同一角色的战斗录音，包内只有白绮的路由脚本。 [QOutlaw 原发布页](https://www.nexusmods.com/phantombladezero/mods/388)
- 独立外观、外套选项和选项存档由 **PBZ Outfit Framework** 提供，使用其第 7351 号外观及选项槽。 [框架原发布页](https://www.nexusmods.com/phantombladezero/mods/903)
- 预览姿势修复和战斗语音脚本通过 **PBZModLoader 1.0.4** 加载。 [加载器原发布页](https://github.com/zoneoflkf/PBZModLoader/releases/tag/v1.0.4)

## 安装

按作者说明安装 PBZ Outfit Framework 和 PBZModLoader。退出游戏，将发布包的 `ProjectPBZ` 合并至游戏目录。旧的 `z_BaiQi054Wardrobe_P` 三件套可以移至备份目录，腾出原版外观。

## 验收

读取已烘焙的 IoStore 包，确认两张表被框架引用，只有一条「白绮」外观，四个外套材质槽可隐藏，原版成年魂的 264 根驱动骨骼仍与游戏基准一致。游戏内打开外观时，预览替身原先禁用了动画后处理，白绮双臂停在 T 字姿势。启用后处理后已在实机分别查看外套显示和隐藏，双臂恢复待机姿势。语音回归测试覆盖白绮、原版外观、非玩家角色、对白和 Wwise 播放失败时的回退。语音实机验证以发行记录为准。
