# pixel-buddy 本机组装与迁移

保存像素剩余额度、12px 中文标签、浅深主题场景、cache 倒计时和按会话实际阈值计算的压缩进度。
界面入口独立实现，动画采用包内 `pixel-at-work` 的 MIT 授权绘图子集。
候选版 `1.0.0-rc.19` 保留两组额度总宽 288px、原文字字号和 54px 动画高度，以 2 倍像素显示，窄窗口居中裁掉两侧景物，不换行增高。
七种状态分别显示工作室、等回信石径、整理工坊、庆祝广场、咖啡露台、休息小屋和信息亭，背景轮廓与主道具均有区别。七景的大面积底色均透明，直接透出宿主面板，不猜测或硬编码面板颜色；保留家具、道具和地面细线，避免画布形成色差框。陈设的浅蓝玻璃、深蓝玻璃与木色仍按宿主传入的 `color-scheme` 切换，不按当地钟点切换。
动画由 SVG SMIL 播放，主题切换只改变 SVG 的样式，不添加插件计时器或轮询。七景背景大多静止，工坊两侧传送带合用一组动画；角色、屏幕等只在当前场景播放。每个状态复用同一份 SVG；额度面板按分钟或实际变化更新，cache 倒计时独立更新底栏。
当前有工作、短暂庆祝、休息、空闲、压缩、等回信等待与未知任务七种场景，不覆盖原生 spinner。庆祝结束后进入咖啡露台，持续闲置约 4 分钟后转入休息小屋睡觉；这是插件的时间阶段，不是宿主提供的额外工作状态。未知任务的信息亭保持静止，不用背景运动暗示任务正在执行。基础阶段由主会话生命周期驱动；压缩直接监听主会话 `session.compact`，手动、自动与插件触发均可播放。预计算和子会话压缩不占用主画面；真正结束、跳过或失败后恢复原阶段，并读取一次 summary 更新进度。
压缩时展示原项目的压纸机：纸张压成紫色方块后移到旁边；沿用 54px 高度与昼夜配色。不主动执行压缩，不改写输入消息或压缩结果，UI 故障不阻断宿主操作，并发请求分别结束后才撤掉动画。
以宿主主会话 `isWorking` 为准：主会话工作期间始终显示工作动画，即使前台工具未返回或后台脚本 / subagent 仍在运行；主会话不工作且仍有已登记任务时才显示等回信。按任务 ID、生命周期、宿主通知与完整快照归并；通知排队可能延迟更新，脱离宿主登记的外部进程不在跟踪范围。缺失或非法快照保留已确认任务，主回复结束或中断不清除后台等待；只有明确终态或有效完整快照才清除。减弱动态效果下等待小人静止。
等回信场景中，CC 小人约 8 秒循环踮脚偷瞄、缩回眨眼、左右轻晃和安静等候；幅度仅 1–2 个逻辑像素，脚掌保持落地。邮箱口始终为空，信封图案与红旗是固定标识，不表示收信、完成比例或预计耗时；只在等待状态播放。
优先级为主会话真实压缩、主会话工作、任务等待、未知或完成/空闲；压缩结束后按主会话当前状态恢复工作或后台等待；独立计数和会话代次避免旧回调清除新状态。
同一会话热重载按会话 ID 接续已有后台记录，旧前台 Promise 不继承；启动和客户端重新连接时各补一次 `agent.list()`。此接口只包含子代理/队友，不能代表完整后台 shell 列表；空结果或读取失败不清空 shell。首次加载、进程重启或此前已经丢失的 shell 记录，需要下一份宿主完整快照才能恢复；没有可靠证据时仍显示问号，不根据历史文本猜测。身份、任务 ID、状态和顺序号仅保存在当前插件状态，不读取日志或命令内容，不增加定时轮询。
上游固定版本包含 41 种场景，当前包沿用工作、庆祝、休息、压缩与睡眠角色的绘图子集；七种地点背景、睡床、等回信等待与未知状态由本地实现。其他绘图可继续移植，数量本身不要求增加高度；接入时需分别适配明确工具事件、命令分类和结果判断，不能把动画当作测试通过的证据。当前未引入上游工具分类、步骤文案、结果正则和 300 ms 轮询。
庆祝只表示本轮正常结束且已确认没有待返回任务，不代表项目测试通过；错误、中断和子任务结束不触发庆祝。本插件与原版 `pixel-buddy@marnie-plugins` 使用不同插件标识。

