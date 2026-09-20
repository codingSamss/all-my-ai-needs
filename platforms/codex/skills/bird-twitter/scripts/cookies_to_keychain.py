#!/usr/bin/env python3
"""从 Chrome 提取 X 凭据并写入登录钥匙串，供 bird 与 bird-bookmark-folders 使用。

必须在持有完全磁盘访问权限的进程里运行（例如你自己的终端）：读取 Chrome 的 Cookies
库受 TCC 管控。授权对象选终端而非 Claude Code——终端路径固定，一次永久有效；
Claude Code 每次升级都换目录，授权会反复失效。

写入钥匙串后，Claude Code 一侧无需任何系统授权即可取用。token 过期时重跑本脚本刷新。
"""
import os
import subprocess
import sys

# device_follow_timeline 与本脚本同目录，复用它的 cookie 解密逻辑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import device_follow_timeline as dft
except ImportError:
    sys.exit("找不到同目录下的 device_follow_timeline 模块，确认 bird-twitter skill 完整")


def keychain_set(service, user, value):
    """写入一条 generic password，并读回校验。

    凭据只能经 argv 传给 security：它从 stdin 读密码时有 128 字节硬上限，而 ct0
    有 160 字符，走 stdin 会被静默截断，后续请求随即以 "requires a matching csrf
    cookie and header" 失败，且写入端毫无报错——不要改回 stdin。

    argv 的暴露窗口是这次调用的毫秒级存活期。作为补偿：不用 check=True、失败时
    也不回显 security 的输出，避免异常信息把完整命令连带凭据带进终端日志。
    """
    proc = subprocess.run(
        ["security", "add-generic-password", "-U", "-a", user, "-s", service, "-w", value],
        capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        sys.exit(f"写入钥匙串条目 {service} 失败（security 退出码 {proc.returncode}）")

    # 写后读回校验。截断这类损坏在写入侧不报错，只会在很久以后表现为认证失败，
    # 所以在这里就把它变成明确错误。
    back = subprocess.run(
        ["security", "find-generic-password", "-a", user, "-s", service, "-w"],
        capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    if back != value:
        sys.exit(
            f"钥匙串条目 {service} 写入后校验失败："
            f"期望 {len(value)} 字符，读回 {len(back)} 字符"
        )


def main():
    try:
        auth, ct0 = dft.extract_twitter_cookies_from_chrome("Default", None)
    except Exception as e:
        # TCC 拦截时底层 cp 会失败；给出可操作指引而不是抛栈
        sys.exit(
            f"读取 Chrome Cookies 失败：{e}\n"
            "当前进程没有完全磁盘访问权限。请在 系统设置 -> 隐私与安全性 -> 完全磁盘访问权限\n"
            "中加入你运行本脚本的终端，重启终端后再试。"
        )

    if not auth or not ct0:
        sys.exit("Chrome 里没读到 auth_token/ct0，先在 Chrome 登录 x.com")

    user = os.environ.get("USER", "")
    for service, value in (("bird-x-auth-token", auth), ("bird-x-ct0", ct0)):
        keychain_set(service, user, value)

    print(f"已写入钥匙串：bird-x-auth-token ({len(auth)} 字符) / bird-x-ct0 ({len(ct0)} 字符)")
    print("现在 Claude Code 一侧无需任何系统授权即可使用 bird 与 bird-bookmark-folders。")


if __name__ == "__main__":
    main()
