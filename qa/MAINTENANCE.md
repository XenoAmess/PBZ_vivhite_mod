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

## 6000D 渲染节点 HTTP 接口提案

首期支持 `blender_review`，使用 Blender 5.3.0 的 EEVEE 跑白绮动作套组。模型文件打包贴图。动作供体 `Delta_SelfTest.blend` 及同目录 `sampling_report.json`、CC0 对照 `Base_Female.blend`、实际游戏动作与其 Blender 导入器都按版本固定。输入和输出的文件名均使用相对路径。

| 请求 | 响应 |
|---|---|
| `GET /v1/capabilities` | `200`。返回 `schema_version`、GPU 型号与显存、Blender 版本和后端、支持的任务、参数范围、队列和文件限制。 |
| `PUT /v1/assets/{sha256}` | 上传 `application/zip` 原始字节。服务端计算并校验 64 位小写十六进制 SHA-256。首次上传返回 `201`，同内容已缓存返回 `200`。 |
| `POST /v1/jobs` | 提交 JSON。带 `Idempotency-Key`，重复请求返回同一个 `job_id`。返回 `202` 和 `job_id`。 |
| `GET /v1/jobs/{job_id}` | `200`。返回 `status`、已完成图数、计划图数、排队和运行时间、结构化错误以及成功时的结果哈希。 |
| `GET /v1/jobs/{job_id}/result` | 完成后返回 `200` 和 `application/zip`。结果含 PNG、各形态的 `motion_report.json`、总清单和运行日志，支持用 `Range` 续传。 |
| `DELETE /v1/jobs/{job_id}` | 取消排队或运行中的任务，返回 `202`。查询状态可确认取消是否结束。 |

`status` 取 `queued`、`running`、`succeeded`、`failed` 或 `cancelled`。建议私网 HTTPS 与 `Authorization: Bearer …`、单 GPU 重任务并发 1、上传上限 2 GiB、结果留存 7 天。用 `429` 和 `Retry-After` 报告队列已满，用 `422` 报告参数或哈希错误，用 `409` 报告结果未就绪或幂等键对应另一份请求。

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

调用由节点预装并锁定版本的 `scripts/run_baiqi_cc0_motion_review.py`。用 `--render triage` 和 `--case`、`--sample-index`、`--view`、`--resolution WIDTH HEIGHT`、`--samples` 映射上述参数，两套形态各运行一次。白绮预设固定 `--neck-head-share .35 --game-hair-shadows`，每个取样点输出灰模与贴图两张。动作诊断仍记录请求动作的所有采样姿态。建议用 Blender `--disable-autoexec`，HTTP 任务只接收上表的结构化参数。

上述例子已在本地 Blender 5.3.0 验证，输出 72 张 1280×1280 的 PNG 和两份动作报告。该结果可作为节点接通后的同输入对照。
