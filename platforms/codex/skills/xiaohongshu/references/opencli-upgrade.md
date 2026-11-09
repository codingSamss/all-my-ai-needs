# OpenCLI 升级核对

安装、升级或排查版本差异时读取本文件；日常只读任务按 `SKILL.md` 执行。

## 2026-11-09 的评估结论

**已验证并部署 OpenCLI 2.0.3 + 实际运行依赖 `undici 7.30.1` + `js-yaml 4.3.2`。** 官方 npm 审计在验证时为 0 条已知漏洞；18 个包的 registry 签名及 2 项发布证明通过。后续安装仍需重新核对公告，日期快照不是永久安全结论。

此前采用的 1.8.8 / `undici 7.29.1` 组合已命中新发布的依赖安全公告，不再作为安装基线。2.0.3 的正式包直接固定 `undici 7.30.1`，无需延续旧版的设备本地依赖替换。版本命中不等于具体站点读取路径已经遭到利用。

### 验证证据与边界

- 来源与完整性：npm tarball 的 SHA-512 与官方 registry integrity 一致；隔离安装的 1,585 个 OpenCLI 程序文件与官方包逐字一致，没有额外程序文件。
- 依赖与安装：通过官方 registry 隔离安装，固定 CLI 版本、禁用安装脚本，记录锁文件；实际解析的关键依赖为上述版本。保留旧程序目录和验证材料以便回退。
- 实际回归：候选与最终安装目录均通过 19 项检查，覆盖三站受管只读命令、动态 `whoami`、搜索筛选、完整签名链接、普通读取、软拦截单次恢复、持续拦截停止、禁用重试、登录墙、网络错误、互动计数未加载、JSON/YAML 输出、本地代理绕行与实际依赖版本。
- 扩展连接：候选 daemon 与现有 Chrome 扩展 1.0.27 握手成功；临时会话结束后没有遗留 lease 或 site slot，并已停止本次启动的 daemon。没有修改扩展权限或账号配置。
- 在线边界：一次后台小红书搜索返回 `AUTH_REQUIRED`，已停止，没有刷新登录或反复访问。已确认连接及登录错误处理，未证明登录后的搜索、笔记和下载全链路可用。离线用例不是线上内容读取的替代证据，也不构成全量代码安全审计或账号风控保证。

签名链接、账号标识、浏览器配置、完整日志和锁文件验证材料只保存在设备本地；公开仓库仅保留本评估摘要与可公开来源。

## 安装与回退

可在独立临时目录使用下列包装清单，避免覆盖当前可用安装：

```json
{
  "name": "opencli-reviewed-runtime",
  "private": true,
  "dependencies": {
    "@jackwener/opencli": "2.0.3"
  }
}
```

```bash
npm install --install-strategy=nested --omit=dev --ignore-scripts --no-fund --registry=https://registry.npmjs.org/
npm audit --omit=dev --registry=https://registry.npmjs.org/
npm audit signatures --registry=https://registry.npmjs.org/
```

保留生成的 `package-lock.json`。默认安装脚本会写入补全等文件，并可能清理本地官方站点 adapter 覆盖；升级前先检查并备份。`--ignore-scripts` 跳过这些副作用，已打包 adapter 仍可直接加载，不需要伪造 adapter 同步清单。

仅在候选验证通过且用户授权后替换最终安装。先保留旧程序和依赖，再切换；最终目录复验失败时恢复旧副本。检查 daemon 是否由本次任务启动，仅停止自己启动的临时实例。不要顺带改变登录态、扩展权限或浏览器配置。

`opencli --version` 只表示 CLI 版本，不能代替实际依赖检查。普通全局重装会重新解析依赖，仍需审查新锁文件和公告，不能套用旧评估结论。

## 功能与版本边界

- 2.0.3 要求 Node.js >=20.18.1、Chrome 扩展 >=1.0.27；先用 `opencli daemon status` 核对已连接扩展，不因为 CLI 更新就自动重装扩展。
- OpenCLI 2.x 默认输出和显式 `-f json` 都采用 `{ "ok": true, "data": ... }`。先检查退出码和 `ok` 再读取 `data`；`{ "ok": false, "error": ... }` 是失败，不能当成空数组。`-f yaml` 保持原始数据结构。这也适用于 Reddit 与 Bilibili 的 OpenCLI 命令。
- 搜索排序、笔记类型、发布时间等原有筛选继续可用；以实际命令 `--help` 为准。站点命令继续使用 `--window`、`--site-session`、`--keep-tab`、`--trace`；不要与 browser 命令的 `--session` 混用。
- `note`、`comments`、`download` 检测到软拦截时最多冷却后重试一次，没有跨命令统一限速。最终风控错误、登录失效、验证码或账号警告都必须停止批次，不增加外层重试。
- 上游新增的发帖、删除、关注等写操作不纳入本仓库的只读技能范围。媒体下载只写本地文件，签名 URL 与原始结果不得入仓。

## 后续升级流程

1. 在隔离目录从官方 registry 安装固定候选，禁用脚本；核对 integrity、安装脚本、运行依赖、签名与安全公告。镜像缺审计接口或公钥意味着未完成，不能当作通过。
2. 保留本地 adapter 修改与可回退副本，核对扩展兼容要求。稳定版若仍固定受影响依赖，单独评估补丁组合，不能仅凭签名放行。
3. 回归成功与错误分支、只读命令声明和输出协议；验证后再更新设备，最终安装目录需再次验证。
4. 做小范围、有界、后台只读烟测。缺登录或遇风控时停止并报告边界；技能同步、CLI 升级、扩展状态和真实内容读取分别说明。

## 来源

- [OpenCLI 2.0.3 release](https://github.com/jackwener/OpenCLI/releases/tag/v2.0.3)
- [固定版本依赖声明](https://github.com/jackwener/OpenCLI/blob/v2.0.3/package.json)
- [Undici 7.30.1 发布](https://github.com/nodejs/undici/releases/tag/v7.30.1)
- [Undici 官方安全公告](https://github.com/nodejs/undici/security/advisories)
- [安装时 adapter 清理逻辑](https://github.com/jackwener/OpenCLI/blob/v2.0.3/scripts/fetch-adapters.js)
- [详情页重试实现](https://github.com/jackwener/OpenCLI/blob/v2.0.3/clis/xiaohongshu/risk-control.js)
- [js-yaml 公告](https://github.com/advisories/GHSA-2883-xcg3-v3hh)
