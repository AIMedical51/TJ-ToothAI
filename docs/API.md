# API 参考

[返回项目 README](../README.md)

本文根据当前 [www/tjtooth/app.py](../www/tjtooth/app.py) 与 [qrcode-server/app.py](../qrcode-server/app.py) 整理，描述代码实际提供的接口。示例仅使用演示信息；请求成功仍取决于本机路径、服务凭据、模型访问权限和外部服务是否已配置。配置步骤及离线验证范围见 [部署说明](DEPLOYMENT.md)。接口定义经过源码核验，配置与本地报告/二维码流程已有离线回归测试；真实模型和智能体服务尚未完成端到端验证。

## 1. 服务地址与约定

| 服务 | 本地示例地址 | 入口 |
| --- | --- | --- |
| 牙齿检测与报告 | `http://localhost:5000` | [www/tjtooth/app.py](../www/tjtooth/app.py) |
| 二维码生成 | `http://localhost:16666` | [qrcode-server/app.py](../qrcode-server/app.py) |

- 两个服务是独立 Flask 应用，应分别启动。
- 当前业务接口没有实现用户登录、API 访问鉴权或报告所有者校验。后端调用外部推理和智能体服务所需的凭据由部署者配置，不应放入客户端请求或版本库。
- 上传接口使用 `multipart/form-data`；单项图片 URL 检测接口使用 `application/json`。
- 所有示例中的本地图片必须替换为真实存在、已获得使用授权的测试图片。`example.com` 图片地址仅表示请求结构，不是项目提供的测试图。
- 响应示例中的时间标识与内容均为演示值，不代表真实检测结果。
- 当前接口未统一错误格式和 HTTP 状态码，调用方应同时检查状态码、响应类型和业务字段。

### 运行配置对接口的影响

主应用通过 [runtime_config.py](../www/tjtooth/runtime_config.py) 加载仓库根目录的 `.env`，已有进程环境变量优先，不会被 `.env` 覆盖。修改配置后需要重启服务。

- 主服务默认监听 `127.0.0.1:5000`，可使用 `TJT_HOST` / `TJT_PORT` 调整。本文的 `localhost` 示例适用于本机调用；其他设备访问需使用部署地址。
- `TJT_DATA_DIR` 默认是仓库根目录下的 `var/`。输入图片、分类输出、患者信息、报告、标注图片和旧 HTML 报告分别保存在其 `inputs/`、`outputs/`、`patient_info/`、`reports/`、`annotated_images/`、`html_reports/` 子目录中，主服务加载时自动创建。相对路径按仓库根目录解析。
- 没有 `ROBOFLOW_API_KEY` 时仍可加载首页；调用推理函数会抛出明确的配置错误，并由相关接口返回 `500`。不要把缺少配置当作模型未检出。
- 没有 `TONGJI_AGENT_API_KEY` 时会跳过智能体请求，在 `debug_info.progress` 中记录原因。有检测框时仍可保存检测报告，但 `agent_response` 为空。该密钥通过后端请求头 `APIKey` 传给智能体服务，不需要添加 `Bearer` 前缀。
- `PUBLIC_BASE_URL` 可指定返回的 `report_url`、`output_url` 和旧 HTML 报告 `file_url` 使用的公开地址；未设置时根据当前请求生成绝对 URL。例如可设为 `https://example.com`。该配置不会使本地服务自动变得可从公网访问。
- `QRCODE_API_URL` 配置报告页面使用的二维码服务 URL，默认 `http://127.0.0.1:16666/v1/create-qr-code/`，由后端以 `qrcode_api_url` 模板变量传入。远程部署时应配置浏览器能够访问的地址。
- `TJT_FONT_PATH` 可指定中文标注字体；未配置或加载失败时使用系统字体回退。字体相对路径按仓库根目录解析。

完整环境变量及部署步骤见 [部署说明](DEPLOYMENT.md)。以上运行目录和配置约定适用于当前主应用，不自动改变独立实验脚本。

## 2. 单张图片综合检测

### `POST /predict`

上传一张图片，执行综合检测，返回标注图片；有检测结果时尝试生成报告。

