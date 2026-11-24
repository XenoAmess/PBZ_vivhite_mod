# 白绮 054.1 · 伊芙战斗语音

白绮两种外观都可使用《剑星》伊芙的战斗录音。识别范围为本地玩家、白绮外观、中文配音和 39 个原版战斗语音事件。对白、过场、音效和其他外观沿用游戏原声。模型使用 [054 调优前存根](https://github.com/XenoAmess/PBZ_vivhite_mod/releases/tag/baiqi-model-baseline-054)。

## 语音出处

录音来自 Shift Up 的《剑星》，对应 limbic7 的 **SoulFemaleVoice CombatOnly V1.3**。适配工具读取玩家在原站下载的压缩包，将音频接到白绮专用的 Wwise 事件目录。GitHub 发行附件是适配工具、运行脚本和说明。 [limbic7 原版文件 3368](https://www.nexusmods.com/phantombladezero/mods/599?tab=files&file_id=3368)

## 安装

先安装 [白绮 054 独立外观](https://github.com/XenoAmess/PBZ_vivhite_mod/releases/tag/baiqi-054-standalone) 及其加载器。准备作者的 CombatOnly V1.3 ZIP、Python 3 和 [retoc 0.1.5](https://github.com/trumank/retoc/releases/tag/v0.1.5)。在解压后的发行附件中运行以下两行，将示例路径替换为本机路径。第一行生成音频包，第二行在游戏退出后安装。

```powershell
py -3 scripts/build_baiqi_eve_wwise.py 'D:/Downloads/CombatOnly.zip' --retoc 'D:/Tools/retoc.exe' --game-root 'Z:/SteamLibrary/steamapps/common/PBZ'
py -3 scripts/install_baiqi_eve_voice.py --game-root 'Z:/SteamLibrary/steamapps/common/PBZ'
```

按作者说明在游戏中选择中文语音。使用「角色 → 外观 → 白绮」。安装时，白绮原先的语音脚本会备份到游戏的 `ProjectPBZ/Saved/BaiQiModBackups`。

## 复核

已读回 39 个 Wwise 事件的路径与编号。逐组比较确认嵌入录音与原始 CombatOnly 存档字节一致。回归测试覆盖白绮、原版外观、非玩家角色、英文配音、对白以及 Wwise 播放失败时的回退。

Steam 构建 26367565 实机验证了传承外观仍走原版语音。切到白绮后，出招和长刀收招成功播放伊芙录音。游戏输出与原包对应录音的归一化波形相关系数分别为 0.850 和 0.824。受击和其他武器未逐个实机抽查。
