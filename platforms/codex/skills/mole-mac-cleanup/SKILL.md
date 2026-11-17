---
name: mole-mac-cleanup
description: Safely operate the installed Mole CLI (`mo`) on macOS using machine-readable status, analysis, history, and dry-run surfaces. Use when Codex is asked to inspect Mac disk, CPU, memory, or network usage; find large files; preview or perform cleanup; preview universal-app slimming; remove apps, installers, or project artifacts; diagnose Mole results; or check and upgrade Mole.
---

# Mole Mac Cleanup

Use the official `tw93/Mole/skills/mole/SKILL.md` and its `references/macos.md` at the release pinned in repo-only `runtime.yaml` as the command-semantics baseline. This skill covers macOS; do not reuse flags or JSON fields from the Windows edition. The audited release is 1.71.0, but an installed binary may be older: check `mo --version` and `mo <command> --help` before using a new command or flag. A skill update does not upgrade Mole.

## Safety Contract

1. Always preview before deletion. Run the matching `--dry-run`, inspect its candidates, summarize the impact, and obtain explicit user confirmation in the current turn before running the destructive command.
2. Treat `clean`, `uninstall`, `purge`, `installer`, `optimize`, and app replacement by `slim` as destructive. Treat installation, `update`, `remove`, and whitelist changes as state-changing and require an explicit request.
3. Never parse or act from a TUI frame. Use JSON surfaces where available. Real `uninstall`, `installer`, and `slim` runs, selection lists, and whitelist editors belong in the user's own terminal. Do not create a pseudo-terminal or feed confirmation keys to bypass this boundary.
4. Never invent flags. Run `mo <command> --help` when the documented surface is insufficient.
5. Preserve Mole's safety layer. Follow the whitelist procedure below for protected paths; never replace Mole with raw `rm`, hand-written recursive deletion, or broad globs. Do not retry a skipped or protected removal by changing tools.
6. Never run `sudo`, supply an administrator password, or create an elevated session. Hand steps needing new administrator authorization to the user's terminal. Closing applications, removing login items or dotfiles, pruning Docker/OrbStack, and deleting virtualenvs or project artifacts require separate confirmation of that exact scope.
7. Bound long scans and watches. Send progress updates, stop low-value scans that remain silent, and never leave `mo status --watch` running in the background.

## Establish the Runtime

Confirm the binary, version, and real package manager:

```bash
command -v mo
mo --version
brew list --versions mole
brew info mole --json=v2
```

Do not trust the `Install:` line from `mo --version` alone; a Homebrew-managed build can report `Manual`. If `brew list --versions mole` succeeds, manage it with Homebrew. If Mole is missing or a command is unsupported, report that and offer the appropriate install or upgrade; do not install or upgrade as a side effect of diagnosis. Older builds may lack `slim`, `--with-data`, or newer JSON fields, so use only the installed version's supported surfaces.

## Choose the Surface

| User intent | Agent-facing command |
|---|---|
| Explain disk usage | `mo analyze --json` or `mo analyze --json <path>` |
| Preview safe cleanup | `mo clean --dry-run` |
| List installed apps with exact uninstall names | `mo uninstall --list` |
| Preview removal of one app | `mo uninstall --list` to read the exact name, then `mo uninstall --dry-run <app>` |
| Preview bounded maintenance | `mo optimize --dry-run` |
| Preview old project artifacts | `mo purge --dry-run` |
| Preview downloaded installers | `mo installer --dry-run` |
| Preview universal-app slimming on Apple Silicon | `mo slim --dry-run`, only if installed help supports it |
| Audit prior cleanup | `mo history --json --limit 20` |
| Capture one health snapshot | `mo status --json` |
| Capture a short time series | `mo status --watch --interval 1s` |

Interactive `analyze`, terminal-attached `status`, app selectors, and installer selectors are human surfaces. Prefer the commands above. If a dry-run still opens a selector, stop and give the user the command to run themselves.

Real runs of `mo clean` and `mo optimize` start immediately without a terminal. Both can use a cached sudo session for system tasks, so the lack of a password prompt does not restrict the run to user files. Obtain consent before invoking either. Without cached authorization, system tasks are skipped. If the preview needs administrator access, agree on a user-level run or a full run in the user's terminal before proceeding. Proceed with user-level cleanup only if the command can stay within that approved scope. Do not schedule two overlapping cleanup runs.

