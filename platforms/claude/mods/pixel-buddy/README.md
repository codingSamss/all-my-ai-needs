# pixel-buddy 本机组装与迁移

保存像素剩余额度、12px 中文标签、透明主题背景、cache 倒计时和 ctx 百分比高亮。
本仓库的界面入口独立实现；宠物动画从上游固定提交下载到设备私有缓存，不公开打包上游源码。
这是候选版 `1.0.0-rc.1`，与原版 `pixel-buddy@marnie-plugins` 使用不同插件标识。

## 一条命令安装

在已经克隆的本仓库根目录运行：

```bash
python3 platforms/claude/mods/pixel-buddy/install.py
```

前提：Python 3.9+、已安装并支持 Mods 的 Claude Code CLI（已测试内核 2.1.288），首次安装能访问 GitHub。
安装器不自动安装系统依赖、不登录账号。新设备仍需自行登录 Claude Desktop。
访问 GitHub 需要代理时，通过本机 `HTTP_PROXY` / `HTTPS_PROXY` 提供；代理地址、鉴权不保存在仓库。

安装器检查同插件安装进程、原子安装锁、已有版本及源码差异；下载一个固定文件并校验 SHA-256；
在 `~/.cache/all-my-ai-needs/mods/pixel-buddy-sam/` 生成完整插件和独立的本机 marketplace，
然后使用官方 CLI 在 user scope 安装、启用并复核文件与登记状态。
标识为 `pixel-buddy-sam@codingSamss-all-my-ai-needs-mods`。
不会写项目文件、修改 permissions/MCP/隐私设置，也不重启 App、不发送提示词、不运行 `/reload-plugins`。

原版已启用时安全停止，避免重复 UI。请在原会话任务完成后单独安排切换；本安装器不会自动禁用原版。
同版本且文件一致时再次运行直接成功；有其他版本、手工修改、异常缓存或未知目录内容时停止，不覆盖。
不使用 command-source，避免每次会话启动自动执行组装命令或触发热重载。

## 先准备或离线安装

```bash
# 只生成完整候选包，输出本机包路径；不注册市场、不改 Claude 设置
python3 platforms/claude/mods/pixel-buddy/install.py --prepare-only

# 已有经过校验的上游缓存时，不重新下载
python3 platforms/claude/mods/pixel-buddy/install.py --offline
```

`--cache-dir` 可指定设备私有缓存，但不能位于仓库内。
`--config-dir` 和 `--claude-bin` 主要用于隔离验证或非默认 CLI 安装位置；默认遵循 `CLAUDE_CONFIG_DIR` 和 PATH。
缓存或锁异常时先调查，禁止盲目删除。安装器不会清理旧版本，原来的文件和会话保持原状。

## 验证

```bash
python3 -m unittest discover -s platforms/claude/mods/pixel-buddy/tests -v
python3 platforms/claude/mods/pixel-buddy/install.py --prepare-only
# 把上一条输出的本机路径代入；不把这个绝对路径提交到仓库
claude plugin validate <PRIVATE_PLUGIN_DIR> --json
claude plugin test <PRIVATE_PLUGIN_DIR>
claude plugin list --json
```

程序验证涵盖：剩余量与未知读数、分钟倒计时不增加账号轮询、12px 字库边界、ctx 分级颜色、主题透明底色，
以及下载哈希、并发锁、源码漂移、符号链接/路径越界、原版冲突和重复安装。
UI 必须在新的 Claude Desktop Code 本地会话验证：浅/深主题、窄宽度布局、文字不遮挡、宠物动画和底栏高亮。
CLI 验证成功不等于 App 已显示；在现场验收前保持 candidate。

## 更新与回滚

上游更新不自动跟随。修改自写入口或授权资产后先审查、更新 `origin.json` 的文件哈希、增加 manifest 版本，
运行隔离验证及新会话 UI 验证后再发布。上游动画必须重新检查整个文件和依赖，修改固定提交及 SHA-256。
当前安装器遇到不同版本会停止：升级/回滚作为单独审阅的迁移操作处理，不能覆盖用户后续修改。
回滚可选择之前已审核的仓库 tag，使用新的私有缓存重建旧包，再通过官方 CLI 安排切换。
不要手写 `installed_plugins.json` 或覆盖正在使用的缓存；不自动卸载，不自动重启。

## 数据与许可边界

公开内容只含自写代码、字体/图标的授权子集和完整 notices，以及公开上游地址/固定哈希。
`origin.json` 不含本机路径、账号、PID、会话、项目、用量数据或登录状态；治理元数据不进入安装包。
安装器仅读取指定插件的启用/安装/市场登记字段，不读取 Keychain、会话历史、项目文件或认证文件。
读取进程列表仅判断安装冲突，不保存/输出命令行。下载不携带 Claude 凭据，不执行上游安装脚本。
运行入口仅使用宿主 session 用量、事件和时钟；无自发模型调用、文件读取、凭据读取、HTTP 请求或进程执行。
计时器是本地显示估算，cacheTtl 配置不改变服务端缓存；账号用量的实际查询由 Claude 宿主负责。

原始动画的许可仍未明确；其源码不入仓，下载副本只在设备本地生成，不能据此宣称获得再分发授权。
`LICENSE-local.txt` 只覆盖自写代码；字体/图标保持 MIT / Public Domain / OFL notices。
发布前仍需逐文件检查及凭据/私有模式扫描。审查有范围与局限，不构成绝对安全保证。

官方参考：[Mods reference](https://code.claude.com/docs/en/plugins/mods/reference)、
[Plugin commands](https://code.claude.com/docs/en/plugins/cli-reference)。
