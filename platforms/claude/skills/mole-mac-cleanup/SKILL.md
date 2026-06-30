---
name: mole-mac-cleanup
description: Safely use Mole (`mo`) to scan, preview, and clean macOS disk usage. Use when Claude Code is asked to run Mole, clean Mac caches, find large files, remove project artifacts, preview app leftovers, inspect installer files, or summarize Mole cleanup candidates before any destructive cleanup.
---

# Mole Mac Cleanup

## Core Rule

Always preview before cleanup. Treat `mo clean`, `mo uninstall`, `mo purge`, `mo installer`, and `mo remove` as destructive unless they include `--dry-run`.

Do not run a destructive Mole command without explicit user confirmation in the current turn. Summarize the dry-run output first, including estimated space, categories, skipped protected/running apps, and any manual review items.

## Workflow

1. Confirm Mole is available:

```bash
command -v mo
mo --version
```

2. Pick the safest preview command:

```bash
mo clean --dry-run
mo purge --dry-run --debug
mo uninstall --dry-run
mo installer --dry-run
mo optimize --dry-run
```

3. For ad hoc disk exploration, prefer:

```bash
mo analyze
mo analyze "$HOME"
mo analyze /Volumes
```

Use `mo analyze` for exploratory cleanup because upstream documents it as safer for ad hoc cleanup: analyze-driven file removal routes through Finder Trash rather than direct deletion.

4. Review generated detail files when present:

```bash
sed -n '1,160p' "$HOME/.config/mole/clean-list.txt"
mo history
mo history --json
```

5. Only after user confirmation, run the matching non-dry-run command.

## Reporting

When reporting dry-run results, include:

- command run and whether it was dry-run
- total potential space and item count
- largest categories or paths
- skipped items and why
- manual-review candidates, especially login items, dotfiles, Docker/OrbStack data, and active browser/app state
- exact next command if the user confirms cleanup

## Safety Defaults

- Do not request sudo unless the user explicitly wants full system-level preview or cleanup.
- Do not close apps automatically; report when Mole skips running apps such as Chrome or Claude Code.
- Do not remove dotfiles, login items, app support data, Docker/OrbStack data, virtualenvs, or project artifacts without a fresh confirmation.
- Prefer Homebrew management for installation and updates:

```bash
brew install mole
brew upgrade mole
brew uninstall mole
```
