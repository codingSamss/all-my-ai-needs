# midea-recall-diagnose

## 作用
基于回放、ELK API、ES 控制台代理 API 的 keyword 漏召回排障流程。

## 平台支持
- Claude Code
- Codex（同名 skill 语义保持一致）

## 配置命令

```bash
./setup.sh midea-recall-diagnose
```

## 验证命令

```bash
./setup.sh list
```

## 依赖
- Python 3
- Claude CLI
- 浏览器登录态 Cookie（用于 ELK / 中立云控制台 API）
- Python 包：`browser_cookie3`、`requests`、`PyYAML`
