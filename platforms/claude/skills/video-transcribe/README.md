# video-transcribe

## 作用
从任意视频/音频链接提取内容并分析。支持 Groq Whisper 全量转录、关键帧分析、时间轴校验和可替代看视频的 Obsidian 图文笔记。支持 Twitter/X、YouTube、Bilibili 等 1000+ 站点。

## 平台支持
- Claude Code（已支持）
- Codex（已支持）

## 工作原理

### 音频转录模式
1. 使用 yt-dlp 下载视频音频轨
2. 调用 Groq Whisper API（whisper-large-v3）在线转录
3. 对超过 25MB 的音频自动切分后逐段转录
4. 输出结构化总结

### 画面分析模式
1. 使用 yt-dlp 下载视频文件（720p）
2. 使用 ffmpeg 按视频时长均匀提取最多 8 张关键帧
3. 使用 Claude 多模态视觉能力分析帧图片
4. 输出画面描述和视觉分析总结

### 完整图文笔记模式
1. 使用 yt-dlp 下载源视频，必要时用 `uvx --from yt-dlp yt-dlp` 避开本机旧版本问题
2. 使用 `whisper-large-v3` + `verbose_json` 全量转录，保留 timestamp segment
3. 按源 timestamps 和转录结果做覆盖校验
4. 提取关键帧并写入同级 assets
5. 输出“摘要 + 阶段索引 + 折叠时间轴 + 图文精读 + 可复用做法 + 准确度说明”

### 综合分析模式（默认）
1. 下载视频 → 提取关键帧 + 提取音频
2. 画面分析 + 音频转录同时进行
3. 综合两者输出完整总结
4. 若音频无有效语音，自动退化为纯画面分析

### 模式判断规则
- **音频模式**：用户明确提到「转录」「字幕」「语音转文字」「他说了什么话」等
- **画面模式**：用户明确提到「画面」「视觉」「展示了什么」「出现了什么」等
- **综合模式**：用户笼统说「分析视频」「视频说了什么」「帮我看看」或意图不明确时

默认使用 Groq API（在线模式），也支持本地 whisper-cpp 作为备选（离线/隐私场景）。

## 配置命令

```bash
# 默认在线模式（Groq API）
./setup.sh video-transcribe

# 本地模式
TRANSCRIBE_MODE=local ./setup.sh video-transcribe
```

## 配置脚本行为

- 退出码：`0` 自动完成，`2` 需手动补齐，`1` 执行失败
- 模式选择：通过 `TRANSCRIBE_MODE` 环境变量控制，默认 `groq`

### Groq 模式（默认）
- 自动检查项：yt-dlp、ffmpeg、`GROQ_API_KEY` 环境变量、Groq API 连通性
- 需手动补齐项：
  - 未设置 `GROQ_API_KEY` 时提示申请
  - 直连 Groq 返回 `403` 且仅代理可通时，需配置代理环境变量

### Local 模式
- 自动检查项：yt-dlp、ffmpeg、whisper-cpp、Whisper 模型文件
- 自动处理：缺少模型时自动下载 small 模型（~465MB）

## 验证命令

```bash
# 检查 Groq API 连通性
curl -s https://api.groq.com/openai/v1/models \
  -H "Authorization: Bearer $GROQ_API_KEY" | head -1

# 如直连返回 403，可改走本地 7897 代理
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 \
  curl -s https://api.groq.com/openai/v1/models \
  -H "Authorization: Bearer $GROQ_API_KEY" | head -1
```

## 使用方式
- 音频转录触发词：`转录`、`字幕`、`语音转文字`、`transcribe`
- 画面分析触发词：`画面`、`视觉分析`、`展示了什么`、`visual`
- 综合分析触发词：`分析视频`、`视频内容`、`说了什么`、`帮我看看`
- 完整笔记触发词：`全量`、`完整`、`不要看视频`、`替代看视频`、`图文笔记`
- 详细命令与触发规则见：`SKILL.md`

## 内置脚本
- `scripts/download_media.sh`：下载音频/视频，含 cookies retry 和 `uvx` fallback。
- `scripts/transcribe_groq.py`：抽音频、分段、Groq 转录、合并 timestamp。
- `scripts/extract_frames.sh`：按均匀间隔或指定 timestamps 抽关键帧。
- `scripts/verify_obsidian_note.sh`：校验 frontmatter、图片引用和 timestamp 覆盖。

## 依赖
- yt-dlp（`brew install yt-dlp`）
- ffmpeg（`brew install ffmpeg`）-- 音频切分 + 关键帧提取
- Groq API Key（https://console.groq.com）-- 音频转录需要，画面分析不需要
- （本地模式）whisper-cpp（`brew install whisper-cpp`）