In 1.62.0+, `mo uninstall --dry-run <app>` ends successfully after the plan. Older versions can print the plan and exit 1 with `Uninstall confirmation needs an interactive terminal`; that message alone is not evidence of deletion. A real uninstall still requires the user's terminal.

## Machine-Readable Evidence

### Disk analysis

`mo analyze --json` returns `scan_status`, `path`, `overview`, `total_size`, optional `total_files` / `large_files[]`, and `entries[]`. Entries include `scan_status`, `name`, `path`, `size`, `is_dir`, and optional `insight`, `cleanable`, and `last_access`. Sizes are bytes. Preserve `complete`, `partial`, and `unavailable`: a partial size is a lower bound, an unavailable size is unknown rather than zero, and a field absent from an older binary must not be inferred. Keep `--json` before the path because flag parsing stops at the first positional argument. Scope expensive scans when possible, for example:

```bash
mo analyze --json "$HOME/Library"
```

Map `cleanable: true` caches and leftovers of removed apps to `clean`, project artifacts to `purge`, and installed apps to `uninstall`. Report documents, media, virtual machines, and backups as user data; their size alone does not make them cleanup candidates. Treat reclaimable-space estimates as estimates, especially with APFS shared blocks, sparse files, or hardlinks.

### Cleanup candidates

`mo clean --dry-run` prints a summary and writes the candidate paths to:

```text
~/.config/mole/clean-list.txt
```

Read that file to review the paths this dry-run found. It is a preview snapshot, not an executable deletion plan: a later `mo clean` rescans and revalidates current candidates, so the two target sets can differ. Never promise the user that the real run will remove exactly this list. `purge --dry-run` and `installer --dry-run` report their candidates in the terminal and do not write this list.

### Cleanup history

`mo history --json --limit N` (N is 1-200) returns `logs`, `sessions[]`, and `deletions[]`. Use `actions.removed`, `trashed`, `skipped`, and `failed` to verify the outcome. When `failed` is nonzero, inspect only the matching session in the operations log and classify permission-protected or running-app paths separately from real cleanup failures.

In Mole 1.59.0+, each session includes an opaque `run_id` and an `attribution`: `run` identifies one run, `command` groups older command-based records, and `ambiguous` means older markers cannot distinguish interrupted or overlapping runs. Do not assign ambiguous counts to one run. An empty `run_id` means no identity was logged; an empty `ended_at` means no end marker was recorded, not confirmed completion. Each deletion records `timestamp`, `mode`, `status`, `size_kb`, and `path`; control bytes in paths appear as `\n`, `\r`, `\t`, or `\xHH`.

For a missing-file investigation, match the exact path, deleted ancestor directories, and records beneath the directory being investigated; use path-component boundaries rather than a raw text prefix. A removal may be logged at either directory or file level. `status: ok` is a completed removal and `dry-run` is a preview. Read the deletion log named in `logs` when the returned history does not cover the requested date. No match means no matching record was found, not proof that Mole did not touch the file.

### Installed apps

`mo uninstall --list` prints the app inventory as a JSON array when stdout is not a TTY. Each entry has `name`, `bundle_id`, `source`, `uninstall_name`, `path`, and `size`. Read `uninstall_name` for the exact argument `mo uninstall` accepts, so the app selector TUI never has to be opened.

```bash
mo uninstall --list
```

### System status

Use `mo status --json` for a single CPU, memory, disk, and network snapshot. `mo status --watch --interval 1s` emits NDJSON; collect only the number of samples needed, then terminate it.

## Command Notes

