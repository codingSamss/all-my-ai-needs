#!/bin/bash
# Claude Code 智能通知脚本
# 自动检测终端类型，支持多种终端跳转

EVENT_TYPE="${1:-stop}"
MAX_LEN=100
DEBUG="${CLAUDE_NOTIFY_DEBUG:-0}"
DEBUG_LOG="$HOME/Desktop/claude-notify-input.log"

NOTIFIER_APP="$HOME/Applications/Claude Code CLI.app/Contents/MacOS/terminal-notifier"
NOTIFIER_BIN="terminal-notifier"
if [[ -x "$NOTIFIER_APP" ]]; then
    NOTIFIER_BIN="$NOTIFIER_APP"
fi

# 读取标准输入（hook传入的JSON数据）
INPUT=$(cat)

log_debug() {
    if [[ "$DEBUG" != "1" ]]; then
        return
    fi
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" >> "$DEBUG_LOG"
}

log_debug "RAW=$INPUT"

# 项目名称（默认取 cwd 末级目录）
PROJECT_PATH=""
if command -v jq &> /dev/null; then
    PROJECT_PATH=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)
fi
if [[ -z "$PROJECT_PATH" ]]; then
    PROJECT_PATH="$PWD"
fi
PROJECT_NAME=$(basename "$PROJECT_PATH")
if [[ -z "$PROJECT_NAME" ]]; then
    PROJECT_NAME="项目"
fi

# 对于 notification 事件，检查 notification_type
if [[ "$EVENT_TYPE" == "notification" ]]; then
    NOTIFICATION_TYPE=""
    if command -v jq &> /dev/null; then
        NOTIFICATION_TYPE=$(echo "$INPUT" | jq -r '.notification_type // ""' 2>/dev/null)
    fi

    # 只在非 idle_prompt 时发送通知
    if [[ "$NOTIFICATION_TYPE" == "idle_prompt" ]]; then
        log_debug "skip idle_prompt"
        exit 0
    fi
fi

# 提取回复内容（尽量通用）
extract_message_from_input() {
    if command -v jq &> /dev/null; then
        echo "$INPUT" | jq -r '
            [
              .message,
              .last_assistant_message,
              .assistant_message,
              .notification_message,
              .text,
              .response,
              .output_text,
              .completion,
              (.. | objects | .text? // empty)
            ]
            | map(select(type=="string"))
            | map(select(length>0))
            | .[0] // ""
        ' 2>/dev/null
    fi
}

# 尝试从 transcript_path 获取最后一条 assistant 文本
extract_message_from_transcript() {
    local transcript_path="$1"
    if [[ -z "$transcript_path" || ! -f "$transcript_path" ]]; then
        echo ""
        return
    fi
    if ! command -v python3 &> /dev/null; then
        echo ""
        return
    fi

    local attempt=0
    while [[ $attempt -lt 5 ]]; do
        local msg
        msg=$(python3 - "$transcript_path" <<'PY'
import json
import sys

path = sys.argv[1]
last_assistant_text = ""
assistant_after_user = ""
seen_user = False
try:
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            t = obj.get('type')
            if t == 'user':
                seen_user = True
                assistant_after_user = ""
                continue
            if t != 'assistant':
                continue
            msg = obj.get('message') or {}
            content = msg.get('content')
            text = ""
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict):
                        if item.get('type') == 'text' and isinstance(item.get('text'), str):
                            parts.append(item.get('text'))
                        elif isinstance(item.get('text'), str):
                            parts.append(item.get('text'))
                text = "".join(parts).strip()
            elif isinstance(content, str):
                text = content.strip()
            if text:
                last_assistant_text = text
                if seen_user:
                    assistant_after_user = text
except Exception:
    pass

if seen_user:
    if assistant_after_user:
        print(assistant_after_user, end='')
    else:
        print('', end='')
else:
    print(last_assistant_text, end='')
PY
)
        if [[ -n "$msg" ]]; then
            echo "$msg"
            return
        fi
        attempt=$((attempt+1))
        sleep 0.2
    done
    echo ""
}

# 规范化与截断
sanitize_and_truncate() {
    local s="$1"
    s=$(printf '%s' "$s" | tr '\r\n\t' '   ' | sed -E 's/[[:space:]]+/ /g; s/^ //; s/ $//')
    if command -v python3 &> /dev/null; then
        s=$(printf '%s' "$s" | python3 -c 'import sys; max_len=int(sys.argv[1]); text=sys.stdin.read(); text=(text[:max_len-1]+"…") if (len(text)>max_len and max_len>1) else (text[:max_len] if len(text)>max_len else text); print(text, end="")' "$MAX_LEN")
    else
        s="${s:0:$MAX_LEN}"
    fi
    printf '%s' "$s"
}

# 检测是否运行在 JetBrains 终端环境
is_jetbrains_env() {
    [[ "${TERMINAL_EMULATOR:-}" == "JetBrains-JediTerm" ]] && return 0
    [[ -n "${JEDITERM_HOME:-}" ]] && return 0
    [[ -n "${IDEA_INITIAL_DIRECTORY:-}" ]] && return 0
    [[ -n "${JETBRAINS_IDE:-}" ]] && return 0
    [[ -n "${JETBRAINS_CLIENT:-}" ]] && return 0
    [[ -n "${INTELLIJ_ENV:-}" ]] && return 0
    [[ -n "${PYCHARM_HOSTED:-}" ]] && return 0
    return 1
}

