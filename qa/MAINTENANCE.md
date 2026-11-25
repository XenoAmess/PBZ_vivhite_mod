# 维护与验收规则

## 版本与复现

- 动作 ID 不得复用为不同动作；修改角度、骨骼分配、镜头、灯光、采样或阈值须更新套件版本。
- 每次运行保存模型、套件、配置和执行代码的 SHA256；结果放入独立运行目录，不覆盖失败记录。
- 单关节扫动以中立姿态开始和结束；组合姿态单独记录，避免多关节动作掩盖问题。
- 先看灰模轮廓和连接，再看贴图/材质。所有规定镜头都必须渲染，不能只挑正面。
- 公开仓库保存代码、参数、失败原因和修复结论，也保存用户模型、烘焙包和完整 Blender 工程；大文件使用 Git LFS 或仓库 Release，并保存哈希。游戏文件按复现需求选择性上传。本机密钥和其他机密信息始终排除。

## 必查项目

静态全身形体使用 `shape_audit_v1.json` v1.1.0：全身八视角，十三个局部各六视角，灰模/贴图共 172 张。头部、肩颈、躯干、双上臂、双肘、双手、骨盆、腿、膝、脚分别记录检查结果；任何缺失或失败都会阻止实机。v1.0.0 的 88 张初始诊断保留，局部背面及右侧覆盖不足已在 v1.1.0 补齐。

1. 中立形体：头颈高度、颈肩过渡、肩宽、上下臂比例、关节位置与角色参考一致。
2. 关节：颈部三轴与组合、锁骨、肩部抬起/前伸/扭转、肘、腕、手指、脊柱、髋、膝、踝。
3. 组合：双手前伸防御、交叉触肩、手触头、蹲姿；之后再检查当地导出的真实游戏动画。
4. 网格：无开裂、尖刺、局部突然变细、明显丢失体积、衣领粘颈、腕部脱开、显著穿插。
5. 贴图：没有跨材质 UV 污染、环形黑边、拉花和裸露错误背面。
6. 输出：骨骼引用、权重、UV、法线与烘焙读回一致，禁止仅开 Blender Preserve Volume 掩盖游戏线性蒙皮问题。

## 放行

数值检查只负责筛选问题，不能代替外观。必须同时满足：参数覆盖完整、所有数值硬门槛通过、所有动作和中立形体人工复查通过、已知缺陷关闭、复查记录与本次输入哈希一致。

状态只能是 `failed`、`pending_review`、`offline_accepted`。`failed` 或 `pending_review` 不允许启动实机验收。离线通过后，实机仍须另记结果，不能沿用旧包的截图或哈希。

## 下一轮优先项 · 嘴部设计

从 098 离线存档开始。复现正面及斜侧仰视时的异常嘴线，同机位渲染底色、灰模和受光图，核对原默认嘴的源图层、三维唇缝与嘴角位置。用原默认嘴的宽度、嘴角走势、唇线和闭口神态作为造型基准，在异常实际出现的贴图或曲面范围内比较修整方案。

首轮分层已经复现两条线。原 Live2D 默认嘴的主唇线是 `Mouth2`，在原 880×800 图集的 y=533–535。098 灰模的口部凹槽在约 y=541–543。仰头 35° 时，两者在画面中明显错开。下一步分别比较唇线对齐和闭口曲面重塑，以一个自然贴合的闭口唇缝作为接受条件。[098 嘴部底色、灰模和受光对照](figures/baiqi_mouth_design/mouth_layers_and_pitch.jpg)

两种形态都检查正视、斜视、侧视及约 20°、35° 的仰视，包含换灯、仰头和游戏攻击动作。闭口的唇缝与嘴角应连续，仰视时的下唇应有自然体积。只在唇周授权范围内评估几何或贴图变化，其外的原脸、肤色、CC0 身体和骨架继续按既有指纹验收。候选通过离线对照后单独提交代码、双工程、烘焙与验收记录。

Unreal 离线预览使用 `scripts/ue_render_baiqi_offline_preview.py`，设 `PBZ_BAIQI_PREVIEW_SHOT_SET=mouth`、`PBZ_BAIQI_PREVIEW_STATES=neutral` 和 `PBZ_BAIQI_PREVIEW_SHADOWS=package`。分别设置 `PBZ_BAIQI_PREVIEW_PASS=lit` 与 `albedo`，输出到不同目录。此预设使用低位主光、两侧照明和八个机位，覆盖正面、侧面以及约 20°、29°、35° 和 42° 仰视。

