---
name: "playwright"
description: "Use when the task requires automating a real browser. This skill is MCP-only and uses `playwright-ext` (`@playwright/mcp --extension`) to attach to the browser extension session."
---


# Playwright MCP Skill

Use Playwright as the reliable browser execution layer when lighter HTTP or platform-native browser paths are not enough:
- `playwright-ext`: reliable browser execution

Use a single channel only:
- Always use `playwright-ext` MCP.
- Do not use `playwright-cli` wrapper in this skill.
- Do not pivot to `@playwright/test` unless the user explicitly asks for test files.

## Role In The Stack

Choose Playwright when:
- the workflow is interaction-heavy and must be verified step by step.
- success depends on stable refs, precise DOM transitions, or repeated re-snapshot control.
- upstream tools already proved that a lighter layer is not reliable enough for the current task.

## Prerequisite check (required)

Before proposing browser actions, verify MCP and runtime dependency:

```bash
claude mcp list | rg "playwright-ext"
command -v npx >/dev/null 2>&1
```

If `playwright-ext` is missing, have the AI merge the MCP template into `~/.claude.json`, then re-check:

```bash
claude mcp list | rg "playwright-ext"
```

If `npx` is missing, ask the user to install Node.js/npm:

```bash
node --version
npm --version
brew install node
```

## Core workflow

1. Confirm that the task truly needs reliable browser execution rather than lighter extraction or inspection layers.
2. Open the page.
3. Snapshot to get stable element refs.
4. Interact using refs from the latest snapshot.
5. Re-snapshot after navigation or significant DOM changes.
6. Verify page state after each important action.
7. Capture artifacts (screenshot, pdf, traces) when useful.

## Takeover Rules

Take over from lighter browser paths when:
- the current layer cannot prove that the intended page state change really happened.
- login/session flow, modal flow, or multi-step navigation needs strong ref discipline.
- the workflow has become complex enough that repeated browser verification is cheaper than continued fallback guessing.

When Playwright takes over, say why it is now required and keep the flow inside Playwright until the critical interaction is verified.

## When to snapshot again

Snapshot again after:

- navigation
- clicking elements that change the UI substantially
- opening/closing modals or menus
- tab switches

Refs can go stale. When a command fails due to a missing ref, snapshot again.

## Guardrails

- Do not position Playwright as the default first hop when HTTP or platform-native browser paths can solve the task more cheaply.
- Always snapshot before referencing element ids like `e12`.
- Re-snapshot when refs seem stale.
- Prefer explicit commands over `eval` and `run-code` unless needed.
- When you do not have a fresh snapshot, use placeholder refs like `eX` and say why; do not bypass refs with `run-code`.
- State the takeover reason when inheriting a task from lighter browser paths.
- Use `--headed` when a visual check will help.
- When capturing artifacts in this repo, use `output/playwright/` and avoid introducing new top-level artifact folders.
- Default to MCP actions and workflows, not Playwright test specs.