RAW_MESSAGE=$(extract_message_from_input)
log_debug "RAW_MESSAGE_FROM_INPUT=$RAW_MESSAGE"

# notification 事件可能只有通用提示语，视为无内容以便走 transcript
if [[ "$EVENT_TYPE" == "notification" ]]; then
    case "$RAW_MESSAGE" in
        "Claude Code needs your attention"|"Claude is waiting for your input"|"Claude Code needs your input"|"Claude needs your attention"|"Needs your attention")
            log_debug "RAW_MESSAGE_GENERIC=$RAW_MESSAGE"
            RAW_MESSAGE=""
            ;;
    esac
fi

TRANSCRIPT_PATH=""
if command -v jq &> /dev/null; then
    TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
fi
log_debug "TRANSCRIPT_PATH=$TRANSCRIPT_PATH"

if [[ -z "$RAW_MESSAGE" && -n "$TRANSCRIPT_PATH" ]]; then
    RAW_MESSAGE=$(extract_message_from_transcript "$TRANSCRIPT_PATH")
    log_debug "RAW_MESSAGE_FROM_TRANSCRIPT=$RAW_MESSAGE"
fi

# 检测终端并获取bundleId
detect_terminal_bundle_id() {
    # 优先使用环境变量
    if [[ -n "$TERM_PROGRAM" ]]; then
        case "$TERM_PROGRAM" in
            "iTerm.app") echo "com.googlecode.iterm2"; return ;;
            "Apple_Terminal") echo "com.apple.Terminal"; return ;;
            "vscode") echo "com.microsoft.VSCode"; return ;;
            "WarpTerminal") echo "dev.warp.Warp-Stable"; return ;;
            "Hyper") echo "co.zeit.hyper"; return ;;
            "Alacritty") echo "org.alacritty"; return ;;
            "JetBrains-JediTerm") echo "com.jetbrains.intellij"; return ;;
            *) ;;
        esac
    fi

    # 检测父进程链中的终端
    local pid=$$
    while [[ $pid -gt 1 ]]; do
        local pname=$(ps -p $pid -o comm= 2>/dev/null)
        case "$pname" in
            *idea*|*intellij*) echo "com.jetbrains.intellij"; return ;;
            *iterm*) echo "com.googlecode.iterm2"; return ;;
            *Terminal*) echo "com.apple.Terminal"; return ;;
            *Code*) echo "com.microsoft.VSCode"; return ;;
            *warp*) echo "dev.warp.Warp-Stable"; return ;;
        esac
        pid=$(ps -p $pid -o ppid= 2>/dev/null | tr -d ' ')
    done

    # 默认使用IDEA
    echo "com.jetbrains.intellij"
}

# 获取bundleId
BUNDLE_ID=$(detect_terminal_bundle_id)

# Ghostty 自带通知，避免重复弹窗
if [[ "${TERM_PROGRAM:-}" =~ [Gg]hostty || "${TERM:-}" =~ [Gg]hostty ]]; then
    if ! is_jetbrains_env; then
        log_debug "skip notify in Ghostty"
        exit 0
    fi
fi

case "$EVENT_TYPE" in
    stop)
        MESSAGE="${RAW_MESSAGE}"
        if [[ -z "$MESSAGE" ]]; then
            MESSAGE="任务已完成"
        else
            MESSAGE=$(sanitize_and_truncate "$MESSAGE")
        fi
        log_debug "FINAL_MESSAGE=$MESSAGE"
        if [[ -n "$BUNDLE_ID" ]]; then
            "$NOTIFIER_BIN" \
                -title "Claude Code: ${PROJECT_NAME} · 任务完成" \
                -message "$MESSAGE" \
                -sound Glass \
                -sender "$BUNDLE_ID" \
                -activate "$BUNDLE_ID" \
                -execute "open -b $BUNDLE_ID" \
                -group "claude-$(date +%s)"
        else
            "$NOTIFIER_BIN" \
                -title "Claude Code: ${PROJECT_NAME} · 任务完成" \
                -message "$MESSAGE" \
                -sound Glass \
                -group "claude-$(date +%s)"
        fi
        ;;
    notification)
        MESSAGE="${RAW_MESSAGE}"
        if [[ -z "$MESSAGE" ]]; then
            MESSAGE="需要你的决策"
        else
            MESSAGE=$(sanitize_and_truncate "$MESSAGE")
        fi
        log_debug "FINAL_MESSAGE=$MESSAGE"
        if [[ -n "$BUNDLE_ID" ]]; then
            "$NOTIFIER_BIN" \
                -title "Claude Code: ${PROJECT_NAME} · 需要决策" \
                -message "$MESSAGE" \
                -sound Ping \
                -sender "$BUNDLE_ID" \
                -activate "$BUNDLE_ID" \
                -execute "open -b $BUNDLE_ID" \
                -group "claude-$(date +%s)"
        else
            "$NOTIFIER_BIN" \
                -title "Claude Code: ${PROJECT_NAME} · 需要决策" \
                -message "$MESSAGE" \
                -sound Ping \
                -group "claude-$(date +%s)"
        fi
        ;;
esac
