# 开发者架构说明

[返回 README](../README.md) · [部署说明](DEPLOYMENT.md) · [API 参考](API.md)

本文描述当前源码的服务边界、执行顺序和数据结构，便于维护与二次开发。项目包含网页应用、远程模型调用、报告编排和独立实验脚本；当前仓库不提供完整训练平台、训练数据集或可据此推导的临床性能结论。

## 1. 两个独立 Flask 应用

| 应用 | 入口 | 默认开发地址 | 职责 |
| --- | --- | --- | --- |
| 主站 | [www/tjtooth/app.py](../www/tjtooth/app.py) | `127.0.0.1:5000` | 网页、图片检测、标注、报告存取与打印页面 |
| 二维码服务 | [qrcode-server/app.py](../qrcode-server/app.py) | `127.0.0.1:16666` | 健康检查、二维码 PNG 生成与背景合成 |

```text
浏览器 / API 调用方
  |
  +--> 主站 Flask --> 本地输入图片与患者 JSON
  |       |
  |       +--> Roboflow HTTP 推理 --> 检测框 / 中文标注
  |       |
  |       +--> 同济智能体：创建会话 --> 可选 OBS 上传 --> 生成分析文本
  |       |
  |       +--> 本地报告 JSON --> 报告网页 / 数据 API / 打印 HTML
  |
  +--> 二维码 Flask --> PNG --> 展示或保存报告链接二维码
```

主站和二维码服务不共享 Python 进程或会话状态。报告页面通过配置的二维码 URL 发起浏览器请求，二维码服务仅编码传入的文本，不读取主站报告 JSON，也不验证报告是否存在。

## 2. 页面与实际入口

| 路由 | 模板 / 作用 |
| --- | --- |
| `/` | `index.html`，项目首页；“开始检测”链接进入 `/caries` |
| `/services` | `services.html`，功能介绍与检测入口 |
| `/caries` | `caries.html`，患者表单、图片选择与检测结果交互 |
| `/about`、`/feature`、`/contact` | 项目介绍、合作伙伴与联系页面 |
| `/video`、`/science_videos` | 演示与科普页面 |
| `/detection_report/<report_id>` | `detection_report.html`，报告、图片、打印与二维码入口 |

当前 [caries.html](../www/tjtooth/templates/caries.html) 将图片作为重复的 `files` 字段提交到 `/predict_multiple`，即使只选一张图片也走多图接口。`/predict` 是另行提供的单图 API，不应混淆两者的字段名或响应结构。

前端表单提交 `name`、`gender`、`age`、`ethnicity`、`statement`、`diagnosis`、`conclusion`。后端保存整个患者对象，但并未为全部字段实现统一的数据模型、类型校验或业务校验。

## 3. 源码与函数职责

```text
tjsrc/
├── www/tjtooth/
│   ├── app.py                 # 主路由、图像处理与报告编排
│   ├── runtime_config.py      # 根 .env、运行目录与服务配置
│   ├── tjtooth.wsgi           # WSGI application 导出
│   ├── templates/            # Jinja HTML 与页面内 JavaScript
│   ├── static/               # CSS、JavaScript、图片等资源
│   └── lib/                  # 独立本地模型及历史报告代码
├── qrcode-server/app.py       # 独立二维码服务
├── docs/                     # 使用、部署、API 与架构说明
└── var/                      # 默认运行数据目录，不属于发布源码
```

| 函数 / 组件 | 主要职责 |
| --- | --- |
| `predict` / `predict_multiple` | 解析上传、保存输入、串联推理和报告、返回 JSON |
| `infer_and_annotate_for_all` | 综合模型调用、类别转换、检测框合并与标注 |
| `infer_and_annotate` | 一个指定模型的推理与标注，用于单项 URL 接口 |
| `remove_overlapping_boxes` | 按框包含关系和 IoU 去重 |
| `draw_colored_bounding_boxes` / `draw_chinese_text_on_image` | 绘制框、颜色与中文标签 |
| `generate_report_json` | 对检测框排序、统计类别、生成序列化结果、保存代表图 |
| `generate_report_with_agent` / `upload_file_to_obs` | 智能体会话、可选标注图上传与文本生成 |
| `external_url` | 按可选 `PUBLIC_BASE_URL` 构建主站绝对链接 |

