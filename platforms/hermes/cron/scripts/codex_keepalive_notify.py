#!/usr/bin/env python3
import shutil
import subprocess
import tempfile
from pathlib import Path

SUCCESS_TEXT = "定时刷新任务执行完成"
PROMPT = f"只回复：{SUCCESS_TEXT}，不要输出任何其他内容。"
TITLE = "Codex Cron"
SENDER_BUNDLE_ID = "com.apple.Terminal"
SUCCESS_MSG = SUCCESS_TEXT


def shorten(text: str, limit: int = 120) -> str:
    text = " ".join(text.replace("\r", " ").replace("\n", " ").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def notify(message: str) -> bool:
    notifier = shutil.which("terminal-notifier")
    if notifier:
        res = subprocess.run(
            [
                notifier,
                "-title",
                TITLE,
                "-message",
                message,
                "-sender",
                SENDER_BUNDLE_ID,
            ],
            capture_output=True,
            text=True,
        )
        if res.returncode == 0:
            return True

    osa = shutil.which("osascript")
    if osa:
        safe_message = message.replace('\\', '\\\\').replace('"', '\\"')
        safe_title = TITLE.replace('\\', '\\\\').replace('"', '\\"')
        script = f'display notification "{safe_message}" with title "{safe_title}"'
        res = subprocess.run([osa, "-e", script], capture_output=True, text=True)
        if res.returncode == 0:
            return True

    return False


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="codex-keepalive-") as tmp:
        tmp_path = Path(tmp)
        out_file = tmp_path / "last_message.txt"
        cmd = [
            "codex",
            "exec",
            "--skip-git-repo-check",
            "--ephemeral",
            "--color",
            "never",
            "--cd",
            str(tmp_path),
            "--output-last-message",
            str(out_file),
            PROMPT,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)

        msg = ""
        if out_file.exists():
            msg = out_file.read_text(encoding="utf-8", errors="replace").strip()

        if res.returncode == 0 and msg == SUCCESS_TEXT:
            notified = notify(SUCCESS_MSG)
            if notified:
                print(SUCCESS_TEXT)
            else:
                print("ERR notify-unavailable")
            return 0

        combined = "\n".join(part for part in [msg, res.stderr, res.stdout] if part).strip()
        reason = shorten(combined or f"exit {res.returncode}")
        notify(f"定时刷新任务失败：{reason}")
        print(f"ERR {reason}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
