# screenshot

## 作用
执行系统级截图（全屏、窗口、区域）并支持临时路径输出，适用于视觉排查与界面对比。

## 平台支持
- Codex（已支持）

## 工作原理
Skill 调用 `scripts/take_screenshot.py`（跨平台）与 macOS 权限辅助脚本完成截图。

## 验证命令

```bash
python3 platforms/codex/skills/screenshot/scripts/take_screenshot.py --help
```

## 依赖
- Python3
- macOS：`screencapture`、`swift`、屏幕录制权限
- Linux：`scrot` 或 `gnome-screenshot` 或 `import`