| 表单字段 | 必需 | 说明 |
| --- | --- | --- |
| `file` | 是 | 一个图片文件；建议使用可被 OpenCV 解码的 JPG / PNG 图片 |
| `patient_data` | 是 | JSON 对象序列化后的字符串，字段见下一节 |

示例：

```bash
curl -sS -X POST 'http://localhost:5000/predict' \
  -F 'file=@/absolute/path/demo.jpg' \
  --form-string 'patient_data={"name":"演示用户","age":30,"gender":"female","ethnicity":"未填写","statement":"用于功能演示"}'
```

典型成功响应，HTTP `200`：

```json
{
  "annotated_image": "<JPEG 图片的 Base64 字符串>",
  "image_filename": "20261112_120000.jpg",
  "info_filename": "20261112_120000.json",
  "report_url": "http://localhost:5000/detection_report/20261112_120000"
}
```

- `annotated_image` 是纯 Base64 字符串，不包含 `data:image/jpeg;base64,` 前缀。网页显示时可使用 `data:image/jpeg;base64,` 加该字段作为图片 `src`。
- `image_filename` 与 `info_filename` 是服务器保存的文件名，不是可直接访问的下载 URL。
- `report_url` 仅在检测框非空、流程执行到保存报告时存在。没有该字段时，应显示图片并提示“本次没有生成报告”，不能解释为已经排除口腔疾病。
- 报告存在也不保证智能体分析文本成功生成；外部服务失败时，报告可能保留检测结果，但分析文本为空。
- 标注图片上传失败或没有可用标注图片时，智能体请求只携带检测统计和已拼接的患者字段，不会附带历史占位图片。

### `patient_data` 的实际字段

| 字段 | 建议传值 | 当前用途 |
| --- | --- | --- |
| `name` | 字符串，如 `"演示用户"` | 保存、报告展示、发送智能体 |
| `age` | 数字或可显示的字符串 | 保存、报告展示、发送智能体 |
| `gender` | `"male"` 或 `"female"` | 保存、报告展示、发送智能体；报告页面将这两个值显示为男 / 女 |
| `ethnicity` | 字符串 | 保存、报告展示、发送智能体 |
| `statement` | 字符串 | 保存并可在报告中展示；当前没有拼入智能体分析请求 |
| `diagnosis` | 字符串 | 前端录入的医生诊断与建议，会保存；当前没有拼入智能体分析请求 |
| `conclusion` | 字符串 | 前端录入的诊断结论，会保存；当前没有拼入智能体分析请求 |

后端只检查 `patient_data` 是否存在及 JSON 能否解析，没有为每个字段实现完整的类型、范围或必填校验。应提交 JSON 对象；合法 JSON 数组、数字等不属于预期输入，可能在后续处理时引发 `500`。

单图流程还会向该对象添加或覆盖 `image_filename` 和 `timestamp`，随后保存为本地 JSON。不要在其中放入无关个人信息。

### 已实现的主要错误响应

| HTTP 状态 | 条件 | `error` 示例 |
| --- | --- | --- |
| `400` | 没有 `file` 字段 | `No file uploaded` |
| `400` | 文件名为空 | `No selected file` |
| `400` | 未传 `patient_data` | `No patient data provided` |
| `400` | `patient_data` 不是有效 JSON | `Invalid patient data format` |
| `500` | 路径、图片解码、推理或其他处理异常 | 实际异常字符串 |

错误正文通常为 `{"error":"..."}`。上传非图片或空内容不会被统一转换成专用的 `400`；文件存在和文件名非空不代表图片已经通过校验。

缺少推理凭据时，相关推理入口的错误信息为：`未配置 ROBOFLOW_API_KEY，请在仓库根目录 .env 或进程环境中设置。` 外部模型请求的其他失败仍可能被统一显示为“网络波动，请重试！”。

## 3. 多张图片综合检测

### `POST /predict_multiple`

一次上传多张图片，输出每张图片的标注结果，并在有检测结果时尝试生成一份合并报告。

| 表单字段 | 必需 | 说明 |
| --- | --- | --- |
| `files` | 是 | 重复提交同名文件字段，每个字段对应一张图片 |
| `patient_data` | 是 | 与单图接口相同的 JSON 对象字符串 |

