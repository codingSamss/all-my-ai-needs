#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""按固定来源在本机组装 Mod；所有安装变更交给 Claude 官方 CLI。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[3]
PLUGIN = "pixel-buddy-sam"
MARKETPLACE = "codingSamss-all-my-ai-needs-mods"
PLUGIN_ID = PLUGIN + "@" + MARKETPLACE
ORIGINAL_ID = "pixel-buddy@marnie-plugins"
LIMIT = 512 * 1024


class Refusal(Exception):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def read_json(path, default=None):
    if not path.exists():
        return {} if default is None else default
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4 * 1024 * 1024:
        raise Refusal("配置文件类型或大小异常，停止。")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError):
        raise Refusal("配置不是有效 JSON，停止，未尝试修复。")
    if not isinstance(value, dict):
        raise Refusal("配置结构异常，停止。")
    return value


def beneath(path, root):
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def private_dir(path):
    # 不跟随缓存目录里的符号链接，避免把安装输出写进其他目录。
    # macOS 自带 /var、/tmp -> /private 的系统映射不属于用户缓存链接。
    system_aliases = {Path("/var"): Path("/private/var"), Path("/tmp"): Path("/private/tmp")}
    for ancestor in [path, *path.parents]:
        if ancestor.is_symlink() and system_aliases.get(ancestor) != ancestor.resolve():
            raise Refusal("缓存路径含符号链接，停止。")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not path.is_dir():
        raise Refusal("缓存路径不是目录。")


@contextmanager
def install_lock(cache):
    private_dir(cache)
    lock = cache / ".install-lock"
    try:
        lock.mkdir(mode=0o700)
    except FileExistsError:
        raise Refusal("已有安装锁，可能有安装进程正在运行；不自动删除或覆盖。")
    try:
        (lock / "pid").write_text(str(os.getpid()), encoding="ascii")
        yield
    finally:
        (lock / "pid").unlink(missing_ok=True)
        lock.rmdir()


def source_files():
    origin = read_json(ROOT / "origin.json")
    expected_installer = origin.get("installer_sha256", "")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_installer) or digest((ROOT / "install.py").read_bytes()) != expected_installer:
        raise Refusal("安装器与审核哈希不一致，需先审查并更新清单。")
    result = {}
    for relative, expected in origin.get("source_sha256", {}).items():
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise Refusal("来源清单非法，停止。")
        local = ROOT / "source" / path
        if local.is_symlink() or not beneath(local, ROOT / "source") or not local.is_file():
            raise Refusal("来源文件缺失或越界，停止。")
        data = local.read_bytes()
        if digest(data) != expected:
            raise Refusal("来源文件与审核哈希不一致，需先审查并更新清单。")
        result[relative] = data
    required = {".claude-plugin/plugin.json", "hooks/hooks.json", "hooks/register.tsx", "types/index.d.ts"}
    if not required.issubset(result):
        raise Refusal("插件模板不完整。")
    upstream = origin["upstream"]
    if upstream["repo"] != "hamymarnie/marnie-plugins" or not re.fullmatch(r"[0-9a-f]{40}", upstream["commit"]):
        raise Refusal("上游地址或提交不在允许范围。")
    if upstream["path"] != "plugins/pixel-buddy/hooks/scene.ts" or not re.fullmatch(r"[0-9a-f]{64}", upstream["sha256"]):
        raise Refusal("上游文件不在允许范围。")
    return origin, result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        raise Refusal("下载出现重定向，需重新审查目标。")


def upstream_scene(cache, origin, offline):
    spec = origin["upstream"]
    folder = cache / "sources"
    private_dir(folder)
    stored = folder / (spec["sha256"] + ".ts")
    if stored.exists():
        if stored.is_symlink() or not stored.is_file() or stored.stat().st_size > LIMIT:
            raise Refusal("上游缓存文件异常。")
        data = stored.read_bytes()
        if digest(data) != spec["sha256"]:
            raise Refusal("上游缓存哈希不符；保留现场，停止安装。")
        return data
    if offline:
        raise Refusal("离线模式缺少已审核的上游缓存。")
    # 匿名 HTTPS 请求一个固定文件；不读 Keychain、git credential 或项目文件。
    url = "https://raw.githubusercontent.com/" + spec["repo"] + "/" + spec["commit"] + "/" + spec["path"]
    opener = urllib.request.build_opener(NoRedirect())
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "all-my-ai-needs-pixel-buddy/1"})
        with opener.open(request, timeout=30) as response:
            data = response.read(LIMIT + 1)
    except (urllib.error.URLError, TimeoutError, OSError):
        raise Refusal("固定上游文件下载失败；请检查网络或代理，不输出凭据和环境变量。")
    if len(data) > LIMIT or digest(data) != spec["sha256"]:
        raise Refusal("下载大小或 SHA-256 不符，未执行下载内容。")
    atomic_write(stored, data)
    return data


