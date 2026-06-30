#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from datetime import datetime

NOTIFIER_BIN = os.path.expanduser("~/Applications/Codex CLI.app/Contents/MacOS/terminal-notifier")
FALLBACK_BIN = "terminal-notifier"
ICON_PATH = os.path.expanduser("~/.codex/assets/gpt-icon.png")
ICON_URL = "file://" + ICON_PATH
SOUND_NAME = "Glass"
OVERRIDE_BUNDLE_ID = os.environ.get("CODEX_NOTIFY_ACTIVATE_BUNDLE_ID", "").strip()
DEBUG = os.environ.get("CODEX_NOTIFY_DEBUG") == "1"
DEBUG_LOG = os.path.expanduser("~/.codex/log/codex-notify.log")
MAX_LEN = 100


def debug(msg: str) -> None:
    if not DEBUG:
        return
    os.makedirs(os.path.dirname(DEBUG_LOG), exist_ok=True)
    with open(DEBUG_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()}] {msg}\n")


def normalize(text: str) -> str:
    return " ".join(text.split())


def truncate(text: str, max_len: int = MAX_LEN) -> str:
    if len(text) <= max_len:
        return text
    if max_len <= 1:
        return text[:max_len]
    return text[: max_len - 1] + "…"


def is_codex_app_runtime() -> bool:
    """只在 Codex App 进程链出现时跳过通知，避免误伤 CLI。"""
    pid = os.getpid()
    while pid > 1:
        try:
            args = subprocess.check_output(["ps", "-p", str(pid), "-o", "args="], text=True).strip()
        except Exception:
            args = ""
        if "Codex.app/Contents" in args:
            debug(f"skip: codex app detected in args: {args}")
            return True
        try:
            ppid = subprocess.check_output(["ps", "-p", str(pid), "-o", "ppid="], text=True).strip()
            pid = int(ppid) if ppid else 1
        except Exception:
            break
    return False




def canonical_event_type(raw_type: object) -> str:
    if not isinstance(raw_type, str):
        return ""
    t = raw_type.strip().lower().replace("_", "-")
    if t in {"approval-requested", "approval-request", "approval-required"}:
        return "approval-requested"
    if t in {"agent-turn-complete", "turn-complete", "agent-complete"}:
        return "agent-turn-complete"
    return t


def get_project_name(payload: dict) -> str:
    cwd = payload.get("cwd") or os.getcwd()
    name = os.path.basename(cwd.rstrip("/")) if isinstance(cwd, str) else ""
    return name or "项目"



def is_jetbrains_env() -> bool:
    terminal_emulator = os.environ.get("TERMINAL_EMULATOR", "").lower()
    term_program = os.environ.get("TERM_PROGRAM", "")
    return any(
        os.environ.get(k)
        for k in (
            "JEDITERM_HOME",
            "IDEA_INITIAL_DIRECTORY",
            "JETBRAINS_IDE",
            "JETBRAINS_CLIENT",
            "INTELLIJ_ENV",
            "PYCHARM_HOSTED",
        )
    ) or "jetbrains" in terminal_emulator or term_program == "JetBrains-JediTerm"

def detect_jetbrains_bundle_id() -> str:
    override = os.environ.get("CODEX_NOTIFY_JETBRAINS_BUNDLE_ID", "").strip()
    if override:
        return override

    jetbrains_ide = os.environ.get("JETBRAINS_IDE", "").strip().lower()
    if "pycharm" in jetbrains_ide:
        return "com.jetbrains.pycharm"

    if os.environ.get("PYCHARM_HOSTED"):
        return "com.jetbrains.pycharm"

    return "com.jetbrains.intellij"

def detect_bundle_id_from_process_tree() -> str:
    pid = os.getpid()
    while pid > 1:
        try:
            pname = subprocess.check_output(["ps", "-p", str(pid), "-o", "comm="], text=True).strip()
        except Exception:
            pname = ""
        low = pname.lower()
        base = os.path.basename(low).strip()

        # JetBrains
        if "pycharm" in low:
            return "com.jetbrains.pycharm"
        if "intellij" in low or "idea" in low:
            return "com.jetbrains.intellij"

        # VS Code / Insiders / VSCodium（避免把 codex 误识别成 code）
        if "code - insiders" in low or "vscodeinsiders" in low:
            return "com.microsoft.VSCodeInsiders"
        if "visual studio code" in low or "code helper" in low:
            return "com.microsoft.VSCode"
        if base in {"code", "code-oss", "vscode"}:
            return "com.microsoft.VSCode"
        if "codium" in low:
            return "com.vscodium"

        # Terminal apps
        if "iterm" in low:
            return "com.googlecode.iterm2"
        if "terminal" in low:
            return "com.apple.Terminal"
        if "warp" in low:
            return "dev.warp.Warp-Stable"
        if "wezterm" in low:
            return "com.github.wez.wezterm"
        if "kitty" in low:
            return "net.kovidgoyal.kitty"
        if "alacritty" in low:
            return "org.alacritty"
        if "hyper" in low:
            return "co.zeit.hyper"

        try:
            ppid = subprocess.check_output(["ps", "-p", str(pid), "-o", "ppid="], text=True).strip()
            pid = int(ppid) if ppid else 1
        except Exception:
            break

    return ""

