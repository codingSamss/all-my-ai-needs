#!/usr/bin/env python3
"""Manage X/Twitter bookmark folders (collections) via GraphQL with Chrome cookie auth.

Read actions are free to run. Write actions require --yes.
"""

import argparse
import json
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import secrets
from pathlib import Path

# Cookie extraction and the full bearer token are reused from the bird-twitter skill.
# Do NOT hardcode the bearer token here: the value published in prose is often truncated.
BIRD_SCRIPTS = Path.home() / ".codex" / "skills" / "bird-twitter" / "scripts"
sys.path.insert(0, str(BIRD_SCRIPTS))
try:
    import device_follow_timeline as dft
except ImportError:
    sys.exit(f"cannot import device_follow_timeline from {BIRD_SCRIPTS}; is the bird-twitter skill installed?")

# GraphQL operation ids, harvested 2026-07-28 from bundle.BookmarkFolders / bundle.Bookmarks.
# When X ships a new frontend these may 404 ("Query not found") or 422
# ("GRAPHQL_VALIDATION_FAILED"). See SKILL.md for the browser-based recovery procedure.
OPS = {
    "BookmarkFoldersSlice":          ("i78YDd0Tza-dV4SYs58kRg", "query"),
    "BookmarkFolderTimeline":        ("g5l-N4fpbp7B-1OAbOdGzw", "query"),
    "Bookmarks":                     ("aqjes8lRHRFG0HUglVTfNg", "query"),
    "bookmarkTweetToFolder":         ("4KHZvvNbHNf07bsgnL9gWA", "mutation"),
    "RemoveTweetFromBookmarkFolder": ("2Qbj9XZvtUvyJB4gFwWfaA", "mutation"),
    "createBookmarkFolder":          ("6Xxqpq8TM_CREYiuof_h5w", "mutation"),
    "EditBookmarkFolder":            ("a6kPp1cS1Dgbsjhapz1PNw", "mutation"),
    "DeleteBookmarkFolder":          ("2UTTsO-6zs93XqlEUZPsSg", "mutation"),
}

WRITE_THROTTLE_SEC = 1.5
API = "https://x.com/i/api/graphql"


def build_opener():
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = ssl.create_default_context()
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))


def build_headers(auth_token, ct0):
    return {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "authorization": dft.normalize_bearer_token(dft.DEFAULT_BEARER_TOKEN),
        "content-type": "application/json",
        "cookie": f"auth_token={auth_token}; ct0={ct0}",
        "origin": "https://x.com",
        "referer": "https://x.com/i/bookmarks",
        "user-agent": dft.DEFAULT_UA,
        "x-csrf-token": ct0,
        "x-twitter-active-user": "yes",
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-client-language": "en",
        "x-client-uuid": str(uuid.uuid4()),
        "x-twitter-client-deviceid": str(uuid.uuid4()),
        "x-client-transaction-id": secrets.token_hex(16),
    }