底栏仍由 Desktop 放在独立一行，恢复远端紧凑数字布局，例如 `cache 57:51 52% 208k/400k`；移除像素条与分隔点，百分比按进度变色，数字为当前用量/实际生效阈值，使用 k/M 缩写。不显示“压缩”标签。
压缩分母来自宿主 `context.breakdown.autoCompactThreshold`，分子使用同份 `summary` 的 `totalTokens`，与 `/context` 的本地统计口径一致；统计含估算，阈值差值不是保证能继续输入的 token 配额。达到阈值只显示 100% 或更高读数，不宣称压缩已经执行。终端保留文字与数值提示。
不读取个人设置文件，不硬编码窗口，不用 `context.window` 或 `rawMaxTokens` 替代压缩触发阈值。原生目录与提示入口继续交由宿主管理，不新增副本。首轮没有响应读数时保留“cache / ctx 待首轮响应”，已有上下文但缓存时间未知时显示“cache 待更新”。Desktop 自动压缩关闭时显示“已关闭”，缺字段、统计未知或读取失败时显示“待更新”；不显示可能误导的 0%。终端仍保留原始 ctx 用量及完整降级说明。
仅会话启动、上下文变化、压缩结束、相关命令和开关变更后读取本地 `summary`；不使用会发 token-count 请求的 `full`，不随秒级 cache 或账号额度变化轮询。Desktop 使用紧凑文字分组，无额外图形资源；百分比向下取整，不提前显示 100%。低于 70% 为绿色、70% 起为琥珀色、90% 起为珊瑚红。当前用量/阈值随配置变更、上下文更新和压缩结束一起刷新；缩写数值含舍入，比例仍按未舍入统计计算。窄至宿主插槽限制时仍可能截断，实际 App 需新会话验收。

## 一条命令安装

在已经克隆的本仓库根目录运行：

```bash
python3 platforms/claude/mods/pixel-buddy/install.py
```

前提：Python 3.9+、已安装并支持 Mods 的 Claude Code CLI（已测试 CLI 内核 2.1.299），无需下载动画或安装 npm 依赖。
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

程序验证涵盖：剩余量与未知读数、分钟倒计时不增加账号轮询、12px 字库边界、真实压缩的开始/结束、跳过/失败/并发恢复与子会话/预计算隔离、实际压缩阈值与分级颜色、关闭/失败降级、配置刷新与旧请求隔离、主题透明底色，
以及源码/许可证哈希、并发锁、源码漂移、符号链接/路径越界、原版冲突和重复安装。
性能回归测试覆盖秒级 cache 更新不替换上方面板、重复额度不重绘、模拟一小时同状态仅 1 份宠物 SVG、
庆祝→休息→空闲和过期回调隔离。模拟计数不是真实 App 的 CPU、内存或泄漏结论。
现场性能仍需以相似任务负载持续采样；既有 Renderer 已累积的内存不会因安装文件切换立即清空。
rc.19 的等待场景已替换为邮箱；其余六景的 SVG 输出与 rc.18 逐字节一致。验证结果见 SECURITY.md；原生 App 场景切换与持续性能需现场验收，保持 candidate。
UI 必须在新的 Claude Desktop Code 本地会话验证：浅/深主题、窄宽度布局、文字不遮挡、宠物动画和独立底栏；将压缩统计与宿主 `/context` 和当前阈值核对，并在真实压缩、并行脚本和子代理等待时检查动画切换与退出。
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
运行入口仅使用宿主 session 用量及本地 summary、事件和时钟；无自发模型调用、直接文件读取、凭据读取、HTTP 请求或进程执行。summary 中的文件/工具明细不存入插件状态，只留下必要数值与压缩开关。
计时器是本地显示估算，cacheTtl 配置不改变服务端缓存；账号用量的实际查询由 Claude 宿主负责。

rc.3 动画来自 `zhuoxingzhang/pixel-at-work` 固定提交 `3fc00b3ad2ef3a57ac043f8d28e7abcbd1679a6c`，MIT 原文保留在 `hooks/scene-NOTICES.txt`。
旧 rc.1/rc.2 使用的许可未明动画不再进入新包；不清理已有设备缓存。
`LICENSE-local.txt` 只覆盖自写代码；动画/字体/图标分别保留 MIT / Public Domain / OFL notices。
发布前仍需逐文件检查及凭据/私有模式扫描。审查有范围与局限，不构成绝对安全保证。

主题继承参考：[MDN prefers-color-scheme](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@media/prefers-color-scheme)。

官方参考：[Mods reference](https://code.claude.com/docs/en/plugins/mods/reference)、
[Plugin commands](https://code.claude.com/docs/en/plugins/cli-reference)。
