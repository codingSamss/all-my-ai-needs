#!/bin/zsh
# 在一台新 Mac 上安装 bird 运行件：二进制、wrapper 软链、凭据工具软链。
# 幂等，可重复运行。skill 文件本身由仓库同步，不属于本脚本职责。

set -e

SCRIPT_DIR="${0:A:h}"
SKILL_DIR="${SCRIPT_DIR:h}"
BIN_DIR="$HOME/.local/bin"
VENDOR="$SKILL_DIR/vendor/bird-macos-universal-v0.8.0.tar.gz"

mkdir -p "$BIN_DIR"

# 1. 二进制。vendor 包内那份签名本身就是坏的，macOS 26+ 判定其无效并 SIGKILL，
#    所以解包后必须重签；重签只换签名，不动二进制内容。
if [[ ! -x "$BIN_DIR/bird-bin" ]]; then
  [[ -f "$VENDOR" ]] || { print -u2 "找不到 vendor 包：$VENDOR"; exit 1; }
  tmp=$(mktemp -d)
  # 任一步失败都不留临时目录
  trap '[[ -n "$tmp" && -d "$tmp" ]] && { rm -f "$tmp"/* 2>/dev/null; rmdir "$tmp" 2>/dev/null; }' EXIT
  tar -xzf "$VENDOR" -C "$tmp"
  [[ -f "$tmp/bird" ]] || { print -u2 "vendor 包内未找到 bird 可执行文件"; exit 1; }
  mv "$tmp/bird" "$BIN_DIR/bird-bin"
  chmod +x "$BIN_DIR/bird-bin"
  print "已解包 bird-bin"
fi

# 幂等：签名有效则跳过；无效（含刚解包那份坏签名）才重签
if ! codesign -v "$BIN_DIR/bird-bin" 2>/dev/null; then
  codesign -f -s - "$BIN_DIR/bird-bin"
  print "已重签 bird-bin"
fi

# 2. wrapper 与凭据工具以软链落到 PATH，源文件随 skill 走
ln -sf "$SCRIPT_DIR/bird-wrapper.zsh" "$BIN_DIR/bird"
ln -sf "$SCRIPT_DIR/cookies_to_keychain.py" "$BIN_DIR/bird-x-cookies-to-keychain"
print "已链接 bird / bird-x-cookies-to-keychain"

# 3. 凭据只存本地登录钥匙串，不随 iCloud 同步，每台机器各存一次。
#    两条都要在——只有一条时 bird 会拿到半套凭据并以 401 失败。
have_auth=0; have_ct0=0
security find-generic-password -a "$USER" -s bird-x-auth-token >/dev/null 2>&1 && have_auth=1
security find-generic-password -a "$USER" -s bird-x-ct0 >/dev/null 2>&1 && have_ct0=1

if (( have_auth && have_ct0 )); then
  print "钥匙串凭据已就位"
else
  print ""
  (( have_auth || have_ct0 )) && print "警告：钥匙串里只有半套凭据，需重新写入整对。"
  print "在 Chrome 登录 x.com 后，于一个持有完全磁盘访问权限的终端里运行："
  print "  bird-x-cookies-to-keychain"
fi