class Client:
    def __init__(self, chrome_profile="Default"):
        auth, ct0 = dft.extract_twitter_cookies_from_chrome(chrome_profile, None)
        if not auth or not ct0:
            sys.exit("could not read auth_token/ct0 from Chrome; log into x.com in Chrome first")
        self.headers = build_headers(auth, ct0)
        self.opener = build_opener()

    def call(self, op_name, variables, features=None):
        query_id, op_type = OPS[op_name]
        if op_type == "mutation":
            url = f"{API}/{query_id}/{op_name}"
            payload = {"variables": variables, "queryId": query_id}
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode(), headers=self.headers, method="POST"
            )
        else:
            params = {"variables": json.dumps(variables, separators=(",", ":"))}
            if features is not None:
                params["features"] = json.dumps(features, separators=(",", ":"))
            url = f"{API}/{query_id}/{op_name}?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(url, headers=self.headers)
        try:
            resp = self.opener.open(req, timeout=30)
            return json.loads(resp.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if e.code in (404, 422):
                sys.exit(
                    f"{op_name} failed with HTTP {e.code}: the queryId is probably stale.\n"
                    f"  {body[:200]}\n"
                    f"  Re-harvest the ids following the recovery procedure in SKILL.md."
                )
            if e.code == 401:
                sys.exit(
                    f"{op_name} failed with HTTP 401. Check that the bearer token is complete "
                    f"(use dft.DEFAULT_BEARER_TOKEN, never a value copied from prose) and that "
                    f"the Chrome session for x.com is still valid.\n  {body[:200]}"
                )
            sys.exit(f"{op_name} failed with HTTP {e.code}: {body[:300]}")


def list_folders(client):
    data = client.call("BookmarkFoldersSlice", {})
    result = data["data"]["viewer"]["user_results"]["result"]
    return result["bookmark_collections_slice"]["items"]


def folder_items(client, folder_id, count=100):
    variables = {
        "bookmark_collection_id": folder_id,
        "count": count,
        "includePromotedContent": False,
    }
    features = {
        "graphql_timeline_v2_bookmark_collection": True,
        "rweb_video_screen_enabled": False,
        "responsive_web_grok_share_attachment_enabled": True,
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "responsive_web_graphql_timeline_navigation_enabled": True,
    }
    return client.call("BookmarkFolderTimeline", variables, features)


def add_to_folder(client, tweet_id, folder_id):
    data = client.call(
        "bookmarkTweetToFolder",
        {"bookmark_collection_id": folder_id, "tweet_id": tweet_id},
    )
    return data.get("data", {}).get("bookmark_collection_tweet_put")


def remove_from_folder(client, tweet_id, folder_id):
    data = client.call(
        "RemoveTweetFromBookmarkFolder",
        {"bookmark_collection_id": folder_id, "tweet_id": tweet_id},
    )
    return data.get("data", {}).get("bookmark_collection_tweet_delete")


def create_folder(client, name):
    data = client.call("createBookmarkFolder", {"name": name})
    return data.get("data", {}).get("bookmark_collection_create")


def resolve_folder(client, ref):
    """Accept either a numeric folder id or an exact folder name."""
    if ref.isdigit():
        return ref
    for item in list_folders(client):
        if item.get("name") == ref:
            return item["id"]
    sys.exit(f"no bookmark folder named {ref!r}; run `list` to see available folders")


def require_confirmation(args, description):
    if not args.yes:
        sys.exit(f"refusing to {description} without --yes")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--chrome-profile", default="Default")
    p.add_argument("--yes", action="store_true", help="required for any write action")
    p.add_argument("--json", action="store_true", help="raw JSON output")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list all bookmark folders (read-only)")

    p_items = sub.add_parser("items", help="list tweets in a folder (read-only)")
    p_items.add_argument("folder")
    p_items.add_argument("-n", "--count", type=int, default=100)

    p_add = sub.add_parser("add", help="add a tweet to a folder (does NOT remove it elsewhere)")
    p_add.add_argument("tweet_id")
    p_add.add_argument("folder")

    p_rm = sub.add_parser("remove", help="remove a tweet from a folder (keeps the bookmark itself)")
    p_rm.add_argument("tweet_id")
    p_rm.add_argument("folder")

    p_mv = sub.add_parser("move", help="add to destination, then remove from source")
    p_mv.add_argument("tweet_id")
    p_mv.add_argument("src_folder")
    p_mv.add_argument("dst_folder")

    p_new = sub.add_parser("create", help="create a new bookmark folder")
    p_new.add_argument("name")

    args = p.parse_args()
    client = Client(args.chrome_profile)

    if args.cmd == "list":
        folders = list_folders(client)
        if args.json:
            print(json.dumps(folders, ensure_ascii=False, indent=2))
        else:
            for f in folders:
                print(f"{f['id']}  {f.get('name')}")
        return

    if args.cmd == "items":
        folder_id = resolve_folder(client, args.folder)
        data = folder_items(client, folder_id, args.count)
        if args.json:
            print(json.dumps(data, ensure_ascii=False))
        else:
            entries = (
                data.get("data", {})
                .get("bookmark_collection_timeline", {})
                .get("timeline", {})
                .get("instructions", [])
            )
            ids = []
            for ins in entries:
                for entry in ins.get("entries", []) or []:
                    eid = entry.get("entryId", "")
                    if eid.startswith("tweet-"):
                        ids.append(eid.split("-", 1)[1])
            print(f"{len(ids)} tweets in folder {folder_id}")
            for tid in ids:
                print(f"  {tid}")
        return

    if args.cmd == "add":
        require_confirmation(args, "add a tweet to a folder")
        folder_id = resolve_folder(client, args.folder)
        print(f"add {args.tweet_id} -> {folder_id}: {add_to_folder(client, args.tweet_id, folder_id)}")
        return

    if args.cmd == "remove":
        require_confirmation(args, "remove a tweet from a folder")
        folder_id = resolve_folder(client, args.folder)
        print(f"remove {args.tweet_id} from {folder_id}: {remove_from_folder(client, args.tweet_id, folder_id)}")
        return

    if args.cmd == "move":
        require_confirmation(args, "move a tweet between folders")
        src = resolve_folder(client, args.src_folder)
        dst = resolve_folder(client, args.dst_folder)
        added = add_to_folder(client, args.tweet_id, dst)
        if added != "Done":
            sys.exit(f"add step returned {added!r}; not removing from source")
        time.sleep(WRITE_THROTTLE_SEC)
        removed = remove_from_folder(client, args.tweet_id, src)
        print(f"move {args.tweet_id}: {src} -> {dst} (add={added}, remove={removed})")
        return

    if args.cmd == "create":
        require_confirmation(args, "create a bookmark folder")
        print(json.dumps(create_folder(client, args.name), ensure_ascii=False))
        return


if __name__ == "__main__":
    main()
