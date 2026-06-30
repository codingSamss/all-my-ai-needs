#!/bin/bash
set -euo pipefail

NEED_MANUAL=0
MODE="${TRANSCRIBE_MODE:-groq}"

echo "[video-transcribe] 检查依赖... (模式: $MODE)"

probe_groq_models() {
  local use_local_proxy="${1:-0}"
  local http_code=""

  if [ "$use_local_proxy" = "1" ]; then
    http_code=$(HTTP_PROXY="http://127.0.0.1:7897" HTTPS_PROXY="http://127.0.0.1:7897" \
      curl -sS -o /tmp/video-transcribe/groq_probe.json -w "%{http_code}" \
      --connect-timeout 8 --max-time 20 \
      https://api.groq.com/openai/v1/models \
      -H "Authorization: Bearer $GROQ_API_KEY" || true)
  else
    http_code=$(curl -sS -o /tmp/video-transcribe/groq_probe.json -w "%{http_code}" \
      --connect-timeout 8 --max-time 20 \
      https://api.groq.com/openai/v1/models \
      -H "Authorization: Bearer $GROQ_API_KEY" || true)
  fi

  echo "${http_code:-000}"
}

# 1. yt-dlp
if command -v yt-dlp >/dev/null 2>&1; then
  echo "[video-transcribe] yt-dlp 已安装: $(yt-dlp --version)"
else
  if command -v brew >/dev/null 2>&1; then
    echo "[video-transcribe] 安装 yt-dlp..."
    brew install yt-dlp
  else
    echo "[video-transcribe] 未检测到 Homebrew，请手动安装: brew install yt-dlp"
    NEED_MANUAL=1
  fi
fi

# 2. ffmpeg
if command -v ffmpeg >/dev/null 2>&1; then
  echo "[video-transcribe] ffmpeg 已安装"
else
  if command -v brew >/dev/null 2>&1; then
    echo "[video-transcribe] 安装 ffmpeg..."
    brew install ffmpeg
  else
    echo "[video-transcribe] 未检测到 Homebrew，请手动安装: brew install ffmpeg"
    NEED_MANUAL=1
  fi
fi

# 3. 按模式检查转录引擎
if [ "$MODE" = "groq" ]; then
  # Groq API 模式：检查 API Key 与连通性
  if [ -n "${GROQ_API_KEY:-}" ]; then
    echo "[video-transcribe] GROQ_API_KEY 已设置"

    mkdir -p /tmp/video-transcribe
    DIRECT_CODE="$(probe_groq_models 0)"
    if [ "$DIRECT_CODE" = "200" ]; then
      echo "[video-transcribe] Groq API 连通性检查通过（直连）"
    else
      PROXY_CODE="$(probe_groq_models 1)"
      if [ "$PROXY_CODE" = "200" ]; then
        echo "[video-transcribe] Groq API 直连失败（HTTP ${DIRECT_CODE}），但本地 7897 代理可用"
        echo "  请在 ~/.zshrc 或 ~/.bashrc 中添加:"
        echo "    export HTTP_PROXY=\"http://127.0.0.1:7897\""
        echo "    export HTTPS_PROXY=\"http://127.0.0.1:7897\""
        echo "  或在调用转录命令前临时加上这两个环境变量"
        NEED_MANUAL=1
      else
        echo "[video-transcribe] Groq API 连通性检查失败（直连 HTTP ${DIRECT_CODE}，代理 HTTP ${PROXY_CODE}）"
        echo "  可手动排查:"
        echo "    curl -s https://api.groq.com/openai/v1/models -H \"Authorization: Bearer \$GROQ_API_KEY\""
        NEED_MANUAL=1
      fi
    fi
  else
    echo "[video-transcribe] GROQ_API_KEY 未设置"
    echo "  请在 ~/.zshrc 或 ~/.bashrc 中添加:"
    echo "    export GROQ_API_KEY=\"你的key\""
    echo "  申请地址: https://console.groq.com"
    NEED_MANUAL=1
  fi
elif [ "$MODE" = "local" ]; then
  # 本地模式：检查 whisper-cpp 和模型
  MODEL_DIR="$HOME/.cache/whisper-cpp"
  MODEL_FILE="$MODEL_DIR/ggml-small.bin"
  MODEL_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin"

  if command -v whisper-cli >/dev/null 2>&1; then
    echo "[video-transcribe] whisper-cpp 已安装"
  else
    if command -v brew >/dev/null 2>&1; then
      echo "[video-transcribe] 安装 whisper-cpp..."
      brew install whisper-cpp
    else
      echo "[video-transcribe] 未检测到 Homebrew，请手动安装: brew install whisper-cpp"
      NEED_MANUAL=1
    fi
  fi

  if [ -f "$MODEL_FILE" ]; then
    MODEL_SIZE=$(du -h "$MODEL_FILE" | cut -f1)
    echo "[video-transcribe] Whisper small 模型已就绪 ($MODEL_SIZE)"
  else
    echo "[video-transcribe] 下载 Whisper small 模型 (~465MB)..."
    mkdir -p "$MODEL_DIR"
    if curl -L "$MODEL_URL" -o "$MODEL_FILE" --progress-bar; then
      echo "[video-transcribe] 模型下载完成"
    else
      echo "[video-transcribe] 模型下载失败，请手动下载:"
      echo "  curl -L $MODEL_URL -o $MODEL_FILE"
      NEED_MANUAL=1
    fi
  fi
else
  echo "[video-transcribe] 未知模式: $MODE (支持: groq, local)"
  exit 1
fi

# 4. 创建工作目录
mkdir -p /tmp/video-transcribe

echo ""
if [ "$NEED_MANUAL" -eq 1 ]; then
  echo "[video-transcribe] 部分依赖需要手动配置，请查看上方提示"
  exit 2
else
  echo "[video-transcribe] 所有依赖已就绪 (模式: $MODE)"
fi
