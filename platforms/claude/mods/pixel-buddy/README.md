# pixel-buddy 本机组装与迁移

保存像素剩余额度、12px 中文标签、透明主题背景、cache 倒计时和 ctx 百分比高亮。
界面入口独立实现，动画采用包内 `pixel-at-work` 的 MIT 授权绘图子集。
候选版 `1.0.0-rc.12` 增加小人和沙漏等待动画。两组额度总宽维持 288px，保留图标、像素百分比、方格条和重置倒计时；动画高度维持 54px，以 2 倍像素显示，窄窗口居中裁掉两侧景物，不换行增高。
浅色主题显示太阳、云、明亮建筑与浅蓝海面，深色主题显示月亮、星星、亮窗与深色港湾；按宿主传入的 `color-scheme` 切换，不按当地钟点切换。
动画由 SVG SMIL 播放，主题切换只改变 SVG 的样式，不添加插件计时器或轮询。每个状态复用同一份 SVG；额度面板按分钟或实际变化更新，cache 倒计时独立更新底栏。
前台 Bash / Agent 调用未返回，或宿主登记的后台脚本 / subagent 尚未结束时，小人看着沙漏并轻点脚；主会话先结束也会继续等待，直到最后一个任务返回。减弱动态效果偏好下显示静止小人与沙漏，不覆盖原生 spinner。
状态来自宿主工具、代理、任务通知和完整任务快照；按任务 ID 去重并隔离过期回调，不按侧栏是否显示推断。不读取命令内容来猜进度，不新增进程查询、文件读取或接口轮询。通知排队可能延迟显示更新；脱离宿主登记的外部进程不在跟踪范围。
重载后或缺少完整任务快照时，显示灰色沙漏与问号，不冒充全部完成；下一次有效快照恢复确定状态。庆祝只表示主会话正常结束且已确认没有待返回任务，不代表项目测试通过；错误、中断和单个子任务结束不触发庆祝。本插件与原版 `pixel-buddy@marnie-plugins` 使用不同插件标识。

底栏优先使用宿主当前有效的压缩窗口：例如响应占用 155k、有效窗口 400k 时显示 `39% 155k/400k`，颜色同样按 39% 判断。
窗口来自 `session.usage({ breakdown: 'summary' })` 的 `rawMaxTokens`，由宿主处理模型级配置、环境变量和启动参数；不硬编码用户阈值，也不自行读取设置文件。
summary 只在启动和上下文变化时做本地估算；分子保留响应的实际 token，不用分类估算总量。压缩关闭、窗口缺失或无效时，显示模型窗口并标为 `ctx`。
这里的百分比表示压缩窗口占用率，不保证在 100% 才触发压缩；宿主可能预留压缩缓冲区。

右侧显示 cache 倒计时、百分比和完整 token 分母，不再带“压缩”字样。Desktop 会对整个底栏槽的长内容显示省略号；插件内部换行无法保证撑开宿主容器，因此优先缩短文案。原生目录与提示入口交由宿主管理，不新增目录副本。
Desktop 新会话页左侧的目录是环境选择器；进入已有会话后可能不显示，不能据此认定为 Mod 挤压。
首次响应前（包括提前中断）显示“cache / ctx 待首轮响应”；已有上下文但没有缓存时间时显示“cache 待更新”。未知用量不填 0，真实零用量保留 `0k`。
原生账号额度与 Mod 的用量来源不同：Mod 仅显示引擎最近响应提供的读数；未产生响应时可能仍未知。

## 一条命令安装

在已经克隆的本仓库根目录运行：

```bash
python3 platforms/claude/mods/pixel-buddy/install.py
```

前提：Python 3.9+、已安装并支持 Mods 的 Claude Code CLI（已测试 CLI 内核 2.1.295），无需下载动画或安装 npm 依赖。
安装器不自动安装系统依赖、不登录账号。新设备仍需自行登录 Claude Desktop。

安装器检查同插件安装进程、原子安装锁、已有版本及源码差异；对包内源码及许可证逐文件校验 SHA-256；
在 `~/.cache/all-my-ai-needs/mods/pixel-buddy-sam/` 生成完整插件和独立的本机 marketplace，
然后使用官方 CLI 在 user scope 安装、启用并复核文件与登记状态。
标识为 `pixel-buddy-sam@codingSamss-all-my-ai-needs-mods`。
不会写项目文件、修改 permissions/MCP/隐私设置，也不重启 App、不发送提示词、不运行 `/reload-plugins`。

原版已启用时安全停止，避免重复 UI。首次从原版迁移时，先完成下方验证，再在已授权的切换窗口通过官方 CLI 操作：

```bash
claude plugin disable pixel-buddy@marnie-plugins --scope user --json
python3 platforms/claude/mods/pixel-buddy/install.py
```

