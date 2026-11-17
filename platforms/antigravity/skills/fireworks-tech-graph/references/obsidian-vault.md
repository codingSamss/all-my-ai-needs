# Obsidian / Vault Diagram Defaults

When the output target is Sam's Obsidian vault, `_teach` HTML, or an HTML file expected to be opened through Obsidian/HTML Reader, optimize for the Obsidian reading pane instead of a full browser canvas:

- Prefer compact portrait or narrow layouts. Default `viewBox` width should be `820-960`; choose height only as large as the content needs. Avoid defaulting to wide `16:9`, `1280x720`, or `1280x760` topology diagrams.
- For architecture and RAG/system maps, split the diagram into vertical bands or multiple figures instead of placing four or more service nodes in a single horizontal row.
- Keep whitespace intentional and limited: outer margins around `40-60px`, group padding around `24-48px`, and no large empty vertical bands inside dashed containers. If a group has too much empty space, compact the viewBox or split the diagram.
- Edge labels must sit near the path but not on top of the stroke, arrowhead, or node border. Re-render and inspect after every compaction pass because label overlap often appears only at Obsidian pane width.
- Use stable arrow marker sizing for Obsidian diagrams. Prefer `markerUnits="userSpaceOnUse"` with modest marker dimensions; avoid `markerUnits="strokeWidth"` for primary arrows because arrowheads can become visually oversized after line-width or pane scaling changes.
- Do not draw dangling or decorative observability connectors. Trace/debug/eval relationships should be shown as node text, a callout, or a clearly continuous edge between two concrete anchors; remove the line if it would appear as a short disconnected segment at Obsidian pane width.
- For `_teach` HTML, prefer inline SVG for primary diagrams. Relative or `file://` image paths can fail under Obsidian/HTML Reader; if external image files are used, verify in Obsidian, not only in a normal browser.
- Final verification must include a rendered PNG inspection and a narrow-reading-pane check: no cropped content, no overflowing text, no arrows through node bodies, no label overlap, and the chart remains readable when scaled to the note body width.