```bash
curl -sS -X POST 'http://localhost:5000/predict_multiple' \
  -F 'files=@/absolute/path/demo-front.jpg' \
  -F 'files=@/absolute/path/demo-side.jpg' \
  --form-string 'patient_data={"name":"演示用户","age":30,"gender":"female","ethnicity":"未填写","statement":"多角度图片演示"}'
```

典型成功响应，HTTP `200`：

```json
{
  "message": "Successfully processed 2 images",
  "image_count": 2,
  "batch_id": "20261112_120000",
  "info_filename": "20261112_120000_batch.json",
  "images_processed": [
    "20261112_120000_1.jpg",
    "20261112_120000_2.jpg"
  ],
  "annotated_images": [
    "<第一张 JPEG 图片的 Base64 字符串>",
    "<第二张 JPEG 图片的 Base64 字符串>"
  ],
  "report_url": "http://localhost:5000/detection_report/20261112_120000"
}
```

处理行为和边界：

1. 图片按上传顺序逐张处理，每张顺序调用两个综合检测模型；这不是并行批推理接口。
2. 合并所有图片的检测结果后，代码还会按检测框坐标去重。由于不同照片有各自的坐标系，跨照片的框可能被误判为重叠，合并数量不应直接当作经过校准的牙位或病灶总数。
3. 智能体接收合并统计结果，以及第一张标注图片作为代表图；当前没有把所有标注图都传给智能体。
4. 报告 JSON 保存全部标注图片；`annotated_images` 与输入图片顺序对应。
5. 全部图片均无检测框时，不生成 `report_url`。
6. 患者信息中会添加或覆盖 `image_filenames`、`image_count`、`timestamp` 和 `batch_id`。
7. 当前后端未设置明确的图片数量或请求大小上限，也没有逐张失败后继续处理的独立结果结构。部署者应在应用或网关补充限制；调用方宜控制批量大小。

缺少文件、出现空文件名、缺少患者信息或患者 JSON 解析失败时返回 `400`；其他处理异常通常返回 `500`。错误正文通常为 `{"error":"..."}`。

## 4. 报告查看、原始数据与打印

### `GET /detection_report/<report_id>`

返回 HTML 报告页面。`report_id` 通常为单图请求的时间标识或多图响应的 `batch_id`；优先使用检测响应返回的 `report_url`。

```text
http://localhost:5000/detection_report/20261112_120000
```

报告不存在时返回 HTTP `404` 和 `{"error":"Report not found"}`；读取或模板渲染失败时通常返回 `500` 和 `{"error":"Failed to load report"}`。

### `GET /api/detection_report/<report_id>`

返回完整报告 JSON：

```bash
curl -sS 'http://localhost:5000/api/detection_report/20261112_120000'
```

主要字段：

| 字段 | 类型 / 说明 |
| --- | --- |
| `patient_data` | 患者信息对象，包含流程添加的文件名和时间等元数据 |
| `detection_results` | **JSON 字符串**，需要再次解析后才能作为数组使用 |
| `agent_response` | 智能体分析文本，失败或无结果时可能为 `null` 或空字符串 |
| `annotated_image` | 单图报告的 JPEG Base64 字符串 |
| `annotated_images` | 多图报告的 JPEG Base64 字符串数组 |
| `image_count` | 多图报告中的图片数量 |
| `timestamp` | 本地生成的 ISO 格式时间字符串，代码未附加时区偏移 |
| `debug_info` | 智能体调用进度及返回信息，可能包含服务响应或文件位置等调试内容 |

`detection_results` 再次解析后的结构示例：

```json
[
  {"id": 1, "class_name": "示例类别", "count": 2},
  {"id": 2, "class_name": "示例类别", "count": 2}
]
```

这里每个条目对应一个检测结果，`count` 是其类别的总数，会在同类别条目中重复；不要把所有条目的 `count` 相加作为总检测数。当前该字段不输出框坐标、置信度或标准牙位编号。

报告不存在返回 `404`；读取失败通常返回 `500`。当前该接口没有报告所有者鉴权，不宜未经访问控制直接暴露个人信息和 `debug_info`。

### `GET /download_pdf/<report_id>`

该接口返回 HTTP `302`，重定向到 `/printable_report/<report_id>`，**不是 PDF 文件下载接口**。

