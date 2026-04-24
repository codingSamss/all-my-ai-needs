# Hermes Memory Whitelist（脱敏快照）

该目录用于把 `~/.hermes/memories/` 中**明确白名单**的条目，生成脱敏快照后入仓；不做运行态 memory 全量镜像。

## 目录结构

```text
platforms/hermes/memory/
├── README.md
├── whitelist.yaml
├── redaction-rules.yaml
└── snapshots/
```

## 同步边界

- 仅支持 `local -> repo` 单向同步。
- `~/.hermes/memories/` 始终只读，不会被脚本回写。
- 同步前必须先 `check`，拿到 `plan_id + approve_token` 后再 `apply`。

## 白名单模型

`whitelist.yaml` 支持字段：

- `id`：快照 ID（唯一）
- `source_file`：源文件名（位于 `~/.hermes/memories/` 下）
- `snapshot_file`（可选）：输出文件名，默认 `<id>.md`
- `redaction_level`（可选）：`standard|strict`，默认 `standard`
- `enabled`（可选）：默认 `true`
- `description`（可选）

## 使用方式

推荐统一入口（会复用 syncctl 两阶段审批）：

```bash
./scripts/sync_hermes_memory_whitelist.sh check
./scripts/sync_hermes_memory_whitelist.sh apply --plan-id <plan_id> --approve-token <token>
```

也可直接调用：

```bash
./scripts/syncctl.sh check --direction local-to-repo --platform hermes --scope memory
./scripts/syncctl.sh apply --plan-id <plan_id> --approve-token <token>
```

## 审核建议

`check` 输出后，先审核以下清单再执行 `apply`：

- 新增快照
- 更新快照
- 跳过项（源文件缺失/规则缺失/白名单关闭）

如果 `apply` 提示源文件 hash 已变化，请重新执行 `check`，避免把 check 之后的运行态漂移直接写入仓库。
