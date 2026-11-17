# Obsidian Video Note Standard

Use this reference when the user wants a note that can replace watching the video.

## Required Sections

1. Frontmatter with source URL, title, creator, video duration, transcript engine, and coverage status.
2. `## 1. 核心摘要`: explain the video's thesis in 5-10 bullets.
3. `## 2. 如何阅读这篇笔记`: tell the reader which sections are skimmable and which provide full coverage.
4. `## 3. 逐段完整笔记`: use a phase table first, then collapsible timestamp callouts.
5. `## 4. 图文精读`: embed selected frames with concise captions tied to the transcript.
6. `## 5. 可复用做法`: extract reusable playbooks, prompts, workflow patterns, and gotchas.
7. `## 6. 准确度说明`: document transcript engine, source timestamp alignment, frame extraction method, and known uncertainty.
8. `## See Also`: source links and related notes.

## Readability Rules

- Do not put 40+ timestamps into one flat bullet list.
- Group timestamps into phases such as setup, research, app build, automation, deployment, and final reflections.
- Put the phase overview in a table, and put detailed timestamp coverage inside collapsed callouts:

```markdown
> [!note]- Part 1: Codex Basics
> - `00:00` ...
> - `02:54` ...
```

- Use screenshots to break long sections. Captions should explain what the image proves or clarifies.
- Keep detailed operational coverage, but move distilled methodology into later sections so the note is not only a transcript map.
- Mark content origin explicitly when needed: `原视频演示`, `转写推断`, `整理者提炼`.

## Completeness Checklist

- Every source timestamp appears in the note or is explicitly marked as merged into a nearby section.
- The opening, middle, and ending transcript were spot-checked.
- The note has enough screenshots to explain interface changes and visual results.
- Markdown image reference count matches actual image files.
- The note states whether a full transcript was retained outside the note.
- External edits to an Obsidian file were followed by `touch <note>`.