## 4. 单图与多图处理顺序

单图 `/predict` 的执行顺序：

1. 检查 `file`、文件名和 `patient_data`，解析患者 JSON。
2. 生成按秒的时间标识，保存原始上传文件和患者信息。
3. 使用 OpenCV 读图，执行 `infer_and_annotate_for_all`。
4. 检测框非空时再次去重，生成检测统计和标注图片文件。
5. 尝试调用智能体，保存报告 JSON，并生成 `report_url`。
6. 将标注图片编码为 JPEG Base64，和文件名、可选报告 URL 一起返回。

多图 `/predict_multiple` 先遍历图片，逐张保存并执行同一综合检测函数，再合并检测结果、保存患者信息并尝试生成一份报告。全部图片的标注结果按上传顺序保存在 `annotated_images` 中。

两种流程都只在检测框非空时生成报告。没有 `report_url` 不代表已排除疾病；有报告也不保证智能体文本生成成功，需检查 `agent_response` 和 `debug_info.progress`。

多图流程仅把**第一张标注图片**传入报告编排作为代表图；智能体收到的是合并统计和这一张可选附件，报告 JSON 则保存全部标注图片。当前没有根据检测数量自动选择代表图。

图片和模型调用均为顺序执行。虽然每次推理使用 `ThreadPoolExecutor`，程序马上等待该任务结果，并未把两模型或多图片并行提交。每个综合模型调用后还会休眠一秒。

## 5. 模型调用与类别转换

综合检测使用 `InferenceHTTPClient`，依次调用 `gp-dental/2`、`teeth-disease-m1uob/1`，置信度阈值为 `0.2`。结果通过 `sv.Detections.from_inference` 转换，内部保存 `xyxy`、`confidence`、`class_id` 和 `data['class_name']`。

主站不导入本地 PyTorch 检测器，综合流程依赖远程服务，并不要求本地 GPU 或分割权重。单项 URL 接口的模型对应如下：

| 路由后缀（位于 `/detect/` 下） | 模型 ID |
| --- | --- |
| `dental_stain` | `dental-stain/2` |
| `calculus` | `teeth-disease-m1uob/1` |
| `periodontitis` | `dental-project-bvtip/2` |
| `caries` | `gp-dental/2` |
| `hypodontia` | `dentalmate-v5/2` |
| `filling` | `dataset-caries/6` |
| `mega_throat_data` | `mega-thoart-data/1` |
| `detect_Xray` | `new-final-dataset-eqnh8/1` |

路由名称不等于模型完整类别定义或能力证明；例如补牙路由使用的模型名仍为 `dataset-caries/6`。单项接口返回标注图片 URL，不生成患者综合报告。

综合检测将类别名转成小写后做字典精确查找，未知标签保留原字符串。映射表是显示转换，不表示模型一定会输出每一种类别：

| 英文标签 | 中文显示 |
| --- | --- |
| `caries` / `calculus` / `dental_plaque` | 龋齿 / 牙结石 / 牙菌斑 |
| `periodontitis` / `gingivitis` | 牙周炎 / 牙龈炎 |
| `gum_disease` / `periodontal_disease` | 牙龈疾病 / 牙周病 |
| `wisdom_tooth`、`wisdom_teeth` / `impacted_tooth` | 智齿 / 阻生齿 |
| `tooth_discoloration` / `dental_stain`、`tooth_stain` | 牙齿变色 / 牙齿着色 |
| `malocclusion`、`misaligned_teeth` / `crowded_teeth` | 牙列不齐 / 牙齿拥挤 |
| `tooth_gap` / `missing_tooth`、`tooth_loss` | 牙缝过大 / 牙齿缺失 |
| `dental_implant` / `crown` / `filling` / `root_canal` | 种植牙 / 牙冠 / 补牙 / 根管治疗 |

