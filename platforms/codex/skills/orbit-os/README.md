# orbit-os

## 作用
Obsidian 知识库的共享规范：Vault 目录结构、frontmatter 受控词表与排版规则。新建或修改知识库笔记前读取，`official-article-ingest` 等技能也会引用。

## 平台支持
- Codex

## 依赖
- Obsidian（库路径由 `$OBSIDIAN_VAULT_ROOT` 指定，本地配置注入）

## 关联技能
| 技能 | 说明 |
|------|------|
| `official-article-ingest` | 收录官方文章前读取 Vault 与排版规范 |
| `handoff` | 复用 `07_交接台` 目录与交接约定 |
| `video-transcribe` | 输出 Obsidian 笔记时遵守路径与排版规范 |

## 验证
按 `SKILL.md` 核对 `$OBSIDIAN_VAULT_ROOT` 下的全库入口与七个顶级目录：

```text
$OBSIDIAN_VAULT_ROOT/
├── 00_Home.md
├── 01_日记/
├── 02_项目/
├── 03_研究/
├── 04_知识沉淀/
├── 05_计划/
├── 06_资产/
└── 07_交接台/
```

目录编号以 `SKILL.md` 为准；策展内容归入 `04_知识沉淀`，不要另建 `05_资讯`。
