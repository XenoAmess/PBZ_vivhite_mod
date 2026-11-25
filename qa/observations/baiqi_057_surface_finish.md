# 白绮 057 服装、材质与表情试验

057 从 056 两套 Blender 工程生成。原 CC0 身体、脸和颈部网格、原始人脸贴图及骨架指纹全部复核一致。改动限于服装、眼镜、发束和白绮材质。

## 服装和头部

- 脱外套上衣的前片跨过胸线。离中线 60 毫米处到衣片中央的前后差，在 1.175 米高度由 19.84 毫米减到 6.30 毫米。该调整沿领口、侧边和腰线渐隐。
- 外套翻领加了折起的体积。上衣、外套和金属镜框的边缘厚度已写入 FBX。镜框保留原图轮廓。后发长短变化集中在发梢，刘海顶部轻微收低。
- 游戏烘焙的原有 66 张纹理逐张一致。新增 16 份材质设置，通过现行游戏原生父材质读取独立粗糙度、法线和高光。虹膜区用原眼部遮罩，衣布法线图加入细织纹，脸和补颈继续使用原肤色色样。实际游戏受光需由之后的发行前实机检查确认。 [Epic 材质输入](https://dev.epicgames.com/documentation/en-us/unreal-engine/physically-based-materials-in-unreal-engine?application_version=5.7)

## 验收

- 穿外套和脱外套各检查 33 组动作、197 个姿态。肩、肘和颈的逐帧变形指标与 056 一致。两形态各有原 CC0 身体的 20 项记录，新增变形超限为零。
- 两形态分别重渲染抬臂、前伸、够肩、防御、前跑、双刀攻击，以及抬低头和转头。服装实体厚度使部分样帧的几何接触计数增加。抽看的同机位渲染未见新露皮，内层接触计数仍留在动作报告。
- UE 5.7.4 将两套 FBX 导入单独的 057 编辑器路径，重新读回 348 骨、穿外套的四个切换区段，以及 16 份材质实例。编辑器保留了每个粗糙度贴图、法线引用和所配的高光参数。FBX 导入器重建了校验用驱动骨绑定姿势，随后通过原生参考骨骼一致性检查。

## 表情试验副本

以原 Cubism Core 的 `ParamEyeLOpen`、`ParamEyeROpen`、`ParamEyeBallX` 采样半闭、全闭和左右视线。只替换眼部变化的像素，对照原嘴部和其余区域逐像素一致。两套实验工程的 `BaiQi Eye Preview` 对象提供 `pose` 属性，0 为原表情，1 至 4 为半闭、全闭、左视和右视。离线控制器的五张渲染与直接换图对照逐像素一致。两套普通 057 工程与游戏烘焙保持中性表情，实验表情还需接到游戏的视线和眨眼驱动。

## 复现

造型使用 `scripts/finish_baiqi_surfaces.py`。FBX 沿用 056 的导出参数。烘焙完成后给 `scripts/bake_baiqi_native_material_inputs.py` 传 `--surface-finish`，UE 使用 `scripts/ue_review_baiqi_surface_finish.py` 读回，并通过 `PBZ_BAIQI_EDITOR_INPUTS` 与 `PBZ_BAIQI_NATIVE_PREFIX` 指定独立候选输入和材质目录。表情试验由 `scripts/bake_baiqi_eye_preview_layers.py` 和 `scripts/build_baiqi_eye_preview.py` 生成。

057 为离线与编辑器候选。游戏继续使用已发行的 054 模型及 054.1 战斗语音。
