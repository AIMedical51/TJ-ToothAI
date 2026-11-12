# 安装、启动与部署

[返回 README](../README.md) · [API 参考](API.md) · [GitHub 发布说明](GITHUB.md)

本文对应当前本地整理版本：仓库根目录包含 `www/tjtooth/` 与 `qrcode-server/`。本次配置改动只发生在本地，没有同步到正在运行的服务器。旧服务器的端口、进程管理器与反向代理规则需要在服务器上另外核实；本仓库没有导出其 Apache/Nginx 站点配置。

## 1. 两个服务及其关系

| 服务 | 入口 | 默认监听 | 用途 |
| --- | --- | --- | --- |
| 主网站 | `www/tjtooth/app.py` | `127.0.0.1:5000` | 页面、图片检测、报告、打印页面 |
| 二维码服务 | `qrcode-server/app.py` | `127.0.0.1:16666` | 报告访问二维码及背景卡片 |

两个目录都有 `app.py`，使用 `app:app` 启动时必须指定正确的工作目录。主站可以单独启动；二维码服务只影响报告二维码功能。

`www/html/index.html` 是 Apache 默认欢迎页，不是 TJ-ToothAI 首页。不要通过双击 HTML 文件或把 `www/` 当成纯静态站点来运行项目：Jinja 模板和检测 API 都需要 Flask。

## 2. 环境与依赖

