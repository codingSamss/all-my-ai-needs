#!/usr/bin/env python3
"""首次丢失阶段门禁（链路驱动版）。

顺序来源优先级：
1) 运行时 CHAIN_NAME 日志（最准确）
2) 关键代码动态解析（SearchLiteFlowService + LiteFlowConstants）
3) 手工 chain-order（仅调试覆盖）
4) 默认顺序兜底
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

DOC_ORDER = [
    "full_range_meta_filter",
    "full_range_docTxtRecall",
    "recall_doc_vector_v3_filter",
    "doc_item_vector_retrieval_batch_es",
    "full_range_rerank",
]

FAQ_ORDER = [
    "full_range_meta_filter",
    "full_range_faqTxtRecall",
    "recall_faq_vector_v3_filter",
    "faq_vector_retrieval_batch_es",
    "full_range_rerank",
]

MIXED_ORDER = [
    "full_range_meta_filter",
    "full_range_faqTxtRecall",
    "full_range_docTxtRecall",
    "recall_faq_vector_v3_filter",
    "recall_doc_vector_v3_filter",
    "faq_vector_retrieval_batch_es",
    "doc_item_vector_retrieval_batch_es",
    "full_range_rerank",
]

TARGET_ORDERS = {
    "DOC": DOC_ORDER,
    "FAQ": FAQ_ORDER,
    "MIXED": MIXED_ORDER,
}

KEYWORDS = {
    "then",
    "when",
    "if",
    "elif",
    "else",
    "and",
    "or",
    "not",
    "true",
    "false",
}

SERVICE_REL = Path(
    "domain/src/main/java/com/midea/jr/robot/rag/recall/domain/search/service/SearchLiteFlowService.java"
)
CONSTANTS_REL = Path(
    "common/src/main/java/com/midea/jr/robot/rag/recall/common/constant/LiteFlowConstants.java"
)


def _to_bool(v: Any) -> bool | None:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        t = v.strip().lower()
        if t in {"true", "1", "yes"}:
            return True
        if t in {"false", "0", "no"}:
            return False
    return None


def _dedup_keep_order(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for it in items:
        v = (it or "").strip()
        if not v or v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def _parse_chain_line(line: str) -> list[str]:
    # 仅提取以小写字母开头的 cmpId，避免把 CHAIN_NAME 误识别为阶段。
    parts = re.findall(r"([a-z][A-Za-z0-9_]*)\[", line or "")
    return _dedup_keep_order(parts)


def _parse_chain_order(raw: str) -> list[str]:
    s = (raw or "").strip()
    if not s:
        return []
    if s.startswith("["):
        data = json.loads(s)
        if not isinstance(data, list):
            raise ValueError("--chain-order JSON 必须是数组")
        return _dedup_keep_order([str(x) for x in data])

    # 支持 a,b,c 或 a==>b==>c
    if "==>" in s:
        return _dedup_keep_order([p.strip() for p in s.split("==>")])
    return _dedup_keep_order([p.strip() for p in s.split(",")])


def _is_doc_text(cmp_id: str) -> bool:
    return "doctxtrecall" in cmp_id.lower()


def _is_faq_text(cmp_id: str) -> bool:
    return "faqtxtrecall" in cmp_id.lower()


def _is_vector_or_rerank(cmp_id: str) -> bool:
    c = cmp_id.lower()
    return ("vector" in c) or ("rerank" in c)


def _resolve_path(repo_root: Path, custom: str | None, fallback_rel: Path) -> Path | None:
    if custom:
        p = Path(custom).expanduser()
        if not p.is_absolute():
            p = (repo_root / p).resolve()
        return p if p.exists() else None

    p = (repo_root / fallback_rel).resolve()
    if p.exists():
        return p
    return None


def _load_text(path: Path | None) -> str:
    if path is None:
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _parse_java_string_constants(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    # 通用：public/private static final String XXX = "yyy";
    for k, v in re.findall(r"(?:public|private)\s+static\s+final\s+String\s+([A-Za-z0-9_]+)\s*=\s*\"([^\"]+)\"\s*;", text):
        out.setdefault(k, v)
    return out


def _strip_java_comments(s: str) -> str:
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    s = re.sub(r"//.*", "", s)
    return s


def _split_args(arg_text: str) -> list[str]:
    s = _strip_java_comments(arg_text)
    parts = [p.strip() for p in s.split(",")]
    return [p for p in parts if p]


def _resolve_arg_token(token: str, constants: dict[str, str]) -> str:
    t = token.strip()
    if t.startswith('"') and t.endswith('"') and len(t) >= 2:
        return t[1:-1]
    return constants.get(t, t)


def _extract_reload_chain_blocks(service_text: str) -> list[tuple[str, str, str]]:
    # 返回 (chain_token, format_str, args_text)
    pattern = re.compile(
        r"FlowBus\.reloadChain\(\s*(?P<chain>[^,]+?)\s*,\s*String\.format\(\s*\"(?P<fmt>(?:[^\"\\]|\\.)*)\"\s*,(?P<args>.*?)\)\s*\)\s*;",
        re.S,
    )
    out: list[tuple[str, str, str]] = []
    for m in pattern.finditer(service_text):
        chain_token = m.group("chain").strip()
        fmt = m.group("fmt")
        args = m.group("args")
        out.append((chain_token, fmt, args))
    return out


def _cmp_order_from_expr(expr: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", expr)
    cmp_tokens = []
    for t in tokens:
        if t.lower() in KEYWORDS:
            continue
        cmp_tokens.append(t)
    return _dedup_keep_order(cmp_tokens)


def _resolve_chain_order_from_code(
    repo_root: Path,
    chain_id: str,
    service_file: str | None,
    constants_file: str | None,
) -> list[str]:
    service_path = _resolve_path(repo_root, service_file, SERVICE_REL)
    constants_path = _resolve_path(repo_root, constants_file, CONSTANTS_REL)
    if service_path is None or constants_path is None:
        return []

    service_text = _load_text(service_path)
    constants_text = _load_text(constants_path)
    if not service_text or not constants_text:
        return []

    # 常量映射：包含 chainId 常量 + cmp 常量
    service_consts = _parse_java_string_constants(service_text)
    cmp_consts = _parse_java_string_constants(constants_text)
    all_consts = dict(cmp_consts)
    all_consts.update(service_consts)

    target_chain_ids = {chain_id, f'"{chain_id}"'}

    for chain_token, fmt, args_text in _extract_reload_chain_blocks(service_text):
        token = chain_token.strip()
        resolved_chain = token
        if token in service_consts:
            resolved_chain = service_consts[token]
        elif token.startswith('"') and token.endswith('"'):
            resolved_chain = token[1:-1]

        if resolved_chain not in target_chain_ids and resolved_chain != chain_id:
            continue

        arg_tokens = _split_args(args_text)
        resolved_args = [_resolve_arg_token(tok, all_consts) for tok in arg_tokens]
        placeholder_count = fmt.count("%s")
        if placeholder_count <= 0 or len(resolved_args) < placeholder_count:
            continue

        try:
            expr = fmt % tuple(resolved_args[:placeholder_count])
        except Exception:
            continue

        order = _cmp_order_from_expr(expr)
        if order:
            return order

    return []


def _resolve_order(args: argparse.Namespace) -> tuple[list[str], str]:
    # 1) 运行时链路（首选）
    if args.chain_line:
        order = _parse_chain_line(args.chain_line)
        if order:
            return order, "chain_line"

    # 2) 关键代码动态解析（无 chain_line 时优先）
    repo_root = Path(args.repo_root).expanduser().resolve()
    code_order = _resolve_chain_order_from_code(
        repo_root=repo_root,
        chain_id=args.chain_id,
        service_file=args.service_file,
        constants_file=args.constants_file,
    )
    if code_order:
        return code_order, "code"

    # 3) 手工覆盖（调试用）
    if args.chain_order:
        order = _parse_chain_order(args.chain_order)
        if order:
            return order, "chain_order"

    # 4) 默认兜底
    return TARGET_ORDERS[args.target_type], f"default_{args.target_type.lower()}"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="首次丢失阶段门禁（链路驱动）")
    p.add_argument("--target-type", choices=["DOC", "FAQ", "MIXED"], default="MIXED")
    p.add_argument("--events", required=True, help="ELK 证据事件 JSON 数组，元素需含 cmpId/phase/hit")
    p.add_argument("--chain-order", default=None, help="阶段顺序（JSON数组/逗号分隔/==>分隔），仅调试覆盖")
    p.add_argument("--chain-line", default=None, help="CHAIN_NAME 日志行，用于提取真实阶段顺序")
    p.add_argument("--chain-id", default="_FULL_RANGE_SEARCH_WITH_LLM_", help="用于代码解析的 chainId")
    p.add_argument("--repo-root", default=".", help="项目根目录（用于动态解析链路代码）")
    p.add_argument("--service-file", default=None, help="SearchLiteFlowService.java 路径（可选，默认按 repo-root 推导）")
    p.add_argument("--constants-file", default=None, help="LiteFlowConstants.java 路径（可选，默认按 repo-root 推导）")
    p.add_argument("--assert-first-loss", default=None, help="待校验的首次丢失 cmpId")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    try:
        raw = json.loads(args.events)
        if not isinstance(raw, list):
            raise ValueError("events 必须是 JSON 数组")
    except Exception as e:
        print(f"FAIL: events 解析失败: {e}")
        return 2

    try:
        order, order_source = _resolve_order(args)
    except Exception as e:
        print(f"FAIL: 链路顺序解析失败: {e}")
        return 2

    if not order:
        print("FAIL: 无可用链路顺序")
        return 2

    response_hits: dict[str, list[bool]] = {k: [] for k in order}
    unknown_cmps: list[str] = []

    for ev in raw:
        if not isinstance(ev, dict):
            continue
        cmp_id = str(ev.get("cmpId", "")).strip()
        phase = str(ev.get("phase", "")).strip().lower()
        hit = _to_bool(ev.get("hit"))
        if not cmp_id or phase != "response" or hit is None:
            continue
        if cmp_id in response_hits:
            response_hits[cmp_id].append(hit)
        else:
            unknown_cmps.append(cmp_id)

    if not any(response_hits.values()):
        print("BLOCKED: 没有可用的 phase=response hit 证据，无法判定首次丢失阶段")
        return 2

    stage_state: dict[str, str] = {}
    for cmp_id in order:
        vals = response_hits[cmp_id]
        if any(v is False for v in vals):
            stage_state[cmp_id] = "false"
        elif any(v is True for v in vals):
            stage_state[cmp_id] = "true"
        else:
            stage_state[cmp_id] = "unknown"

    first_loss = None
    for cmp_id in order:
        if stage_state[cmp_id] == "false":
            first_loss = cmp_id
            break

    if not first_loss:
        print("BLOCKED: 未发现 hit=false 阶段，不能输出首次丢失结论")
        return 2

    first_idx = order.index(first_loss)
    prior = order[:first_idx]

    # 关键门禁：若结论在向量/重排阶段，前序文本阶段必须已验证（不是 unknown）
    if _is_vector_or_rerank(first_loss):
        if args.target_type == "DOC":
            doc_text_prior = [c for c in prior if _is_doc_text(c)]
            for c in doc_text_prior:
                if stage_state.get(c) == "unknown":
                    print(f"BLOCKED: 未验证 {c}(response) 证据，禁止判定 DOC 向量/后序阶段为首次丢失")
                    return 2
        elif args.target_type == "FAQ":
            faq_text_prior = [c for c in prior if _is_faq_text(c)]
            for c in faq_text_prior:
                if stage_state.get(c) == "unknown":
                    print(f"BLOCKED: 未验证 {c}(response) 证据，禁止判定 FAQ 向量/后序阶段为首次丢失")
                    return 2
        else:
            # MIXED：至少要验证一个前序文本阶段，避免直接跳向量
            text_prior = [c for c in prior if _is_doc_text(c) or _is_faq_text(c)]
            if text_prior and all(stage_state.get(c) == "unknown" for c in text_prior):
                print("BLOCKED: 未验证任一前序文本召回(response)证据，禁止判定向量/后序阶段为首次丢失")
                return 2

    if args.assert_first_loss:
        claim = args.assert_first_loss.strip()
        if claim != first_loss:
            print(f"FAIL: 断言不一致，assert={claim}, actual={first_loss}")
            return 2

    print(f"PASS: FIRST_LOSS={first_loss} ORDER_SOURCE={order_source}")
    print(f"ORDER: {order}")
    for cmp_id in order:
        print(f"- {cmp_id}: {stage_state[cmp_id]}")
    if unknown_cmps:
        uniq = sorted(set(unknown_cmps))
        print(f"INFO: 未纳入当前链路顺序的 cmpId={uniq}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
