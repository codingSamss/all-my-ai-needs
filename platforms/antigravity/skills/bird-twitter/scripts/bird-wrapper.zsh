#!/bin/zsh
# bird wrapper：从登录钥匙串取出 X 凭据，经环境变量交给真二进制 bird-bin。
#
# 为什么走环境变量而不是命令行参数：argv 出现在任何用户可读的 ps 输出里，而环境
# 变量只在 `ps eww` 这类显式查看进程环境的场合可见——暴露面小一档，但并非不可见。
#
# 为什么二进制路径写死、不接受环境变量覆盖：wrapper 会把凭据 export 给它 exec 的
# 那个程序，路径若可被调用环境改写，等于把凭据交给任意程序。

BIRD_BIN="$HOME/.local/bin/bird-bin"

if [[ ! -x "$BIRD_BIN" ]]; then
  print -u2 "bird-bin 不存在：$BIRD_BIN"
  print -u2 "运行本 skill 的 scripts/install_local.zsh 安装，详见 SKILL.md"
  exit 127
fi

# auth_token 与 ct0 必须同源成对。调用方已完整提供时原样沿用；只提供半套时忽略
# 半套、改用钥匙串里的整对——混用两个来源会得到 401 或 CSRF 失败，且报错信息只
# 提示认证问题，诊断方向会被带偏。
if [[ -z "$AUTH_TOKEN" || -z "$CT0" ]]; then
  kc_auth=$(security find-generic-password -a "$USER" -s bird-x-auth-token -w 2>/dev/null)
  kc_ct0=$(security find-generic-password -a "$USER" -s bird-x-ct0 -w 2>/dev/null)
  if [[ -n "$kc_auth" && -n "$kc_ct0" ]]; then
    export AUTH_TOKEN="$kc_auth" CT0="$kc_ct0"
  fi
  unset kc_auth kc_ct0
fi

exec "$BIRD_BIN" "$@"