### `GET /printable_report/<report_id>`

返回适合打印的 HTML 页面。在浏览器中打开后，使用“打印”并选择“保存为 PDF”。

```text
http://localhost:5000/printable_report/20261112_120000
```

该页面读取报告失败时返回错误提示 HTML，当前实现并未为所有失败情形设置对应的 `4xx` / `5xx` 状态，可能仍返回 HTTP `200`。

## 5. 单项图片 URL 检测

以下八个接口都接收远程图片 URL，返回标注图片的访问 URL，不生成上述患者综合报告。

| POST 路径 | 路由用途名称 | 当前模型 ID |
| --- | --- | --- |
| `/detect/dental_stain` | 牙渍检测 | `dental-stain/2` |
| `/detect/calculus` | 牙结石检测 | `teeth-disease-m1uob/1` |
| `/detect/periodontitis` | 牙周炎检测 | `dental-project-bvtip/2` |
| `/detect/caries` | 龋齿检测 | `gp-dental/2` |
| `/detect/hypodontia` | 牙齿缺失检测 | `dentalmate-v5/2` |
| `/detect/filling` | 补牙检测 | `dataset-caries/6` |
| `/detect/mega_throat_data` | 咽喉图片检测扩展 | `mega-thoart-data/1` |
| `/detect/detect_Xray` | X 光图片检测扩展 | `new-final-dataset-eqnh8/1` |

表中的用途名称依据路由命名整理，实际输出类别取决于对应模型；不能仅凭名称推断模型效果、覆盖范围或临床适用性。模型服务和访问权限也可能变化。

请求示例：

```bash
curl -sS -X POST 'http://localhost:5000/detect/caries' \
  -H 'Content-Type: application/json' \
  -d '{"image_url":"https://example.com/demo-tooth.jpg"}'
```

成功响应，HTTP `200`：

```json
{
  "output_url": "http://localhost:5000/images/caries/output_2026-11-12_12:00:00.jpg"
}
```

- 此处返回的是 JSON 对象中的 URL 字符串，不是图片二进制或 Base64。
- 访问 `output_url` 后才取得图片。输出路径中 `detection_type` 由具体路由决定，例如补牙接口使用 `detect_filling`。
- JSON 对象缺少 `image_url` 时返回 `400` 和 `{"error":"No image_url provided"}`；下载、解码或推理异常通常返回 `500` 和异常信息。
- 非 JSON 请求或非对象 JSON 不一定使用上述错误格式，可能直接由 Flask 或未捕获异常产生响应。
- 服务器主动抓取 `image_url`。当前代码未实现目标地址白名单、完整下载超时和大小限制；对外开放前应补充校验，避免抓取非预期地址。

### 图片读取接口

| GET 路径 | 返回内容 | 已知边界 |
| --- | --- | --- |
| `/images/<detection_type>/<filename>` | 分类检测图片文件 | 当前文件不存在时返回字符串 `404`，未显式设置 HTTP `404`，客户端不能只看状态码 |
| `/annotated/<filename>` | 用于报告的 JPEG 标注图片 | 无效文件名为 `400`；不存在或空文件为 `404`；不可读为 `403`；其他异常为 `500` |

`/annotated/` 成功响应设置 `Content-Type: image/jpeg`、允许跨域，并允许公共缓存一小时。涉及个人图片时，部署者应重新评估访问控制和缓存策略。

## 6. 二维码服务

### `GET /health`

```bash
curl -sS 'http://localhost:16666/health'
```

成功返回 HTTP `200`：

```json
{"status":"ok"}
```

该检查仅表示二维码 Flask 路由可响应，不检查主检测服务、模型服务或背景图是否就绪。

### `GET /v1/create-qr-code/`

将 `data` 编码为二维码。成功返回 **PNG 图片二进制**，`Content-Type: image/png`，不是 JSON 或图片 URL。

