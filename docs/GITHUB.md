# 发布到 GitHub

本文说明 [AIMedical51/TJ-ToothA](https://github.com/AIMedical51/TJ-ToothA) 的源码检查、首次发布与后续维护流程。GitHub 仓库名为 `TJ-ToothA`，项目品牌名称保留为 **TJ-ToothAI**。

获取已有仓库的源码请使用 `git clone https://github.com/AIMedical51/TJ-ToothA.git`。首次初始化与首次推送步骤仅适用于尚未接入该远程仓库的本地源码。

以下步骤以 `TJ-ToothA/` 为仓库根目录，当前主程序位于 `www/tjtooth/`，二维码服务仍位于根目录下的 `qrcode-server/`：

```text
TJ-ToothA/
├── README.md
├── .gitignore
├── docs/
├── qrcode-server/
└── www/
    ├── html/                 # 随服务器下载的 Apache 默认欢迎页
    └── tjtooth/              # Flask 主应用、模板和静态资源
```

`www/html/index.html` 是 Apache2 Ubuntu 默认欢迎页，不是 TJ-ToothAI 的产品首页；产品首页由 `www/tjtooth/app.py` 和 `www/tjtooth/templates/index.html` 提供。上面的仓库结构也不代表部署时应直接公开整个目录。

## 本地配置与公开内容的边界

- 首次使用时，仅在仓库根目录不存在 `.env` 的情况下执行 `cp .env.example .env`，再执行 `chmod 600 .env`。不要覆盖已有配置；用本地编辑器填写 `ROBOFLOW_API_KEY`、`TONGJI_AGENT_API_KEY` 等凭据，不要将其粘贴到聊天、文档或代码中。
- 可提交的 `.env.example` 仅包含空凭据字段和普通配置示例；变量名、公开服务地址和模型 ID 本身不是密钥。
- 按维护者要求，原有宣传联系方式、人物介绍、照片、固定二维码和背景图保留，不做去标识化处理。
- `.env`、含旧密钥的原始备份、证书私钥和运行时患者记录仍由忽略规则排除。不要强制添加这些文件，也不要把未经筛选的整个本地目录压缩后公开。

可以生成经过忽略规则筛选与基础密钥检查的发布包：

```bash
python3 scripts/export_public.py --check-only
python3 scripts/export_public.py
```

默认输出 `dist/TJ-ToothAI-public.zip`，包含顶层 `TJ-ToothAI/`。该脚本不会初始化实际 Git 仓库、创建远端或推送；基础规则无法识别所有可能的新凭据，后续添加文件仍需检查。

## 1. 凭据处理状态与发布前操作

服务端凭据通过外部配置提供，首页不包含长期 token 的 Coze 初始化代码。下面列出相关位置及发布时需要检查的事项：

| 文件 | 已做处理 / 当前状态 | 发布前仍需处理 |
| --- | --- | --- |
| `www/tjtooth/app.py` | Roboflow 与同济智能体凭据改为外部配置 | 在服务后台撤销或轮换旧密钥，按根 `.env.example` 和 README 配置新值 |
| `www/tjtooth/CariesSegment.py` | Roboflow key 改为 `os.environ["ROBOFLOW_API_KEY"]` | 单独启动此历史脚本时，由 shell 或进程管理器提供环境变量 |
| `www/tjtooth/roboflow_usable.py` | Roboflow key 改为 `os.environ["ROBOFLOW_API_KEY"]` | 单独启动此历史脚本时，由 shell 或进程管理器提供环境变量 |
| `www/tjtooth/templates/index.html` | 移除带有长期 token 的 Coze 初始化，不再自动启用该浮窗 | 撤销旧 token；如需恢复，另行设计受控短期鉴权 |
| `www/tjtooth/app.py.bak.20260702_184257` | 若本地存在原始备份，其可能包含旧凭据；由 `.gitignore` 排除 | 不要强制加入 Git，也不要上传或分享该备份 |

**代码外置配置不会自动撤销旧凭据。** 请自行到各服务的管理后台撤销或轮换旧密钥与 token，并在部署环境配置新值。不要将旧密钥复制到 README、Issue、终端截图或提交信息中。

主应用通过 `runtime_config.py` 自动加载根目录的 `.env`，已有进程环境变量优先，不会被 `.env` 覆盖。具体配置见根 `.env.example` 和 README；可以提交仅含空值或占位值的 `.env.example`，实际 `.env` 已被忽略。两个独立历史脚本直接使用下面的读取方式，不会自行加载 `.env`，缺少变量时会报错：

```python
import os

roboflow_api_key = os.environ["ROBOFLOW_API_KEY"]
```

独立运行历史脚本时，通过 shell、进程管理器或受控的服务端环境提供 `ROBOFLOW_API_KEY`。独立二维码服务也不会加载根 `.env`，其配置需由 shell 或 systemd 等进程管理器传入。不要把真实密钥写进可以共享的命令脚本或提交记录中。

Coze 的浏览器鉴权需要单独处理：把长期 token 放入环境变量后再渲染到 HTML，访问者仍然能读取它，不能解决泄露问题。当前未启用相关初始化；如需恢复，应按服务商当前支持的方式设计由服务端控制权限和有效期的短期鉴权流程。

上传源码不会自动更新服务器，部署时需要独立安装依赖并配置服务。外部服务的凭据撤销或轮换由账号所有者完成。真实模型推理和智能体服务需在部署环境中验证；发布前还应审查访问控制、日志、数据保存与删除、部署配置及服务权限。

## 2. 检查运行数据、资源和授权

根目录的 `.gitignore` 已排除常见虚拟环境、Python 缓存、日志、日期备份、环境文件、私钥文件、上传/输出/报告目录、部分报告文件名以及模型权重。它还排除根目录的 `var/` 运行数据，以及 `www/tjtooth/ssl/`、`ssl_old/`、`annotated_images/`、`test.png` 和 `temp_image.jpg`，并覆盖各层的 `temp/`、`logs/` 和 `nohup.out`。这些规则也适用于后续从服务器下载或运行生成的同名文件/目录。网站所需的图片、CSS、JavaScript 和二维码背景图保留在可提交范围内。

上传前仍需人工检查：

- 不要上传患者姓名、年龄、口腔照片、检测结果、报告 JSON/HTML/PDF、数据库或未经脱敏的截图。忽略规则不能判断任意文件是否包含患者信息。
- 主程序的运行目录已改为可配置的本地路径；默认运行数据放在被忽略的根 `var/` 下，具体配置见 README。若改用仓库内其他目录，应同步更新忽略规则。旧部署的 `/home/ubuntu/temp/` 等目录仍可能保存患者记录，不要随服务器文件一起打包上传。
- SSL 证书目录可能包含私钥、旧证书及部署配置，不应随源码上传；本地保留不等于允许公开。`www/tjtooth/test.png` 和 `temp_image.jpg` 按测试/临时产物排除，不影响 `static/images/` 下的网页素材。
- `www/tjtooth/static/example/`、`www/tjtooth/static/pdf/` 等目录后续若加入文件，也需检查是否含真实记录；不要假定静态目录中的内容都适合公开。
- 模型权重应确认来源和分发权限后另行提供；不要把未提供的下载地址写成可用资源。
- 检查网站图片、人物照片、视频、模板、第三方 JS/CSS、模型及关联服务的使用与再分发权限，保留适用的版权声明。
- 当前未指定统一的 `LICENSE`。选择许可证前，请确认你有权以该许可证发布项目及相关资源；公开仓库本身不等于已授予开源许可。

`.gitignore` 只影响尚未跟踪的文件，不能删除源码中的密钥，也不能清除已经提交过的秘密。如果敏感内容已进入其他仓库的历史记录，应先撤销凭据，再按 GitHub 的敏感数据清理流程处理历史；删除最新文件不足以完成清理。

## 3. 创建空的远程仓库

目标仓库为 `AIMedical51/TJ-ToothA`。如果目标仓库尚不存在，以 `AIMedical51` 账号创建名称为 `TJ-ToothA` 的仓库；如果已经存在，直接检查远程状态并使用已有仓库。公开和私有仓库都不应保存真实密钥及患者数据。

首次从本地发布时，请创建**空仓库**，不要让 GitHub 自动生成 README、`.gitignore` 或 LICENSE，因为本地已有文档。若远程已经有提交，应先拉取并整合已有内容，不要使用强制推送覆盖。

官方说明：[将本地代码添加到 GitHub](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github)。

## 4. 配置 GitHub SSH 鉴权

本项目无需保存 SSH 私钥。先检查电脑是否已经有用于 GitHub 的 SSH 配置；已有可用密钥时可以继续使用，不必创建新密钥。

如需新建，请按 [GitHub：生成 SSH 密钥并添加到 ssh-agent](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent) 操作，使用你自己确认的邮箱或标识，并选择不会覆盖已有密钥的新文件名。随后按 [GitHub：将 SSH 公钥添加到账号](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account) 添加 `.pub` 公钥；私钥不能上传到 GitHub 设置或代码仓库。

配置完成后，可在终端验证：

```bash
ssh -T git@github.com
```

首次连接时应核对 GitHub 官方公布的主机指纹后再接受。成功消息应显示你预期的 GitHub 用户名；GitHub 不提供 SSH shell，因此不要仅凭进程退出码判断鉴权是否成功。

## 5. 初始化本地仓库并审查暂存内容

以下命令以**凭据已经清理、敏感数据已经排除、资源授权已经确认**为前提。先进入项目根目录，也就是同时包含 `www/`、`qrcode-server/` 和 `docs/` 的 `TJ-ToothA/`；不要在 `www/tjtooth/` 内另建一个仓库。

```bash
cd /path/to/TJ-ToothA
git init
git branch -M main
git config --local user.name "AIMedical51"
git config --local user.email "替换为你已验证的GitHub邮箱或GitHub提供的noreply邮箱"
```

将示例路径替换为项目实际路径，邮箱占位文字也必须替换。邮箱可在 GitHub 的 Settings → Emails 查看；这里使用仓库局部配置，不修改其他项目的 Git 身份。

先检查未跟踪和被忽略的文件：

```bash
git status --short --untracked-files=all
git status --short --ignored
git check-ignore -v .DS_Store www/tjtooth/app.py.bak.20260702_184257 www/tjtooth/test.png
git check-ignore -v --stdin <<'EOF'
www/tjtooth/ssl/private.key
www/tjtooth/ssl_old/archive.pem
www/tjtooth/temp/patient_info/example.json
www/tjtooth/annotated_images/example.jpg
www/tjtooth/logs/app.log
www/tjtooth/temp_image.jpg
var/inputs/example.jpg
nohup.out
EOF
```

最后一组是用于检查规则覆盖范围的示例路径，即使文件尚不存在也可检查；命令不会创建这些文件。再检查 `git status --short --untracked-files=all`，确认主应用源码、`www/tjtooth/static/images/` 和二维码背景素材仍在可提交范围内。

确认当前源码中的真实密钥已经移除后，再将文件加入暂存区：

```bash
git add .
git diff --cached --stat
git diff --cached --name-only
git diff --cached --check
git diff --cached
```

逐项检查暂存文件列表和差异，确认没有备份、权重、私钥、患者记录或真实 token。不要把包含敏感值的差异输出公开分享。`git diff --cached --check` 只检查空白等格式问题，不能替代密钥审查。

可以额外运行下面的搜索辅助定位需要复核的文件；它只打印文件名，不打印匹配的值：

```bash
git grep --cached -l -I -E 'api_key|APIKey|apiKey|token|password|PRIVATE KEY'
```

文档、环境变量名和正常鉴权代码也可能命中；无匹配也不能保证没有秘密。需要结合代码人工确认。发现不应提交的文件时，在首次提交前从暂存区移除并完善忽略规则，例如：

```bash
git rm --cached -- path/to/unwanted-file
```

这条命令保留工作目录中的文件，只取消其暂存跟踪。不要把 `--cached` 省略。

## 6. 提交和首次推送

仅在审查通过、SSH 鉴权可用且目标远程空仓库准备好后执行。以下命令使用指定仓库 `AIMedical51/TJ-ToothA`：

```bash
git commit -m "docs: prepare TJ-ToothAI source and documentation"
git remote add origin git@github.com:AIMedical51/TJ-ToothA.git
git remote -v
git push -u origin main
```

若提示 `origin` 已存在，先用 `git remote -v` 检查其地址，不要盲目覆盖。若提示远程存在本地没有的提交，先检查并整合远端历史，不使用 `--force`。

推送后在 GitHub 检查 README 是否正常渲染、文档链接是否有效、项目静态素材是否齐全，并再次确认仓库内没有不应公开的文件。下载一份干净的源码，按 README 重新安装和配置，有助于发现依赖于本机路径或未随仓库提供的资源。