代码尝试从第二个模型中移除包含 `caries` 或“龋齿”的标签，避免与第一个模型重复；当前仅在筛选后仍有其他标签时才写回筛选结果，因此“第二模型只返回龋齿”的边界情形并未被完全过滤。

## 6. 检测框去重与结果解释

`remove_overlapping_boxes` 在包含比例达到 `0.5` 或两框 IoU 大于 `0.3` 时，移除其中面积较大的框。它没有按类别分组，也不按置信度优先保留，不能等同于经过校准的标准 NMS 或牙位匹配。

去重发生在单模型结果、同图多模型合并以及多图结果合并等位置。**多图合并后仍直接比较不同照片的坐标，可能发生跨图误去重**；当前也没有跨角度牙齿身份匹配，因此统计数不能直接解释为独立牙齿或独立病灶总数。

标注图片在模型结果合并完成前已经绘制，后续合并去重不会重新绘制所有图片。因此可见框与最终统计条目可能不完全一致。

## 7. 运行数据与持久化

`runtime_config.py` 默认以仓库根目录的 `var/` 为 `TJT_DATA_DIR`，自动创建六个子目录：

| 子目录 | 内容与读写位置 |
| --- | --- |
| `inputs/` | 上传图片及单项 URL 推理的临时输入 |
| `outputs/<detection_type>/` | 单项接口标注图，由 `/images/…` 读取 |
| `patient_info/` | 单图或批次患者 JSON，包含图片名及时间元数据 |
| `reports/` | `agent_report_<report_id>.json`，报告页面、API 与打印共用 |
| `annotated_images/` | 代表标注图，用于 OBS 上传及 `/annotated/…` 访问 |
| `html_reports/` | 旧结构化报告接口生成的 HTML，由 `/view_report/…` 读取 |

此外，Matplotlib 默认使用 `var/matplotlib/` 缓存，也可由标准变量 `MPLCONFIGDIR` 指定。持久化依赖本地文件，没有数据库事务、任务队列、报告索引或自动清理机制。

单图报告标识和多图批次标识采用 `%Y%m%d_%H%M%S`；单项输入和输出也按秒命名。**同一秒内的并发请求可能写入相同文件名，导致覆盖、混淆或报告冲突**。多图序号只区分同一批次中的图片，不能消除跨请求冲突。OBS 文件 ID 和旧 HTML 报告使用 UUID，不会反向解决主流程的命名问题。

## 8. 智能体与 OBS 调用顺序

1. 检查 `TONGJI_AGENT_API_KEY`；缺失时返回明确进度信息，不发起该流程的网络请求。
2. 向配置基址下的 `/api/v1/create_conversation` 发请求，通过 `APIKey` 请求头鉴权，取得 `AppConversationID`。
3. 拼接姓名、年龄、性别、民族与检测统计 JSON。**患者自述 `statement` 没有进入 prompt**，`diagnosis` 和 `conclusion` 也未拼入请求。
4. 有可用标注图时计算 SHA-256，向 `/up` 上传二进制，读取文件路径并构造 `/down` 下载 URL。
5. 将可用附件放入 `QueryExtends.Files`，调用 `/api/v1/chat_query_v2`，采用 `blocking` 响应模式和配置的 `UserID`。
6. 解析返回文本中的 `answer`，与调用进度一起返回上层保存。

上传失败或图片不存在时，附件列表为空，继续发送统计信息，不再附带无关历史占位图。会话或聊天失败时可能仅返回 `progress`，上层仍可保存包含检测结果的报告。