def detect_terminal_bundle_id() -> str:
    if OVERRIDE_BUNDLE_ID:
        return OVERRIDE_BUNDLE_ID

    # JetBrains 终端环境优先
    if is_jetbrains_env():
        process_bundle_id = detect_bundle_id_from_process_tree()
        if process_bundle_id in {"com.jetbrains.pycharm", "com.jetbrains.intellij"}:
            return process_bundle_id
        return detect_jetbrains_bundle_id()

    term_program = os.environ.get("TERM_PROGRAM")
    mapping = {
        "iTerm.app": "com.googlecode.iterm2",
        "Apple_Terminal": "com.apple.Terminal",
        "vscode": "com.microsoft.VSCode",
        "WarpTerminal": "dev.warp.Warp-Stable",
        "Hyper": "co.zeit.hyper",
        "Alacritty": "org.alacritty",
        "WezTerm": "com.github.wez.wezterm",
        "kitty": "net.kovidgoyal.kitty",
        "JetBrains-JediTerm": detect_jetbrains_bundle_id(),
    }
    if term_program in mapping:
        return mapping[term_program]

    return detect_bundle_id_from_process_tree()


def main() -> int:
    if len(sys.argv) < 2:
        return 0
    try:
        payload = json.loads(sys.argv[1])
    except Exception:
        return 0

    event_type = canonical_event_type(payload.get("type"))
    if event_type not in {"agent-turn-complete", "approval-requested"}:
        return 0

    # 如果是 Codex App 运行环境，直接跳过，避免覆盖 App 通知
    if is_codex_app_runtime():
        return 0

    # Ghostty 已有内建通知，避免重复弹窗。
    # 但如果当前是 JetBrains 终端（可能继承了 Ghostty 环境变量），仍然要发送通知。
    term_program = os.environ.get("TERM_PROGRAM", "")
    term_value = os.environ.get("TERM", "")
    jetbrains_env = is_jetbrains_env()
    if not jetbrains_env and (term_program.lower() == "ghostty" or "ghostty" in term_value.lower()):
        debug("skip notify inside Ghostty")
        return 0

    project_name = get_project_name(payload)

    if event_type == "approval-requested":
        title = f"Codex CLI：{project_name} · 需要决策"
        default_message = "需要你的决策"
    else:
        title = f"Codex CLI：{project_name} · 任务完成"
        default_message = "任务已完成"

    def pick_message() -> str:
        for key in (
            "last-assistant-message",
            "message",
            "approval_message",
            "reason",
            "summary",
            "text",
        ):
            val = payload.get(key)
            if isinstance(val, str) and val.strip():
                return val
        return default_message

    message = truncate(normalize(pick_message()), MAX_LEN)

    bin_path = NOTIFIER_BIN if os.path.exists(NOTIFIER_BIN) else FALLBACK_BIN

    group = f"codex-cli-{int(datetime.now().timestamp())}"

    cmd = [
        bin_path,
        "-title",
        title,
        "-message",
        message,
        "-group",
        group,
        "-sound",
        SOUND_NAME,
    ]

    bundle_id = detect_terminal_bundle_id()
    if bundle_id:
        # 用目标终端/IDE 作为 sender，减少自定义 notifier app 被系统静默的概率
        cmd += ["-sender", bundle_id]
        cmd += ["-activate", bundle_id]
        cmd += ["-execute", f"open -b {bundle_id}"]

    # 兜底：若运行的是原始 terminal-notifier，则尝试覆盖图标
    if bin_path == FALLBACK_BIN and os.path.exists(ICON_PATH):
        cmd += ["-appIcon", ICON_URL]

    if DEBUG:
        debug(f"cmd: {' '.join(cmd)}")
        debug(f"bundle_id: {bundle_id}")

    try:
        subprocess.run(cmd, check=False)
    except Exception:
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
