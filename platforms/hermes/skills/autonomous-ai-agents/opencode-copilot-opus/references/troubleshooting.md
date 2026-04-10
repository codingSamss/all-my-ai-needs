# Opencode + Copilot Opus Troubleshooting

## 1) ProviderModelNotFoundError (anthropic/* unavailable)

Symptom:

```text
ProviderModelNotFoundError: providerID: "anthropic"
```

Cause:

- Current opencode credentials do not include Anthropic provider.
- You are actually using GitHub Copilot channel.

Fix:

1. List models: `opencode models | grep github-copilot`.
2. Use Copilot model id: `github-copilot/claude-opus-4.6`.
3. Check auth: `opencode auth list` should show `GitHub Copilot oauth`.

## 2) Cache EPERM / permission denied on ~/.cache/opencode

Symptom:

```text
EPERM: operation not permitted, open '~/.cache/opencode/version'
```

Fix:

- Set `XDG_CACHE_HOME=/tmp`.
- Use helper script with default safe mode.

## 3) Configuration is invalid (Unrecognized key)

Symptom:

```text
Error: Configuration is invalid ... Unrecognized key: "skills"
```

Fix:

- Temporarily bypass local config parsing:
  `XDG_CONFIG_HOME=/tmp opencode ...`
- Keep auth in `~/.local/share/opencode/auth.json`.

## 4) Keep same discussion context across rounds

Recommended order:

1. Start: `opencode run -m github-copilot/claude-opus-4.6 "..."`
2. Continue latest: `opencode run -c "补充背景..."`
3. Continue exact session: `opencode run -s <session_id> "继续..."`

## 5) Session ID retrieval

- List: `opencode session list`
- Use first `ses_*` as latest active session.
- For deterministic automation, persist session id in your task note.