def atomic_write(path, data):
    private_dir(path.parent)
    if path.is_symlink():
        raise Refusal("目标文件为符号链接，停止。")
    descriptor, temporary = tempfile.mkstemp(prefix=".write-", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def verify_tree(path, expected):
    if path.is_symlink() or not path.is_dir():
        raise Refusal("插件目录缺失或是符号链接。")
    for relative, data in expected.items():
        file = path / relative
        if file.is_symlink() or not beneath(file, path) or not file.is_file() or digest(file.read_bytes()) != digest(data):
            raise Refusal("插件文件存在本地改动或缺失；不覆盖。")
    for file in path.rglob("*"):
        relative = file.relative_to(path).as_posix()
        if file.is_symlink():
            raise Refusal("插件目录含符号链接。")
        if file.is_file() and relative not in expected and not relative.startswith(".in_use"):
            raise Refusal("插件目录含未声明文件；不覆盖。")


def assemble(cache, offline=False):
    origin, files = source_files()
    files["hooks/scene.ts"] = upstream_scene(cache, origin, offline)
    fingerprint = digest(json_bytes({name: digest(data) for name, data in sorted(files.items())}))[:16]
    release = cache / "releases" / fingerprint
    plugin = release / "plugin"
    if plugin.exists():
        verify_tree(plugin, files)
    else:
        private_dir(release.parent)
        with tempfile.TemporaryDirectory(prefix=".build-", dir=str(release.parent)) as temporary:
            output = Path(temporary) / "plugin"
            for relative, data in files.items():
                atomic_write(output / relative, data)
            # 先写完整包，才发布到新的版本目录；旧版本不删除、不改写。
            Path(temporary).rename(release)
    return plugin, files, fingerprint


def cli_run(binary, arguments, config, cwd):
    environment = os.environ.copy()
    environment["CLAUDE_CONFIG_DIR"] = str(config)
    try:
        completed = subprocess.run([binary, *arguments], cwd=str(cwd), env=environment,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=90, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise Refusal("官方 CLI 未能完成操作；未重启 App 或重载会话。")
    if completed.returncode:
        raise Refusal("官方 CLI 拒绝 " + " ".join(arguments[:3]) + "；未绕过权限或策略。")
    try:
        return json.loads(completed.stdout)
    except ValueError:
        return None


def state(config):
    settings = read_json(config / "settings.json")
    installed = read_json(config / "plugins" / "installed_plugins.json").get("plugins", {})
    known = read_json(config / "plugins" / "known_marketplaces.json")
    enabled = settings.get("enabledPlugins", {})
    if not isinstance(enabled, dict) or not isinstance(installed, dict):
        raise Refusal("插件登记结构异常，停止。")
    entries, selected_marketplace = installed.get(PLUGIN_ID, []), known.get(MARKETPLACE)
    if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
        raise Refusal("插件安装条目异常，停止。")
    if selected_marketplace is not None and not isinstance(selected_marketplace, dict):
        raise Refusal("市场条目异常，停止。")
    return enabled, entries, selected_marketplace


def conflicts():
    if sys.platform != "darwin":
        return  # 跨设备仍有本安装器原子锁；macOS 额外核对同插件 CLI 安装进程。
    completed = subprocess.run(["/bin/ps", "-axo", "pid=,args="], capture_output=True, text=True, timeout=10)
    if completed.returncode:
        raise Refusal("无法核对安装进程，停止。")
    for line in completed.stdout.splitlines():
        match = re.match(r"\s*(\d+)\s+(.*)", line)
        if match and int(match[1]) != os.getpid() and re.search(
            r"(?:^|\s)(?:\S*/)?claude\s+plugin\s+(?:install|update|uninstall)\s+pixel-buddy(?:-sam)?(?:@|\s|$)", match[2]):
            raise Refusal("检测到同插件安装/更新进程；不终止进程，停止本次操作。")


def catalog_for(fingerprint):
    return {"name": MARKETPLACE, "owner": {"name": "codingSamss"}, "plugins": [
        {"name": PLUGIN, "source": "./plugins/" + fingerprint}
    ]}


def publish_catalog(cache, plugin, files, fingerprint):
    root = cache / "marketplace"
    catalog = root / ".claude-plugin" / "marketplace.json"
    if catalog.exists():
        prior = read_json(catalog)
        entries = prior.get("plugins", [])
        valid = prior.get("name") == MARKETPLACE and prior.get("owner") == {"name": "codingSamss"}
        valid = valid and isinstance(entries, list) and len(entries) == 1 and isinstance(entries[0], dict)
        valid = valid and entries[0].get("name") == PLUGIN
        valid = valid and re.fullmatch(r"\./plugins/[0-9a-f]{16}", entries[0].get("source", ""))
        if not valid:
            raise Refusal("本机 marketplace 有非预期改动；不覆盖。")
    output = root / "plugins" / fingerprint
    if output.exists():
        verify_tree(output, files)
    else:
        private_dir(output.parent)
        with tempfile.TemporaryDirectory(prefix=".package-", dir=str(output.parent)) as temporary:
            for relative, data in files.items():
                atomic_write(Path(temporary) / relative, data)
            Path(temporary).rename(output)
    expected = json_bytes(catalog_for(fingerprint))
    if not catalog.exists() or catalog.read_bytes() != expected:
        atomic_write(catalog, expected)
    return root


def install(binary, config, cache, offline):
    conflicts()
    enabled, entries, known = state(config)
    if enabled.get(ORIGINAL_ID):
        raise Refusal("原版 pixel-buddy 已启用；为避免双重显示，停止。当前会话不变，请在任务结束后单独安排切换。")
    plugin, files, fingerprint = assemble(cache, offline)
    cli_run(binary, ["plugin", "validate", str(plugin), "--json"], config, plugin.parent)
    user_entry = next((entry for entry in entries if entry.get("scope") == "user"), None)
    if user_entry:
        installed = Path(user_entry.get("installPath", ""))
        if not (beneath(installed, config / "plugins") or beneath(installed, cache)):
            raise Refusal("已安装插件的路径不在受管范围。")
        # 有任何后续手工修改就停止；升级前不能用包版本号掩盖源码漂移。
        previous_manifest = read_json(installed / ".claude-plugin" / "plugin.json")
        if previous_manifest.get("version") == json.loads(files[".claude-plugin/plugin.json"])["version"]:
            verify_tree(installed, files)
            if enabled.get(PLUGIN_ID):
                print("已安装并启用，文件一致；无需重复安装。")
                return
        else:
            raise Refusal("已有其他版本；请先审查升级差异，不自动覆盖。")
    root = publish_catalog(cache, plugin, files, fingerprint)
    if known:
        source = known.get("source", {})
        if not isinstance(source, dict) or source.get("source") != "directory" or Path(source.get("path", "")).resolve() != root.resolve():
            raise Refusal("同名 marketplace 指向其他来源，停止。")
    else:
        cli_run(binary, ["plugin", "marketplace", "add", str(root), "--scope", "user", "--json"], config, root)
    if not user_entry:
        cli_run(binary, ["plugin", "install", PLUGIN_ID, "--scope", "user", "--json"], config, root)
    enabled, entries, _ = state(config)
    if not enabled.get(PLUGIN_ID):
        cli_run(binary, ["plugin", "enable", PLUGIN_ID, "--scope", "user", "--json"], config, root)
    enabled, entries, _ = state(config)
    selected = next((entry for entry in entries if entry.get("scope") == "user"), None)
    if not selected or not enabled.get(PLUGIN_ID):
        raise Refusal("官方 CLI 完成后登记/启用状态不符。")
    verify_tree(Path(selected["installPath"]), files)
    print("已安装并启用 " + PLUGIN_ID + "；请用新的 Desktop Code 本地会话验证，现有会话未重载。")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true", help="仅组装缓存，不修改 Claude 设置")
    parser.add_argument("--offline", action="store_true", help="仅使用已校验的下载缓存")
    parser.add_argument("--cache-dir", type=Path, default=Path.home() / ".cache" / "all-my-ai-needs" / "mods" / PLUGIN)
    parser.add_argument("--config-dir", type=Path, default=Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))))
    parser.add_argument("--claude-bin", default=shutil.which("claude"))
    args = parser.parse_args()
    cache, config = args.cache_dir.absolute(), args.config_dir.absolute()
    try:
        if beneath(cache, REPO):
            raise Refusal("构建缓存不得放进仓库，避免公开设备运行态文件。")
        if not args.prepare_only and not args.claude_bin:
            raise Refusal("请先安装 Claude Code CLI；本工具不自动安装系统依赖。")
        with install_lock(cache):
            if args.prepare_only:
                plugin, _, _ = assemble(cache, args.offline)
                print(str(plugin))
            else:
                # 多个缓存路径仍共享同一个配置锁，防止并发写入同一插件登记。
                with install_lock(config / "plugins" / "installer-locks" / PLUGIN):
                    install(args.claude_bin, config, cache, args.offline)
        return 0
    except (Refusal, OSError, KeyError, TypeError, AttributeError, ValueError) as error:
        print(str(error) if isinstance(error, Refusal) else "文件或元数据操作失败，停止；不输出私有配置。", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
