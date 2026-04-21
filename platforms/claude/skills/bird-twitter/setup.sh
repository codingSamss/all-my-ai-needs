#!/bin/bash
set -euo pipefail

NEED_MANUAL=0
PROXY_HTTP="${HTTP_PROXY:-http://127.0.0.1:7897}"
PROXY_HTTPS="${HTTPS_PROXY:-http://127.0.0.1:7897}"
BIRD_NPM_PACKAGE="${BIRD_NPM_PACKAGE:-@jcheesepkg/bird}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIRD_VENDOR_BUNDLE_NAME="${BIRD_VENDOR_BUNDLE_NAME:-bird-macos-universal-v0.8.0.tar.gz}"
BIRD_VENDOR_BUNDLE_PATH="${BIRD_VENDOR_BUNDLE_PATH:-$SCRIPT_DIR/vendor/$BIRD_VENDOR_BUNDLE_NAME}"
BIRD_VENDOR_BUNDLE_SHA256="${BIRD_VENDOR_BUNDLE_SHA256:-3d89bb404e8b0ed4ef331f0dc62d873852634ca2a814ae7a4ac7effc114320cf}"

# Ensure user-level binaries are discoverable in non-interactive shells.
mkdir -p "$HOME/.local/bin"
export PATH="$HOME/.local/bin:$PATH"

install_bird_from_vendor_bundle() {
  local bundle="$1"
  local tmp_dir

  if [ ! -f "$bundle" ]; then
    return 1
  fi

  if ! echo "$BIRD_VENDOR_BUNDLE_SHA256  $bundle" | shasum -a 256 -c - >/dev/null 2>&1; then
    echo "[bird-twitter] 仓库内置 Bird 包 sha256 校验失败: $bundle"
    return 1
  fi

  tmp_dir="$(mktemp -d /tmp/bird-install.XXXXXX)"
  if tar -xzf "$bundle" -C "$tmp_dir" &&
     [ -f "$tmp_dir/bird" ] &&
     install -m 755 "$tmp_dir/bird" "$HOME/.local/bin/bird"; then
    rm -rf "$tmp_dir"
    return 0
  fi

  rm -rf "$tmp_dir"
  return 1
}

echo "[bird-twitter] 检查 Bird CLI..."
if command -v bird >/dev/null 2>&1; then
  echo "[bird-twitter] Bird CLI 已安装"
else
  echo "[bird-twitter] 尝试安装仓库内置 Bird CLI 包"
  if install_bird_from_vendor_bundle "$BIRD_VENDOR_BUNDLE_PATH"; then
    echo "[bird-twitter] 内置包安装成功: $(command -v bird)"
  else
    echo "[bird-twitter] 内置包安装失败或不可用，继续尝试外部来源"
  fi

  if command -v brew >/dev/null 2>&1; then
    if ! command -v bird >/dev/null 2>&1; then
      echo "[bird-twitter] 尝试通过 Homebrew 安装 Bird CLI"
      if brew install steipete/tap/bird; then
        echo "[bird-twitter] Homebrew 安装成功"
      else
        echo "[bird-twitter] Homebrew 安装失败（上游公式可能已下线）"
      fi
    fi
  fi

  if ! command -v bird >/dev/null 2>&1; then
    if command -v npm >/dev/null 2>&1; then
      echo "[bird-twitter] 尝试通过 npm 安装 Bird CLI（社区镜像）: $BIRD_NPM_PACKAGE"
      if HTTP_PROXY="$PROXY_HTTP" HTTPS_PROXY="$PROXY_HTTPS" \
           npm install -g --prefix "$HOME/.local" "$BIRD_NPM_PACKAGE"; then
        echo "[bird-twitter] npm 安装完成"
      else
        echo "[bird-twitter] npm 安装失败"
      fi
    fi
  fi

  if ! command -v bird >/dev/null 2>&1; then
    echo "[bird-twitter] 未能自动安装 Bird CLI。"
    echo "[bird-twitter] 建议手动确认可用来源（Homebrew 公式已下线时可通过 npm 社区镜像安装）。"
    echo "[bird-twitter] 例如：npm install -g --prefix \"\$HOME/.local\" @jcheesepkg/bird"
    NEED_MANUAL=1
  else
    echo "[bird-twitter] Bird CLI 已可用: $(command -v bird)"
  fi
fi

if command -v bird >/dev/null 2>&1; then
  if HTTP_PROXY="$PROXY_HTTP" HTTPS_PROXY="$PROXY_HTTPS" \
       bird --cookie-source chrome --timeout 15000 whoami >/dev/null 2>&1; then
    echo "[bird-twitter] Bird 认证已就绪"
  else
    echo "[bird-twitter] Bird 认证检查失败，请先确认："
    echo "  1) Chrome 已登录 X/Twitter"
    echo "  2) 代理可用（HTTP_PROXY/HTTPS_PROXY），默认尝试: http://127.0.0.1:7897"
    echo "  3) 可手动验证:"
    echo "     HTTP_PROXY=$PROXY_HTTP HTTPS_PROXY=$PROXY_HTTPS bird --cookie-source chrome --timeout 15000 whoami"
    NEED_MANUAL=1
  fi
fi

if [ "$NEED_MANUAL" -eq 1 ]; then
  exit 2
fi
