#!/usr/bin/env python3
"""本地经 aicloset-server 查询线上 ai_closet_agent_new 会话记录。

运维侧只掌握用户 ID，因此分两步：
  1. list --user <用户ID>     拉该用户会话列表（按最近活跃时间倒序）
  2. show --conversation <ID> 拉指定会话的消息与请求原始记录

只用标准库，可在任何机器直接跑；server 域名用 --base-url 或环境变量
AICLOSET_SERVER_BASE_URL 指定。

示例：
  uv run python scripts/ops_conversation_records.py list --user 1024 \\
      --base-url https://<server 域名>
  uv run python scripts/ops_conversation_records.py show --conversation sty_xxx \\
      --base-url https://<server 域名>
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT_SECONDS = 20
PREVIEW_LIMIT = 28


def request_json(base_url, path, params=None):
    url = base_url.rstrip("/") + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise SystemExit(f"接口返回 {exc.code}：{detail}")
    except urllib.error.URLError as exc:
        raise SystemExit(f"无法连接 {url}：{exc.reason}")


def preview(text, limit=PREVIEW_LIMIT):
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[:limit] + "…"


def resolve_base_url(raw):
    base_url = (raw or os.getenv("AICLOSET_SERVER_BASE_URL", "")).strip()
    if not base_url:
        raise SystemExit("缺少 server 域名：用 --base-url 或在环境变量 AICLOSET_SERVER_BASE_URL 指定。")
    return base_url


def cmd_list(args):
    payload = request_json(
        resolve_base_url(args.base_url),
        f"/api/internal/stylist/records/users/{urllib.parse.quote(args.user)}/conversations",
        {
            "limit": args.limit,
            "offset": args.offset,
            "include_deleted": "true" if args.include_deleted else "false",
        },
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    conversations = payload.get("conversations") or []
    print(
        f"用户 {payload.get('user_id')}：共 {payload.get('total', 0)} 条会话，"
        f"本页 {len(conversations)} 条（limit={payload.get('limit')} offset={payload.get('offset')}"
        f"{'，含已删除' if payload.get('include_deleted') else '，不含已删除'}）"
    )
    if not conversations:
        print("（没有会话；排查会话消失时追加 --include-deleted）")
        return
    print(f"{'会话 ID':<38} {'更新时间':<21} {'消息':>4}  状态  最近一句")
    for item in conversations:
        state = "已删除" if item.get("deleted") else "正常"
        print(
            f"{item.get('conversation_id', ''):<38} {str(item.get('updated_at', ''))[:19]:<21} "
            f"{item.get('message_count', 0):>4}  {state}  {preview(item.get('last_user_message'))}"
        )


def cmd_show(args):
    payload = request_json(
        resolve_base_url(args.base_url),
        f"/api/internal/stylist/records/conversations/{urllib.parse.quote(args.conversation)}",
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    session = payload.get("session") or {}
    messages = payload.get("messages") or []
    requests = payload.get("requests") or []
    state = f"已删除（{session.get('deleted_at')}）" if session.get("deleted") else "正常"
    print(f"会话 {payload.get('conversation_id')}")
    print(
        f"  用户 {session.get('owner_id')}｜版本 {session.get('version')}｜状态 {state}"
    )
    print(f"  创建 {session.get('created_at')}｜更新 {session.get('updated_at')}")
    print(f"  消息 {len(messages)} 条｜请求记录 {len(requests)} 条")
    for message in messages:
        print(f"\n[第 {message.get('version')} 轮] {message.get('created_at')}")
        print(f"  用户：{preview(message.get('user_message'), 200)}")
        reply = message.get("reply")
        if isinstance(reply, (dict, list)):
            reply_text = json.dumps(reply, ensure_ascii=False)
        else:
            reply_text = str(reply or "")
        print(f"  回复：{preview(reply_text, 200)}")
    for record in requests:
        print(
            f"\n[请求] {record.get('request_id')}｜status={record.get('status')}"
            f"｜digest={preview(record.get('digest'), 16)}"
        )
        response = record.get("response")
        text = json.dumps(response, ensure_ascii=False) if isinstance(response, (dict, list)) else str(response or "")
        print(f"  响应：{preview(text, 300)}")


def build_parser():
    parser = argparse.ArgumentParser(description="查询线上 Stylist 会话记录（经 aicloset-server 只读接口）。")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--base-url", default="", help="server 域名，缺省读环境变量 AICLOSET_SERVER_BASE_URL。")
    common.add_argument("--json", action="store_true", help="输出原始 JSON。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", parents=[common], help="按用户 ID 列会话（时间倒序）。")
    list_parser.add_argument("--user", required=True, help="用户 ID（即 stylist 的 owner_id，纯数字）。")
    list_parser.add_argument("--limit", type=int, default=20, help="每页条数，1-100，默认 20。")
    list_parser.add_argument("--offset", type=int, default=0, help="偏移量，默认 0。")
    list_parser.add_argument("--include-deleted", action="store_true", help="连带已删除会话一起列。")
    list_parser.set_defaults(handler=cmd_list)

    show_parser = subparsers.add_parser("show", parents=[common], help="按会话 ID 查消息与请求记录。")
    show_parser.add_argument("--conversation", required=True, help="会话 ID，如 sty_xxx。")
    show_parser.set_defaults(handler=cmd_show)
    return parser


def main():
    args = build_parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
