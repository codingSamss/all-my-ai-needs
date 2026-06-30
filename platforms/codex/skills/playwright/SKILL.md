---
name: "playwright"
description: "Use only when the user explicitly asks for Playwright Extension / real-browser debugging, or when HTTP, in-app Browser, and Codex Chrome plugin cannot complete an interaction-heavy workflow. This skill requires manually enabled `playwright-ext` (`@playwright/mcp --extension`)."
---


# Playwright MCP Skill

This is not the default browser surface. For local app checks, screenshots, ordinary page inspection, or tasks that do not require the user's active Chrome session, prefer Codex `Browser` / in-app browser in the background. For tasks that need the user's Chrome login state or existing tabs, prefer the Codex Chrome plugin before Playwright.

Use Playwright as the reliable browser execution fallback in this stack:
- HTTP/API or static extraction: default first choice when it can answer the task
- Codex Browser / in-app browser: default browser surface for local pages and ordinary page inspection
- Codex Chrome plugin: logged-in Chrome profile, existing tabs, and extension-backed interaction
- `playwright-ext`: explicit fallback only after manual enablement

When this skill is deliberately selected, use a single channel only:
- Use `playwright-ext` MCP inside this skill only when `codex mcp get playwright-ext` reports it is enabled.
- Do not use `playwright-cli` wrapper in this skill.
- Do not pivot to `@playwright/test` unless the user explicitly asks for test files.

## Role In The Stack

Choose Playwright when:
- the user explicitly asks to use Playwright Extension or a real Chrome extension session.
- the Codex Chrome plugin cannot complete the action and Playwright has been manually enabled.
- the workflow is interaction-heavy and must be verified step by step.
- success depends on stable refs, precise DOM transitions, or repeated re-snapshot control.
- upstream tools already proved that a lighter layer is not reliable enough for the current task.

## Prerequisite check (required)

Before proposing browser actions, verify MCP and runtime dependency:

```bash
codex mcp get playwright-ext
command -v npx >/dev/null 2>&1
```

If `playwright-ext` is missing or disabled, do not configure or enable it unless the user explicitly asks. If they do, configure it with extension token:

```bash
codex mcp add playwright-ext \
  --env PLAYWRIGHT_MCP_EXTENSION_TOKEN=<token> \
  -- npx @playwright/mcp@latest --extension
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
- the Codex Chrome plugin has been tried or ruled out, and `playwright-ext` is enabled.

When Playwright takes over, say why it is now required and keep the flow inside Playwright until the critical interaction is verified.

## When to snapshot again

Snapshot again after:

- navigation
- clicking elements that change the UI substantially
- opening/closing modals or menus
- tab switches

Refs can go stale. When a command fails due to a missing ref, snapshot again.

## Guardrails

- Do not position Playwright as the default first hop when Codex Browser or Chrome plugin can solve the task.
- Always snapshot before referencing element ids like `e12`.
- Re-snapshot when refs seem stale.
- Prefer explicit commands over `eval` and `run-code` unless needed.
- When you do not have a fresh snapshot, use placeholder refs like `eX` and say why; do not bypass refs with `run-code`.
- State the takeover reason when inheriting a task from lighter browser paths.
- Use `--headed` when a visual check will help.
- When capturing artifacts in this repo, use `output/playwright/` and avoid introducing new top-level artifact folders.
- Default to MCP actions and workflows, not Playwright test specs.