| Query 参数 | 必需 | 默认值与实际行为 |
| --- | --- | --- |
| `data` | 是 | 编码的文本或 URL；缺失或空字符串返回 `400` |
| `name` | 否 | 默认空字符串；背景图可用时，将非空姓名绘制在背景图右下角 |
| `size` | 否 | 默认 `200x200`；格式为 `宽x高`，各维被限制在 `32`～`2048`；二维码边长取较小维度 |
| `margin` | 否 | 默认 `4`；作为二维码库的边框模块数使用，处理后范围为 `0`～`32`，不是最终 PNG 的像素边距 |
| `ecc` | 否 | 默认 `M`；接受 `L` / `M` / `Q` / `H`，大小写不敏感；其他值回退到 `M` |

`size` 无法解析时回退为 `200x200`。`margin` 当前使用 `value or 4` 处理，因此显式传 `margin=0` 也会变成 `4`；负数经过范围处理可变为 `0`。文档描述的是现状，不能假定 `margin=0` 已实现无边框。

生成二维码并保存：

```bash
curl -sS --get 'http://localhost:16666/v1/create-qr-code/' \
  --data-urlencode 'data=https://example.com/demo-report' \
  --data-urlencode 'name=演示用户' \
  --data-urlencode 'size=290x290' \
  --data-urlencode 'margin=4' \
  --data-urlencode 'ecc=M' \
  --output demo-qrcode.png
```

背景与输出尺寸：

- 背景图默认使用脚本同目录的 `qrcode_background.png`，可通过进程环境变量 `QRCODE_BG_PATH` 指定；建议使用绝对路径。
- 背景图可打开时，二维码贴到背景坐标 `(130, 140)`，返回整张背景图，最终 PNG 尺寸不由 `size` 决定。
- 背景图不可打开时，服务回退为纯二维码 PNG，此时 `name` 不会绘制，输出尺寸为 `min(宽, 高)` 的正方形。
- 背景尺寸和粘贴位置固定，过大的 `size` 可能使二维码被背景边界裁切；应结合背景模板选择尺寸，并实际扫码验证。
- `name` 仅用于文字标注，不会自动追加到编码内容。二维码的内容完全由 `data` 决定。

缺少 `data` 时返回 HTTP `400` 和 `{"error":"Missing required query param: data"}`。其他二维码生成、字体或绘制异常未全部统一捕获，可能产生 Flask 的 `500` HTML 响应。

成功响应允许跨域，并设置 `Cache-Control: private, no-store`；应用已移除直接打印 `data` 和 `name` 的调试输出。报告地址和姓名仍属于 URL 查询参数，反向代理或其他访问日志可能记录它们，需要在部署层配置日志策略。

## 7. 旧接口与独立实验服务

- 主应用仍保留 `POST /generate_report` 和 `GET /view_report/<filename>`，属于旧 HTML 报告流程。生成的 HTML 保存到 `TJT_DATA_DIR/html_reports/`，成功响应的 `file_url` 指向 `/view_report/<filename>`，通过该 GET 接口读取 HTML 文件。它们与当前 `/predict` → `/detection_report/` 链路不同，旧请求结构也未统一，不建议作为新的集成入口。
- [OrificeDetection.py](../www/tjtooth/OrificeDetection.py) 的 `/upload_predict`、[CariesSegment.py](../www/tjtooth/CariesSegment.py) 的 `/caries_segment`、[appsquare.py](../www/tjtooth/appsquare.py) 的 `/square` 均由各自独立 Flask 脚本提供，不会因启动 [www/tjtooth/app.py](../www/tjtooth/app.py) 而自动挂载。
- [roboflow_usable.py](../www/tjtooth/roboflow_usable.py) 等历史脚本的接口不属于本文主应用契约。复用前需单独核对依赖、凭据、绑定地址和模型文件。

## 8. 调用方的处理建议

1. 先完成本地路径和第三方服务配置，再提交脱敏测试图片验证完整链路。
2. 对上传结果分别判断图片字段、`report_url` 和报告中的 `agent_response`，避免把 HTTP `200` 直接当作整套流程成功。
3. 展示图片时区分 Base64、图片 URL 和二维码 PNG 二进制，按对应类型读取。
4. 调用方应自行设置合理超时；后端的部分外部请求未设置超时，综合检测也可能因多图、多个模型和报告生成而较慢。
5. 错误正文可能为 JSON、纯文本或 HTML；先检查响应的 `Content-Type`，再解析内容。
6. 检测结果与 AI 报告用于项目演示和辅助参考，不能代替专业口腔检查与诊疗。
