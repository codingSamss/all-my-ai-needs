# orbit-session-diary

把当日 Codex/Claude 会话整理为“原始会话索引”，再由助手回看关键 `jsonl` 原文并人工写入 Obsidian 日记正文。

## 入口

- Skill: `SKILL.md`
- Script: `scripts/session_diary.py`
- Excludes: `references/excludes.json`

## 快速使用

```bash
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
python3 "$CODEX_HOME/skills/orbit-session-diary/scripts/session_diary.py"
```

1. 先跑脚本拿原始会话索引（上面命令）。
2. 助手基于证据人工汇总并直接写 `01_日记/YYYY-MM/YYYY-MM-DD.md` 正文。
3. 若通过终端改动 `.md`，执行 `touch <file>` 刷新 Obsidian 感知。

正文输出建议固定为：`今日主线` + `今天做了什么` + `主题聚合（核心）` + `结果汇总` + `关联项目`。
写作前先回看关键 `jsonl`，不要用自动标签分类替代人工判断。

说明：
- `--output-mode write-auto` 仅用于维护自动附录区块，不作为正文生成方式。
- `--dry-run` 已废弃，默认行为即 evidence 模式，无需额外指定。
- 主题中出现具体知识库对象（论文/专题/栏目）时，建议补 `[[文档名]]` 或相对路径作为来源。