常规双形态表情回归使用同一脚本的 `PBZ_BAIQI_PREVIEW_SHOT_SET=regression`，用 `lit` 预览 `neutral,half_blink,closed,look_left,look_right`。包含正面双侧打光、左右斜视和斜后五个机位，共 50 张图。

099 的首个闭口候选保留原画唇线，重做了旧开口所在的局部曲面。100 对照三档唇部起伏后采用中间档，补足侧面体积。两种形态在正面、侧面和仰视复核中均只出现一条闭口唇线。以上机位进入后续回归。[099 嘴部验收记录](observations/baiqi_099_closed_mouth.md) [100 唇部体积记录](observations/baiqi_100_lip_volume.md)

## 6000D 统一服务调用

`scripts/run_baiqi_remote_review.py` 默认采用 `auto`。它检查网关是否接单，打包两套模型、动作供体及报告、CC0 对照和本次选中的游戏动作，再通过 `/v1/render/assets` 和 `/v1/render/jobs` 提交。节点固定使用验收脚本 `fb7e7cf`、Blender 5.3.0 和 EEVEE。客户端按结果 ZIP 哈希、逐文件哈希、输入模型哈希、动作套组哈希和图数核对回包。[统一模型服务协议](https://github.com/XenoAmess/local-model-operations/blob/main/deployments/video-generation/docs/unified-model-service.md#blender-白绮动作验收)

```powershell
py -3 scripts/run_baiqi_remote_review.py --models output/live2d_delta/baiqi_094_crown_profile --out artifacts/remote_review_094
```

`--models` 指向含 `BaiQi_CC0_coat_on.blend` 和 `BaiQi_CC0_coat_off.blend` 的目录。`--form`、`--case`、`--view`、`--sample-index` 可重复指定。默认跑两种形态、三组动作、三个采样、两个视角，分别输出灰模与贴图。默认每图 1280×1280、32 样本，共 72 张。服务每次最多接收 512 张图。需要自定义供体和对照时使用 `--donor` 与 `--cc0-control`。

远端拒绝连接、维护、任务失败、结果校验失败、排队超过 60 秒或 120 秒无进展时，自动退回本机 Blender 执行同一动作和渲染参数。等待上限可用 `--queue-timeout` 和 `--stall-timeout` 调整，超时会尝试取消该次提交的任务。`--mode local` 直接本地执行，`--mode remote` 用于单测远端并保留错误。服务地址可通过 `PBZ_RENDER_SERVICE_URL` 或 `--service-url` 设置，局域网默认 `http://192.168.1.11:8080`。如服务启用认证，用环境变量 `PBZ_RENDER_SERVICE_TOKEN` 传入。可用 `--blender` 或 `PBZ_BLENDER_EXE` 指定本机 Blender。

两条路径都把图片和动作报告写入输出目录下的 `result/`。`run.json` 记录执行端、耗时及回退原因。远端还保留经校验的原始 `result.zip` 和其中的 `manifest.json`。整套动作接触度量、面部专用近景及 Unreal 读回继续用各自的本机验收入口。

2026-11-25 联调分别用真实 6000D 和故意断连后的本机回退运行默认批次。两端各回收 72 张 PNG，两个形态各有 3 组动作和 15 个姿态，逐项动作报告一致。6000D 渲染流程约 28.5 秒，本机约 29.3 秒，队列与文件传输时间另计。

## 6000D 渲染节点 HTTP 接口提案

此节记录最初的接口提案。接入后使用上一节的统一服务协议。

首期支持 `blender_review`，使用 Blender 5.3.0 的 EEVEE 跑白绮动作套组。模型文件打包贴图。动作供体 `Delta_SelfTest.blend` 及同目录 `sampling_report.json`、CC0 对照 `Base_Female.blend`、实际游戏动作与其 Blender 导入器都按版本固定。输入和输出的文件名均使用相对路径。

输入 ZIP 根目录采用以下结构。节点可预装并按哈希缓存 `fixtures`，每次迭代只换 `models`。动作 JSON 和游戏动作路径跟随 `source_commit` 对应的仓库版本，节点预装该版本的导入器。

```text
models/BaiQi_CC0_coat_on.blend
models/BaiQi_CC0_coat_off.blend
fixtures/Delta_SelfTest.blend
fixtures/sampling_report.json
fixtures/Base_Female.blend
```

| 请求 | 响应 |
|---|---|
| `GET /v1/capabilities` | `200`。返回 `schema_version`、GPU 型号与显存、Blender 版本和后端、支持的任务、参数范围、队列和文件限制。 |
| `PUT /v1/assets/{sha256}` | 上传 `application/zip` 原始字节。服务端计算并校验 SHA-256，格式为 64 个小写十六进制字符。首次上传返回 `201`，同内容已缓存返回 `200`。 |
| `POST /v1/jobs` | 提交 JSON。带 `Idempotency-Key`，重复请求返回同一个 `job_id`。返回 `202` 和 `job_id`。 |
| `GET /v1/jobs/{job_id}` | `200`。返回 `status`、已完成图数、计划图数、排队和运行时间、结构化错误以及成功时的结果哈希。 |
| `GET /v1/jobs/{job_id}/result` | 完成后返回 `200` 和 `application/zip`。结果含 PNG、各形态的 `motion_report.json`、总清单和运行日志，`Range` 续传返回 `206`。 |
| `DELETE /v1/jobs/{job_id}` | 取消排队或运行中的任务，返回 `202`。查询状态可确认取消是否结束。 |

`status` 取 `queued`、`running`、`succeeded`、`failed` 或 `cancelled`。建议私网 HTTPS 与 `Authorization: Bearer …`、单 GPU 重任务并发 1、上传上限 2 GiB、结果留存 7 天。用 `429` 和 `Retry-After` 报告队列已满，用 `422` 报告参数或哈希错误，用 `409` 报告结果未就绪或幂等键对应另一份请求。

首期 `capabilities` 可按以下结构实现。`gpu` 和 `backend` 填节点实际探测值，文件大小和显存都以字节计。`timeout_seconds` 从任务进入 `running` 开始计时。

```json
{
  "schema_version": "1",
  "gpu": {"name": "NVIDIA RTX PRO 6000D", "vram_bytes": 90194313216},
  "runtime": {"blender_version": "5.3.0", "backend": "Vulkan"},
  "kinds": ["blender_review"],
  "limits": {
    "max_upload_bytes": 2147483648,
    "max_concurrent_jobs": 1,
    "retention_seconds": 604800
  },
  "blender_review": {
    "engines": ["EEVEE"],
    "forms": ["coat_on", "coat_off"],
    "views": ["front", "back", "side", "oblique"],
    "resolution_edge_px": {"min": 128, "max": 4096},
    "samples": {"min": 1, "max": 128},
    "timeout_seconds": {"min": 30, "max": 1800}
  }
}
```

节点按 `source_commit` 使用已部署的仓库版本。同一身份的 `Idempotency-Key` 与任务 JSON 绑定，重试时返回原任务。初次受理返回 `{"job_id":"<id>","status":"queued"}`。状态响应提供 `queue_seconds`、`run_seconds` 和 `progress`，成功后补充结果大小和哈希。上传经完整校验后供任务读取，结果 ZIP 完成后才将状态标为 `succeeded`。

```json
{
  "kind": "blender_review",
  "input_sha256": "<64 lowercase hexadecimal characters>",
  "source_commit": "<git commit>",
  "params": {
    "forms": ["coat_on", "coat_off"],
    "cases": ["arms_forward", "arms_abduction", "Hun_BaiShanDual_Attack_A"],
    "sample_indices": [0, 2, 4],
    "views": ["front", "oblique"],
    "resolution": [1280, 1280],
    "samples": 32,
    "engine": "EEVEE",
    "timeout_seconds": 1800
  }
}
```

`sample_indices` 从 0 起，逐个动作校验。机位可选 `front`、`back`、`side`、`oblique`。建议节点首期开放每边 128–4096 像素和每图 1–128 个采样，服务端按 `capabilities` 返回实际范围。结果清单应写出实际参数、输入包与模型哈希、套组和代码版本、GPU 和 Blender 版本、耗时、峰值显存及文件清单。客户端可依此配对来自同一动作、姿态、视角和渲染模式的两个版本。

建议结果包用 `manifest.json`、`coat_on/motion_report.json`、`coat_off/motion_report.json` 和各形态目录下的 `samples/`。状态查询使用 `progress: {done, total}`，成功时给出 `result_sha256` 和 `result_size_bytes`，失败时给出 `error: {code, message}`。任务运行成功后，模型按动作报告和复查流程验收。

调用由节点预装并锁定版本的 `scripts/run_baiqi_cc0_motion_review.py`。用 `--render triage` 和 `--case`、`--sample-index`、`--view`、`--resolution WIDTH HEIGHT`、`--samples` 映射上述参数，两套形态各运行一次。白绮预设固定 `--neck-head-share .35 --game-hair-shadows`，每个取样点输出灰模与贴图两张。动作诊断仍记录请求动作的所有采样姿态。建议用 Blender `--disable-autoexec`，HTTP 任务只接收上表的结构化参数。

上述例子已在本地 Blender 5.3.0 验证，输出 72 张 1280×1280 的 PNG 和两份动作报告。该结果可作为节点接通后的同输入对照。