建议使用独立的 **Python 3.11** 环境。当前固定的 `inference-sdk==0.37.1` 声明要求 Python `>=3.8,<3.13`，并限制 NumPy、Pillow、OpenCV 的版本；因此不能直接使用 Python 3.13/3.14 安装这套依赖。[SDK 发布元数据](https://pypi.org/project/inference-sdk/0.37.1/)

主站使用 [requirements-web.txt](../www/tjtooth/requirements-web.txt)。它只列当前 Web 入口所需的直接依赖及 Gunicorn；传递依赖由 pip 解析，并非跨平台完整锁文件。检测实际在远端执行，主流程不需要 CUDA、PyTorch 或本地模型权重。

原 [requirements_tjtoothai_env.txt](../www/tjtooth/requirements_tjtoothai_env.txt) 保留作历史服务器环境记录，其中有 `package @ file:///...` 本机构建路径、两个 OpenCV 分发包和实验脚本依赖。**不要直接把它作为新机器的安装入口。** 当前 SDK 要求 `opencv-python`，不要自行同时添加 `opencv-python-headless` 来替换它；无图形界面的 Linux 若提示缺少共享库，应先安装所缺的系统库。

以下命令以 macOS/Linux 的 Bash 或 Zsh 为例，均在仓库根目录执行。`python3.11` 需事先安装；如果独立环境里的 `python` 已是 3.11，也可使用它创建虚拟环境。

```bash
cd /path/to/tjsrc
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r www/tjtooth/requirements-web.txt
python -m pip check
```

Windows 可使用 WSL 按本文操作；原生 Windows 的虚拟环境激活方式不同，Gunicorn 命令也不适用。当前文档不声称已经验证原生 Windows 部署。

## 3. 主站配置

首次配置时复制模板；如果 `.env` 已存在，直接编辑它，避免覆盖已有设置。

```bash
cp .env.example .env
```

[runtime_config.py](../www/tjtooth/runtime_config.py) 根据自身位置定位仓库根目录并读取 `.env`。**进程环境变量优先于 `.env`**，已有环境值不会被文件覆盖。`.env` 已被 Git 忽略，示例文件中没有真实凭据。

| 变量 | 默认值/要求 | 说明 |
| --- | --- | --- |
| `ROBOFLOW_API_KEY` | 空 | 检测需要有效密钥及相应模型权限 |
| `ROBOFLOW_API_URL` | `https://detect.roboflow.com` | Roboflow 推理服务入口 |
| `TONGJI_AGENT_API_KEY` | 空 | 报告智能体凭据，按服务端 `APIKey` 请求头使用，不要自行添加 `Bearer` 前缀 |
| `TONGJI_AGENT_BASE_URL` | `https://agent.tongji.edu.cn/api/proxy` | 创建会话、聊天及 OBS 上传/下载代理的共同前缀 |
| `TONGJI_AGENT_USER_ID` | `tj-toothai` | 智能体请求使用的用户标识 |
| `TJT_DATA_DIR` | 仓库根目录的 `var/` | 图片、患者资料、报告和缓存的根目录；相对值以仓库根目录为基准 |
| `TJT_FONT_PATH` | 空 | 可选中文字体文件，未设置时尝试 Linux 系统字体 |
| `PUBLIC_BASE_URL` | 空 | 对外站点地址，如 `https://tooth.example.com`；为空时基于当前请求生成链接 |
| `QRCODE_API_URL` | `http://127.0.0.1:16666/v1/create-qr-code/` | 浏览器实际请求的二维码地址；服务器部署建议设为同源 `/v1/create-qr-code/` |
| `TJT_HOST` | `127.0.0.1` | 仅用于直接运行 `app.py` |
| `TJT_PORT` | `5000` | 仅用于直接运行 `app.py` |

没有 Roboflow 密钥时可以浏览页面，但检测会明确报配置缺失。没有智能体密钥时不会发起智能体请求，检测流程可能仍保存报告，但分析文本不会生成。仅填写任意字符串不能替代有效服务权限。

综合检测当前使用 `gp-dental/2` 和 `teeth-disease-m1uob/1`，阈值为 `0.2`。模型 ID 仍位于 `app.py`，没有提供训练数据、训练流程或自托管模型的部署包。若切换模型，需一并检查类别映射、标注和结果合并逻辑。

## 4. 启动主站

```bash
source .venv/bin/activate
python www/tjtooth/app.py
```

浏览器打开 [本地主页](http://127.0.0.1:5000/) 或 [检测页面](http://127.0.0.1:5000/caries)。主入口关闭调试模式；按 `Ctrl+C` 停止。

也可通过 Flask CLI 启动，CLI 的 host/port 参数在这种方式下决定监听地址：

```bash
python -m flask --app www/tjtooth/app.py run --host 127.0.0.1 --port 5000
```

应用初始化时自动创建以下目录，运行用户需要拥有 `TJT_DATA_DIR` 的写权限：

```text
var/
├── inputs/            # 上传的原始图片
├── outputs/           # 单项检测的标注图片
├── patient_info/      # 患者资料 JSON
├── reports/           # 综合报告 JSON
├── annotated_images/  # 给报告使用的标注图
├── html_reports/      # 旧 HTML 报告接口的产物
└── matplotlib/        # 默认 Matplotlib 缓存
```

这些目录不进入 Git。程序目前没有自动过期清理机制；删除运行数据会使对应报告或图片无法访问，应由部署者设置保留策略。

## 5. 独立启动二维码服务

新开终端，在仓库根目录创建另一套环境，避免两套服务的依赖相互影响：

```bash
cd /path/to/tjsrc
python3.11 -m venv .venv-qr
source .venv-qr/bin/activate
python -m pip install -r qrcode-server/requirements.txt
python qrcode-server/app.py
```

检查服务并生成一张不含真实身份信息的示例二维码：

```bash
curl --fail http://127.0.0.1:16666/health
curl --fail --get 'http://127.0.0.1:16666/v1/create-qr-code/' \
  --data-urlencode 'data=https://example.com/report/demo' \
  --data-urlencode 'size=290x290' \
  --output /tmp/tjtooth-report-qr.png
```

健康检查返回 `{"status":"ok"}`，二维码请求返回 PNG。默认背景来自脚本同目录的 `qrcode_background.png`；读取失败时返回纯二维码，所以健康检查成功不等于背景或字体配置成功。

二维码服务**不自动加载主站的 `.env`**。以下可选变量通过终端或进程管理器提供。自定义背景与字体请使用绝对路径；相对值会按进程当前工作目录解析：

| 变量 | 默认值/行为 |
| --- | --- |
| `QRCODE_BG_PATH` | 脚本同目录 `qrcode_background.png` |
| `QRCODE_FONT_PATH` | 优先使用指定字体，否则尝试系统中文字体与默认字体 |
| `QRCODE_HOST` | `127.0.0.1`，仅直接运行脚本时使用 |
| `QRCODE_PORT` | `16666`，仅直接运行脚本时使用 |

例如：

```bash
QRCODE_FONT_PATH=/absolute/path/to/chinese-font.ttc python qrcode-server/app.py
```

## 6. 中文字体、视频和静态资源

主站标注图片需要中文字体，二维码卡片中的中文姓名也需要。Ubuntu 可安装 `fonts-wqy-zenhei`、`fonts-noto-cjk` 等字体包；其他系统可使用有授权的 `.ttf`/`.ttc`，分别配置 `TJT_FONT_PATH` 和 `QRCODE_FONT_PATH`。字体路径应指向实际文件，不能只填写字体名称。

```bash
sudo apt-get update
sudo apt-get install fonts-wqy-zenhei fonts-noto-cjk libgl1 libglib2.0-0
```

上述是 Ubuntu 常用安装示例，应按实际发行版及缺失库调整。macOS 无需执行 `apt-get` 命令。

当前本地副本没有 MP4 视频。网页引用的可选素材包括：

```text
www/tjtooth/static/video/v_s.mp4
www/tjtooth/static/video/caries/Bass_brushing.mp4
www/tjtooth/static/video/caries/Dental_sealant.mp4
www/tjtooth/static/video/caries/Rescuing_cavities.mp4
www/tjtooth/static/video/caries/cleaning_tools.mp4
www/tjtooth/static/video/periodontitis/Periodontitis.mp4
www/tjtooth/static/video/calculus/calculus.mp4
www/tjtooth/static/video/wisdom_teeth/Wisdom_teeth.mp4
```

补充有权使用的素材后再展示视频能力。科普入口的 `static/images/science_video_qr.png` 是固定图片，域名变化后应重新生成。部分模板还引用缺失的 `owl.theme.default.min.css`、`owl.carousel.js`，个别旧脚本路径使用 `js/...`；这些会产生资源 404，属于尚待清理的前端模板问题，不能通过安装 Python 包解决。

## 7. 服务器运行示例

以下是可用于迁移的命令示例，**不是从现有服务器核实出的原启动命令**。首次迁移应使用独立目录和测试数据；本地配置整理改变了数据默认位置，不会自动搬迁服务器上的历史报告。

建议保留完整仓库层级，例如部署到 `/opt/tj-toothai/`，主程序位于 `/opt/tj-toothai/www/tjtooth/app.py`，`.env` 位于 `/opt/tj-toothai/.env`。配置模块按这套相对层级定位根目录；若只把几个文件直接覆盖到原 `/var/www/tjtooth/`，识别出的根目录将是 `/var`。这种部署方式必须另外调整布局，或通过进程环境显式提供配置及绝对 `TJT_DATA_DIR`，不能照搬本地默认值。

在仓库根目录用 Gunicorn 启动两个服务，分别交由 systemd 等进程管理器托管：

```bash
.venv/bin/gunicorn --chdir www/tjtooth --bind 127.0.0.1:5000 \
  --workers 1 --threads 1 --timeout 180 app:app

.venv-qr/bin/gunicorn --chdir qrcode-server --bind 127.0.0.1:16666 \
  --workers 2 app:app
```

主站目前使用精确到秒的文件名及共享推理客户端，建议先采用单 worker、单线程进行功能验证；此配置不提供高并发能力。外部 HTTP 调用仍缺少完整超时控制，`--timeout 180` 只是进程层的保护，不能替代请求超时、任务队列或异常恢复。

反向代理将站点主路径转发到 `127.0.0.1:5000`，将 `/v1/create-qr-code/` 转发到 `127.0.0.1:16666`。例如在你已有的 HTTPS Nginx `server` 配置中添加下列片段，域名、TLS、访问控制和上传大小需要另外配置：

```nginx
location /v1/create-qr-code/ {
    proxy_pass http://127.0.0.1:16666;
    proxy_set_header Host $host;
}

location / {
    proxy_pass http://127.0.0.1:5000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 180s;
}
```

主站配置 `PUBLIC_BASE_URL=https://你的域名`、`QRCODE_API_URL=/v1/create-qr-code/`。不要把示例 HTTP 端口直接当成完成了 HTTPS 的公网部署，也不要让 Web 服务器把 `.env`、运行数据目录或整个仓库作为静态根目录暴露。

如果继续使用 Apache/mod_wsgi，可参考 [tjtooth.wsgi](../www/tjtooth/tjtooth.wsgi)。它只负责导入同目录主应用，不再写死旧代理、Conda site-packages 和安装路径；Apache 的虚拟环境、运行用户、工作进程及站点规则需要由部署配置指定。mod_wsgi 与其 Python 解释器应使用匹配的构建，不能通过手工加入其他 Python 版本的 site-packages 来代替环境配置。

### 从旧服务器数据目录迁移

| 旧服务器路径 | 当前数据目录下的位置 |
| --- | --- |
| `/home/ubuntu/temp/inputs` | `inputs/` |
| `/home/ubuntu/temp/outputs` | `outputs/` |
| `/home/ubuntu/temp/patient_info` | `patient_info/` |
| `/home/ubuntu/temp/reports` | `reports/` |
| `/var/www/tjtooth/annotated_images` | `annotated_images/` |
| `/var/www/tjtooth/static/outputs/report` | `html_reports/` |

在备份并确认权限后，将需要保留的数据迁移到你设置的 `TJT_DATA_DIR`，而不是加入 Git。旧静态 HTML 报告 URL 与当前独立报告路由可能不同，若需保持已有链接，应在部署配置中另行设置兼容跳转。

## 8. 上线前还需解决的实际限制

当前是学习与研究展示应用：没有登录、报告所有者验证和完整的上传限制；持有报告链接的访问者可能读取报告及图片。报告标识采用时间戳，不是访问凭证。请先使用测试或脱敏数据验证，真实数据部署需要补充访问控制、输入校验、保留周期和审计机制。

图片会发送到 Roboflow；患者姓名、年龄、性别、民族和检测统计会发送给智能体，标注图会尝试上传 OBS。现有上传调用未设置有效期，下载链接包含匿名访问参数。二维码请求也携带报告地址和姓名。清理本地文件不等于删除外部服务的数据。

首页中含长期 token 的可选聊天浮窗已从本地版移除；如需恢复，必须设计合适的浏览器鉴权。旧源码中的凭据仍应由账号持有人在相应服务后台轮换，文档和本地代码修改不会自动撤销它们。

## 9. 验证顺序与常见问题

本地验证记录（2026-11-12）：在 macOS ARM64 的独立 Python 3.11.18 临时环境中成功安装两套依赖，49 个包的依赖一致性检查通过。`tests/test_local_configuration.py` 的 10 项离线回归测试全部通过，覆盖根 `.env` 与环境优先级、缺少凭据、页面渲染、图片/报告存取、打印重定向、智能体上传失败回退和二维码生成。另通过 Flask CLI 路由加载、两个 Gunicorn 入口配置检查和 Apache WSGI 导入检查。

这些检查没有启动真实模型推理或调用真实智能体，推理结果与服务响应使用模拟数据；没有验证公网 TLS、服务器反向代理、真实浏览器摄像头或临床效果。Matplotlib 与较新 pyparsing 会输出弃用提示，当前不影响这些测试通过。

部署到目标机器后，仍按以下顺序检查：

1. `python -m pip check`，确认依赖一致。
2. 先不填密钥，检查首页、`/caries`、`/science_videos` 页面及二维码 `/health`。
3. 配好自己的服务权限，用脱敏 JPG/PNG 检查单图和多图 API。
4. 检查标注中文、报告正文、浏览器打印保存 PDF。
5. 使用实际部署域名生成二维码，再用另一台设备扫码，确认报告可达。

| 现象 | 检查方向 |
| --- | --- |
| 安装提示 Python 版本不支持 | 使用 Python 3.11；不要直接套用历史环境快照 |
| `No such file` 或权限错误 | 检查 `TJT_DATA_DIR`、运行用户及字体/背景文件路径 |
| 检测提示未配置密钥 | 在根 `.env` 设置 `ROBOFLOW_API_KEY`，重启主站；历史脚本需进程环境变量 |
| “网络波动，请重试” | 也可能是密钥无效、模型无权限或响应不兼容；结合服务端错误检查 |
| 有标注图但没有 AI 文字 | 检查智能体凭据、会话/聊天接口权限及 OBS 上传链路 |
| 未返回 `report_url` | 可能没有检测框；不能据此认定没有疾病 |
| 二维码有图但没有背景或姓名 | 检查背景路径、字体；纯二维码回退不会绘制姓名 |
| 手机扫码打不开 | 不要编码另一台设备无法访问的 localhost 地址；检查公网域名/局域网网络 |
| 摄像头无法开启 | 检查权限，使用 localhost 或 HTTPS 安全上下文 |
| PDF 没有直接下载 | 当前功能打开 HTML 打印页，允许弹窗后由浏览器保存 PDF |
| 视频空白或 404 | 本地副本缺少视频资源，按模板路径补齐素材 |

摄像头的安全上下文和权限要求参见 [MDN getUserMedia 文档](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)。
