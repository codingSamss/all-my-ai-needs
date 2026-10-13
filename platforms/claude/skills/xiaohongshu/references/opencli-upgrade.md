# OpenCLI 升级核对

安装、升级或排查版本差异时读取本文件；日常只读任务按 `SKILL.md` 执行。

## 2026-10-13 的评估结论

**已验证 OpenCLI 1.8.8 + 实际运行依赖 `undici 7.29.1` + `js-yaml 4.3.2` 的组合，并完成设备升级。** 官方 npm 审计在验证时为 0 条已知漏洞；17 个包的 registry 签名及 1 项发布证明通过。后续安装前仍需重新核对版本及公告，不把日期快照当成永久结论。

原版 1.8.8 固定依赖 `undici 7.29.0`，不能与上述组合混同。Undici 官方已发布 7.29.1 修复版，OpenCLI 的 `main` 也已调整依赖，但 npm 最新正式包仍为原版 1.8.8。本次保留正式版程序文件，只在设备本地替换依赖；没有安装未发布的主分支源码。

### 验证证据与边界

- 来源与完整性：npm 包 SHA-512 与 registry integrity 一致；先前已核对 34 个小红书模块及安装/包配置文件与 release tree `8271afc67e8504bda94c147f446ee29775d08274` 一致。本次隔离安装的全部 1,675 个 OpenCLI 程序文件也与官方包一致。
- 实际回归：13 项检查通过，覆盖 CLI 启动、6 个只读命令声明、5 个搜索筛选参数、正常读取、软拦截单次恢复、持续拦截停止、禁用重试、登录墙、网络错误、签名 URL、YAML 解析、本地代理绕行与 TLS 修复。部署到最终安装目录后再次通过。
- TLS 对照：仅在本机测试证书和服务上验证，7.29.0 会丢失 `BalancedPool` 的自定义校验回调；7.29.1 保留回调并按预期拒绝连接。该公告有特定调用前提，不能把依赖版本命中等同于小红书路径已遭利用。
- 安装边界：跳过安装脚本，保留旧版程序目录、依赖锁文件与验证记录以便回退。升级前确认没有本地 adapter 覆盖；浏览器、账号配置及扩展权限未修改，daemon 保持未运行。
- 未验证项：未登录账号执行小红书在线请求。本次检查不构成全量代码安全审计，也不能证明账号不会触发平台风控。

### 依赖修补的维护方式

仅运行 `opencli --version` 无法辨别原版与修补组合，应检查 CLI 实际解析到的依赖版本。上游 `package.json` 保持原样，仍声明 `undici 7.29.0`；常规依赖树检查可能因此报告版本不符，漏洞复核应以实际安装依赖及本地锁文件为准。

重装或执行 npm 全局更新可能覆盖本地修补。每次升级都重新生成并审查候选锁文件，验证通过后才替换；不要把普通 `npm install -g @jackwener/opencli@1.8.8` 当成这组已验证安装。

可在独立临时目录使用以下包装清单固定关键依赖，安装时指定官方 registry、`--omit=dev --ignore-scripts`。保留生成的 `package-lock.json` 用于复核与重复安装；这一步只准备候选，不会自动替换全局 CLI。

```json
{
  "name": "opencli-reviewed-runtime",
  "private": true,
  "dependencies": {
    "@jackwener/opencli": "1.8.8"
  },
  "overrides": {
    "@jackwener/opencli": {
      "undici": "7.29.1",
      "js-yaml": "4.3.2"
    }
  }
}
```

默认安装脚本会写入补全等文件，并可能删除 `~/.opencli/clis` 中的官方站点本地覆盖。必须先比较并保留本地修补；`--ignore-scripts` 跳过这些副作用，已打包 adapter 仍可直接加载。不要手工伪造 adapter 同步清单。

## 功能与版本边界

1.8.8 提供搜索排序、笔记类型、发布时间等筛选，并修复滚动结果漏采和笔记字段误取。它对 `note`、`comments`、`download` 检测到的软拦截最多冷却后重试一次；没有跨命令的统一限速。若最终仍返回风控错误，调用方必须停止批次。

用实际安装版本的帮助确认参数；不要为了筛选功能临时使用未审查的开发分支。旧版仍可使用已支持的基础只读命令，完整签名链接与批次停止规则同样适用。

## 后续升级流程

1. 在临时目录通过官方 registry 安装固定候选版本，禁用安装脚本；检查 integrity、安装脚本、运行依赖、registry 签名和官方漏洞公告。镜像缺少审计接口或公钥属于未完成，不能当作通过。
2. 核对实际依赖版本与漏洞适用条件。若稳定版仍锁定受影响版本，可评估同一依赖主版本内已修复的补丁组合；保留原始程序文件、锁文件和回退副本，并单独验证兼容性。未通过时暂缓升级，不能仅因签名有效就放行。
3. 离线验证普通成功、软拦截恢复、持续拦截停止、登录墙、签名 URL 校验和只读命令声明。通过后再按用户授权更新设备依赖；不要在升级中清理本地覆盖或自动更改扩展权限。
4. 最后做有界只读烟测；若缺登录态或扩展未连接，报告边界，不切换账号或反复访问。skill 文档同步与 CLI/扩展升级分别报告。

## 来源

- [OpenCLI 1.8.8 release](https://github.com/jackwener/OpenCLI/releases/tag/v1.8.8)
- [固定版本依赖声明](https://github.com/jackwener/OpenCLI/blob/v1.8.8/package.json)
- [Undici 7.29.1 安全修复发布](https://github.com/nodejs/undici/releases/tag/v7.29.1)
- [安装时 adapter 清理逻辑](https://github.com/jackwener/OpenCLI/blob/v1.8.8/scripts/fetch-adapters.js)
- [详情页重试实现](https://github.com/jackwener/OpenCLI/blob/v1.8.8/clis/xiaohongshu/risk-control.js)
- [Undici TLS 公告](https://github.com/nodejs/undici/security/advisories/GHSA-w293-vg96-wgc3)
- [Undici WebSocket 公告](https://github.com/nodejs/undici/security/advisories/GHSA-rfgv-xxqx-mfg5)
- [js-yaml 公告](https://github.com/advisories/GHSA-2883-xcg3-v3hh)