- `mo clean` permanently removes caches and also sweeps evidence-backed leftovers from already-uninstalled apps. It does not uninstall an installed app. It normally empties `~/.Trash` unless that row is protected by the clean whitelist. Mention the Trash scope in every clean preview. Mole 1.71.0 preserves Puppeteer-managed browsers and Buzz models.
- In 1.71.0, `mo uninstall` keeps personal data such as Buzz models by default and moves the app plus selected leftovers to Trash. Review the `Personal data kept` list before proposing any data removal. `--with-data` preselects eligible personal data while holding back protected browser profiles, shared app-group containers, game libraries, and UTM and VirtualBuddy virtual machines. Let the user choose in their terminal. macOS-protected containers are skipped. Without Full Disk Access, treat unmeasured container sizes as unknown. Older versions differ, so rely on their help and preview. Offer `--permanent` only when the user explicitly asks to bypass Trash.
- `mo clean --external <path>` cleans `.DS_Store`, AppleDouble `._*`, and `.TemporaryItems` from a mounted external volume, not its Trash. Resolve and show the exact mounted path, preview with `--dry-run`, then obtain confirmation.
- In current upstream Mole, `mo purge` targets both local build output (`target/`, `build/`, `dist/`, `.next/`) and dependency directories that require a network to restore (`node_modules/`, `Pods/`, `venv/`, `vendor/`). A purge is therefore not always recoverable offline: classify the dry-run candidates by recovery type and show that distinction before requesting confirmation. Add `--include-empty` to surface zero-size candidates. A non-interactive real run requires an explicit `--yes`; dry-run does not. Use `--yes` only after the user has authorized removal in the current turn. Artifacts with authored content stay protected, and an inconclusive content probe keeps the candidate and reports an incomplete run. `mo purge --paths` opens an interactive editor for the scan directories; it is a human surface, so report that the user has to edit it themselves instead of entering it.
- `mo purge` accepts no positional project path. `--yes` covers every eligible candidate, not a project selected by the agent; for a subset, give the user `mo purge` to choose in their terminal. Recent or unverifiable activity, cloud-synced folders, and safety exclusions can leave previewed candidates untouched. In 1.71.0, open files and active builds also protect artifacts. A Swift package `.build` directory containing dependencies contributes only compiler output. A valid scan-root configuration with no active paths falls back to the default roots, so review the effective scope before approval.
- `mo slim` is for Apple Silicon and removes Intel code from eligible universal apps. It works on a copy, verifies code signing and Gatekeeper, then moves the original to Trash before replacement. Running apps and protected signatures can be skipped, and app updates restore the Intel code. The agent may preview; the user makes the selection and runs the replacement in their own terminal.
- `mo optimize` refreshes caches and system services rather than only deleting files. Explain the planned effects before requesting approval.
- Use `--debug` only to diagnose a command that did nothing or failed; normal runs should stay concise.

## Protecting a Path

Use Mole's own whitelist format. Clean protections live in `~/.config/mole/whitelist`; optimize protections live in `~/.config/mole/whitelist_optimize`. A saved file replaces optional defaults, while built-in safety protections remain enforced. Do not create a new file containing only the requested path: have the user initialize the matching whitelist editor and save the defaults first. If it still does not exist, stop and report that.

After an explicit protection request, an existing readable file may be updated by adding the exact path while preserving every existing entry. `~` and `$HOME` expand, `#` begins a comment, and paths containing `..` are rejected. Verify the change with the matching dry-run; for `clean`, inspect `clean-list.txt` for the exact path, descendants, and any ancestor removal that could cover it before claiming the scope is protected. If a whitelist or `purge_paths` file is unreadable or invalid, stop and keep the original file for review.

## Upgrade Mole

If Homebrew manages Mole, check that `brew info mole --json=v2` offers the reviewed release. Keep the previous keg available for rollback:

```bash
HOMEBREW_NO_INSTALL_CLEANUP=1 brew upgrade mole
```

Otherwise, upstream provides `mo update`. `mo update --nightly` installs unreleased `main`; never run it unless the user explicitly requests nightly. After any upgrade, verify the installed version and run a non-destructive smoke test:

```bash
mo --version
mo analyze --json "<small_test_directory>"
mo history --json --limit 1
mo clean --dry-run
```

If a bounded full-disk preview times out, retain its log and report the unvisited scope as unverified.

## Report and Verify

Before cleanup, report the command, potential bytes/items, largest categories, exact risky paths, protected/running-app skips, and the proposed real command. After an approved cleanup:

1. Compare free space before and after.
2. Read `mo history --json --limit 1`.
3. Explain nonzero `failed` and important `skipped` counts. Keep partial or unavailable results visible, and do not retry skipped removals or escalate privileges automatically.
4. Verify separately protected paths still exist when the dry-run surfaced dotfiles, login items, Docker data, dependency stores, virtualenvs, or active project state.

A dry-run provides no backup and no undo. Clean deletions are normally permanent, so the preview is the only point at which the user can veto; it is not a way to reverse anything afterwards, and it does not guarantee the real run will target the same set. If a user asks whether Mole removed a specific file, use the deletion log path returned by history and answer from the relevant file or ancestor-directory records.
