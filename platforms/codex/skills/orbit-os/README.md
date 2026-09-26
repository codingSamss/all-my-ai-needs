# orbit-os

## 作用
OrbitOS Obsidian Vault 共享配置。定义 Vault 结构、格式规则、排版规范，供 orbit-* 系列技能引用；也可在知识库相关操作中直接调用以获取 Vault 上下文。

## 平台支持
- Codex

## 依赖
- Obsidian（库路径由 `$OBSIDIAN_VAULT_ROOT` 指定，本地配置注入）

## 关联技能
| 技能 | 说明 |
|------|------|
| `orbit-ai-newsletters` | AI 新闻简报摘要 |
| `orbit-ai-products` | AI 产品发布追踪 |

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
