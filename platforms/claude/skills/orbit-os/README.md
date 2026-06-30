# orbit-os

## 作用
OrbitOS Obsidian Vault 共享配置。定义 Vault 结构、格式规则、排版规范，被 orbit-* 系列独立技能引用，不直接调用。

## 平台支持
- Claude Code

## 依赖
- Obsidian（库路径: `$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/Sam's`）

## 关联技能
| 技能 | 说明 |
|------|------|
| `orbit-ai-newsletters` | AI 新闻简报摘要 |
| `orbit-ai-products` | AI 产品发布追踪 |

## 配置
```bash
./setup.sh orbit-os
```

## 验证
确认 Vault 路径下存在 `00_收件箱`、`10_日记`、`20_项目` 等目录。
