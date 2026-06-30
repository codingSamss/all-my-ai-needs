---
name: taste-design
description: Taste 设计统一入口。用于前端页面设计/改版、图到代码、品牌视觉、移动端/网页参考图、Stitch 设计系统；先按任务路由到一个子模块，避免加载多个 taste skill。
---

# Taste Design

这是 Taste 系列的唯一运行入口。仓库内保留各细分模块，但日常不要把它们作为独立 skill 暴露给 agent。

## 使用原则

- 先判断任务类型，再读取一个最匹配的子模块；只有任务明确跨阶段时，才额外读取一个辅助子模块。
- 不要为了“设计任务”批量读取 `references/skills/` 下的所有模块。
- 用户明确点名某个旧模块名时，按点名模块处理；如果旧模块名与当前任务冲突，先说明冲突并按用户意图选择。
- 用户只是泛泛要求“做个页面 / 优化页面 / 做官网 / 改版”时，默认读取 `references/skills/taste-design-frontend/SKILL.md`。

## 路由表

- 新建 landing page、官网、作品集、页面设计、前端页面改版：读取 `references/skills/taste-design-frontend/SKILL.md`。
- 已有项目视觉改造、消除模板感、在不破坏功能的前提下重做界面：读取 `references/skills/taste-redesign-existing-projects/SKILL.md`。
- 根据截图、设计稿、生成图或参考图落地代码：读取 `references/skills/taste-image-to-code/SKILL.md`。
- 只生成网页视觉参考图，不直接写代码：读取 `references/skills/taste-imagegen-frontend-web/SKILL.md`。
- 只生成移动端 App / iOS / Android 多屏视觉参考图，不直接写代码：读取 `references/skills/taste-imagegen-frontend-mobile/SKILL.md`。
- 品牌识别、logo 方向、品牌规范板、视觉世界探索：读取 `references/skills/taste-brandkit/SKILL.md`。
- 生成或沉淀 Google Stitch 用的 `DESIGN.md`：读取 `references/skills/taste-stitch-design/SKILL.md`；需要样例规范时再读 `references/skills/taste-stitch-design/DESIGN.md`。
- 用户明确要求高端视觉质感、避免 AI 廉价感、提升字体/间距/阴影/卡片质量：读取 `references/skills/taste-high-end-visual-design/SKILL.md`。
- 用户明确要求高级极简、文档感、工作台平台感：读取 `references/skills/taste-minimalist-ui/SKILL.md`。
- 用户明确要求工业粗野风、瑞士网格、终端感、机械高对比 UI：读取 `references/skills/taste-industrial-brutalist-ui/SKILL.md`。
- 用户明确要求高强度营销页、AIDA、强视觉冲击、GSAP 动效，或点名 GPT/Codex 强设计规则：读取 `references/skills/taste-gpt/SKILL.md`。
- 用户要求完整代码、完整文件、长内容严禁省略时，把 `references/skills/taste-full-output-enforcement/SKILL.md` 作为辅助模块读取；不要把它当作设计主模块。
- 只有用户明确要求旧版 Taste 行为或兼容旧项目时，才读取 `references/skills/taste-design-frontend-v1/SKILL.md`。

## 组合规则

- 设计并实现新页面：`taste-design-frontend` 为主；如明确要求先出视觉稿，再补 `taste-image-to-code`。
- 现有页面重设计并实现：`taste-redesign-existing-projects` 为主；如有截图到代码要求，再补 `taste-image-to-code`。
- 品牌视觉后接官网实现：先用 `taste-brandkit` 定方向；进入代码阶段再读 `taste-design-frontend`。
- 风格词只是修饰时，不要抢主入口。例如“做一个极简 SaaS 首页”仍以 `taste-design-frontend` 为主，只在需要细化极简规则时补 `taste-minimalist-ui`。
