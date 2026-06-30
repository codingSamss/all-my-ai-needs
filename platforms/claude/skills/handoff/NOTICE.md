# Notice

`handoff` is adapted from Matt Pocock's `mattpocock/skills` repository.

- Source repository: <https://github.com/mattpocock/skills>
- Source path: `skills/productivity/handoff`
- Pinned commit: `bddb833cbaa322ff89d07e490530860aa73a4293`
- License: MIT

The upstream skill is a compact instruction for writing a handoff document into the OS temporary directory. This Claude version keeps that behavior, removes upstream-only frontmatter fields, and expands the body with Claude-compatible workflow, redaction, output-location, and template guidance.

Local extensions maintained for Sam's workflow:

- `temp` mode preserves the upstream behavior and writes short handoffs to the OS temporary directory.
- `workspace` mode writes into the current workspace only when explicitly requested.
- `vault` mode writes persistent multi-machine handoffs into the Obsidian `08_交接台` task structure and indexes large external artifacts under iCloud `AgentArtifacts`.