旧插件及定制文件保留，不覆盖其缓存；安装器不会自动禁用原版。旧会话可能继续运行已加载的旧代码，
需在任务结束后用新本地 Code 会话或显式 `/reload-plugins` 确认新版；不能把配置启用当作实际加载。
如果安装失败或需要恢复，通过官方 CLI 禁用 `pixel-buddy-sam@codingSamss-all-my-ai-needs-mods`（若已启用），
再启用 `pixel-buddy@marnie-plugins`；不要同时启用两版。
同版本且文件一致时再次运行直接成功；有其他版本、手工修改、异常缓存或未知目录内容时停止，不覆盖。
不使用 command-source，避免每次会话启动自动执行组装命令或触发热重载。

## 先准备或离线安装

```bash
# 只生成完整候选包，输出本机包路径；不注册市场、不改 Claude 设置
python3 platforms/claude/mods/pixel-buddy/install.py --prepare-only

# 兼容旧命令；当前版本的源码组装默认即为离线
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
以及源码/许可证哈希、并发锁、源码漂移、符号链接/路径越界、原版冲突和重复安装。
性能回归测试覆盖秒级 cache 更新不替换上方面板、重复额度不重绘、模拟一小时同状态仅 1 份宠物 SVG、
庆祝→休息→空闲和过期回调隔离。模拟计数不是真实 App 的 CPU、内存或泄漏结论。
现场性能仍需以相似任务负载持续采样；既有 Renderer 已累积的内存不会因安装文件切换立即清空。
rc.12 的 36 项 SDK 测试与 13 项安装器测试通过。新增覆盖前台脚本、后台脚本与 subagent 并行、重复/乱序通知、停止失败、未知快照与重载旧回调隔离；事件由 SDK 测试环境模拟，不等同于原生 App 的真实任务验收。
原生 App 已确认有效窗口读数为 400k，比例按该窗口计算，rc.10 的精简文案与完整分母已确认显示。rc.12 等待动画的真实脚本/subagent 现场验收仍需空闲会话加载；运行中不重载。
此前 rc.6 已在正常宽度与文件侧栏收窄布局下确认等待文案完整；真实数字现场验收暴露了宿主省略问题，不能用结构断言替代截图。
完整 UI 仍需在 Claude Desktop Code 本地会话验证：浅/深主题、窄宽度布局、文字不遮挡、宠物动画和底栏高亮。
CLI 验证成功不等于 App 已显示；在现场验收前保持 candidate。

## 更新与回滚

上游更新不自动跟随。修改自写入口或授权资产后先审查、更新 `origin.json` 的文件哈希、增加 manifest 版本，
运行隔离验证及新会话 UI 验证后再发布。更新绘图子集时必须复核选入代码、来源和 MIT notice，更新固定提交及 SHA-256。
当前安装器遇到不同版本会停止：升级/回滚作为单独审阅的迁移操作处理，不能覆盖用户后续修改。
确认旧版本文件无漂移后，在安装锁内组装并发布新本地 catalog，再执行官方 `claude plugin marketplace update` 和 `claude plugin update <PLUGIN_ID> --scope user`；旧版本缓存保留。
回滚可选择之前已审核的仓库 tag，使用新的私有缓存重建旧包，再通过官方 CLI 安排切换。
不要手写 `installed_plugins.json` 或覆盖正在使用的缓存；不自动卸载，不自动重启。

## 数据与许可边界

公开内容只含自写代码、动画/字体/图标的授权子集和完整 notices，以及公开上游地址/固定哈希。
`origin.json` 不含本机路径、账号、PID、会话、项目、用量数据或登录状态；治理元数据不进入安装包。
安装器仅读取指定插件的启用/安装/市场登记字段，不读取 Keychain、会话历史、项目文件或认证文件。
读取进程列表仅判断安装冲突，不保存/输出命令行。组装不访问网络，不执行上游安装脚本。
运行入口仅使用宿主 session 用量、事件和时钟；无自发模型调用、文件读取、凭据读取、HTTP 请求或进程执行。
计时器是本地显示估算，cacheTtl 配置不改变服务端缓存；账号用量的实际查询由 Claude 宿主负责。

rc.3 动画来自 `zhuoxingzhang/pixel-at-work` 固定提交 `3fc00b3ad2ef3a57ac043f8d28e7abcbd1679a6c`，MIT 原文保留在 `hooks/scene-NOTICES.txt`。
旧 rc.1/rc.2 使用的许可未明动画不再进入新包；不清理已有设备缓存。
`LICENSE-local.txt` 只覆盖自写代码；动画/字体/图标分别保留 MIT / Public Domain / OFL notices。
发布前仍需逐文件检查及凭据/私有模式扫描。审查有范围与局限，不构成绝对安全保证。

主题继承参考：[MDN prefers-color-scheme](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@media/prefers-color-scheme)。

官方参考：[Mods reference](https://code.claude.com/docs/en/plugins/mods/reference)、
[Plugin commands](https://code.claude.com/docs/en/plugins/cli-reference)。