OBS 上传目前不传过期时间；代码构造的下载链接带有匿名下载参数。服务端实际保留策略和访问控制由外部服务决定，不能从本地实现推导“自动删除”或“仅本人可访问”。

## 9. 报告数据、页面与打印

`generate_report_json` 按检测框的纵坐标、横坐标排序，为每个条目写入 `id`、`class_name`、该类别的总数 `count`，再序列化为字符串。每个同类别条目重复总数，不能把这些 `count` 相加计算总检测数；该输出不包含框坐标、置信度或标准牙位编号。

报告文件包含 `patient_data`、字符串形式的 `detection_results`、`agent_response`、`timestamp`、`debug_info`。单图保存 `annotated_image`；多图保存 `annotated_images` 数组和 `image_count`，图片均为 JPEG Base64。

`/detection_report/<id>` 渲染报告模板，`/api/detection_report/<id>` 返回上述 JSON。`/download_pdf/<id>` 只是重定向到 `/printable_report/<id>`；后者生成 HTML，由浏览器打印并保存 PDF，当前主流程不调用服务端 PDF 引擎。

二维码服务将报告页面传来的 URL 编码成 PNG；背景图可用时合成卡片和可选姓名，不可用时返回纯二维码。它使用独立的 `QRCODE_BG_PATH`、`QRCODE_FONT_PATH`、`QRCODE_HOST`、`QRCODE_PORT`，不自动加载主站 `.env`，当前响应禁止持久缓存。

## 10. 配置和部署边界

[runtime_config.py](../www/tjtooth/runtime_config.py) 使用 `Path(__file__).resolve().parents[2]` 定位仓库根，以 `override=False` 加载 `.env`，保留进程环境变量优先级。配置覆盖数据目录、Roboflow 与智能体连接、公开基址、二维码地址、字体及开发监听地址；完整变量表见部署说明。

缺少 Roboflow 密钥时首页仍可加载，推理入口明确报错。`PUBLIC_BASE_URL` 用于生成绝对链接，不会自动配置域名、HTTPS、端口转发或访问权限。二维码地址必须对浏览器可达，远程部署不能照搬浏览器端的本机回环地址。

[tjtooth.wsgi](../www/tjtooth/tjtooth.wsgi) 只加入自身目录并导出 `application`，不再注入旧代理或 Conda 路径。Python 环境、进程数、反向代理与超时由部署层配置；增加工作进程前应先解决文件标识和并发写入问题。

当前代码没有完整身份鉴权、上传配额、远程 URL 白名单或统一异常协议；部分网络请求未设置超时。`future.result(timeout=30)` 也不等于整个 HTTP 请求有严格 30 秒上限。生产环境需要在应用与网关补充这些能力，不能把本地启动成功视为完成生产部署。

## 11. 历史与实验入口

| 文件 | 与当前主站的关系 |
| --- | --- |
| [OrificeDetection.py](../www/tjtooth/OrificeDetection.py) | 独立 `/upload_predict` 服务，调用本地 PyTorch 分割检测器，输入缩放到 352×352，默认 CPU 加载 |
| [CariesSegment.py](../www/tjtooth/CariesSegment.py) | 独立 `/caries_segment` 服务，使用 Roboflow SDK 的 `caries-detection-euzne/1` |
| [roboflow_usable.py](../www/tjtooth/roboflow_usable.py) | 历史单项检测与旧报告 API，不是当前网页主入口 |
| [appsquare.py](../www/tjtooth/appsquare.py) | 独立 `/square` 演示接口 |
| `addReport.py`、`lib/generate_report.py`、`rubish.py` | 历史报告实现或片段，不由当前主应用自动挂载 |

本地分割脚本要求 `lib/snapshots/240527_Net_epoch_best_official_842.pth`，当前仓库未提供该权重。该脚本及其他历史服务仍需单独检查绑定地址、相对目录和依赖；主站配置模块不自动迁移它们。启动 `www/tjtooth/app.py` 不会启动这些服务。
