# OpenCLI 升级核对

安装、升级或排查版本差异时读取本文件；日常只读任务按 `SKILL.md` 执行。

## 2026-10-13 的评估结论

最新 npm 稳定版为 1.8.8，但功能可用不等于依赖安全通过。该版本固定依赖 `undici 7.29.0`，官方 npm 审计命中高危及其他公告；**暂缓直接安装此原始依赖组合**。上游 `main` 已调整依赖，但不能将未发布源码的修复宣称为稳定版能力。后续操作前重新核对版本及公告，不把这份日期快照当成永久结论。

评估依据：npm 包 SHA-512 与 registry integrity 一致，34 个随包发布的小红书模块及安装/包配置文件与 release tree `8271afc67e8504bda94c147f446ee29775d08274` 一致；隔离安装的 17 个包通过 registry 签名校验。依赖审计仍命中 `undici`，所以签名和完整性检查不能替代漏洞检查。

- `undici 7.29.0` 的修复版本包括 7.29.1；其中 TLS 公告仅影响使用 `BalancedPool` 且传入函数形式 TLS/连接选项的应用，不能把包版本命中等同于小红书路径已遭利用。
- 旧版依赖也要核对：`undici 6.28.0` 位于 WebSocket 公告受影响范围，6.x 对应修复版本为 6.28.1；`js-yaml <4.3.2` 命中合并键处理的拒绝服务公告。保留旧 CLI 不表示其现有依赖安全。
- 默认安装脚本会写入补全等文件，并可能删除 `~/.opencli/clis` 中的官方站点本地覆盖。升级前比较并保留本地修补；使用 `--ignore-scripts` 可跳过安装脚本，已打包 adapter 仍可直接加载。

本评估覆盖安装副作用、关键依赖、常用只读命令及风控重试边界，不是全量代码安全审计，也不能证明账号不会触发平台风控。

## 功能与版本边界

1.8.8 提供搜索排序、笔记类型、发布时间等筛选，并修复滚动结果漏采和笔记字段误取。它对 `note`、`comments`、`download` 检测到的软拦截最多冷却后重试一次；没有跨命令的统一限速。若最终仍返回风控错误，调用方必须停止批次。

用实际安装版本的帮助确认参数；不要为了筛选功能临时使用未审查的开发分支。旧版仍可使用已支持的基础只读命令，完整签名链接与批次停止规则同样适用。

## 后续升级流程

1. 在临时目录通过官方 registry 安装固定候选版本，禁用安装脚本；检查 integrity、安装脚本、运行依赖、registry 签名和官方漏洞公告。镜像缺少审计接口或公钥属于未完成，不能当作通过。
2. 核对实际依赖版本与漏洞适用条件。若稳定版锁定受影响版本，优先等待修复发布；设备本地的兼容安全补丁需保留回退副本、记录版本并单独验证，不悄悄修改上游源码。
3. 离线验证普通成功、软拦截恢复、持续拦截停止、登录墙、签名 URL 校验和只读命令声明。通过后再按用户授权更新设备依赖；不要在升级中清理本地覆盖或自动更改扩展权限。
4. 最后做有界只读烟测；若缺登录态或扩展未连接，报告边界，不切换账号或反复访问。skill 文档同步与 CLI/扩展升级分别报告。

## 来源

- [OpenCLI 1.8.8 release](https://github.com/jackwener/OpenCLI/releases/tag/v1.8.8)
- [固定版本依赖声明](https://github.com/jackwener/OpenCLI/blob/v1.8.8/package.json)
- [安装时 adapter 清理逻辑](https://github.com/jackwener/OpenCLI/blob/v1.8.8/scripts/fetch-adapters.js)
- [详情页重试实现](https://github.com/jackwener/OpenCLI/blob/v1.8.8/clis/xiaohongshu/risk-control.js)
- [Undici TLS 公告](https://github.com/nodejs/undici/security/advisories/GHSA-w293-vg96-wgc3)
- [Undici WebSocket 公告](https://github.com/nodejs/undici/security/advisories/GHSA-rfgv-xxqx-mfg5)
- [js-yaml 公告](https://github.com/advisories/GHSA-2883-xcg3-v3hh)
