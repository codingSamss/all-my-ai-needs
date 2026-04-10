#!/usr/bin/env python3
"""ELK 查询门禁：生成模板 + 校验 KQL 是否符合 skill 强约束。"""

from __future__ import annotations

import argparse
import re
import sys


MODES = ("first", "cmp", "hit_false")


def build_kql(request_id: str, target_id: str, mode: str, cmp_id: str | None) -> str:
    base = [
        f'message: "{request_id}"',
        f'message: "{target_id}"',
        'message: "TRACE_TARGET_ES"',
    ]
    if mode == "cmp":
        if not cmp_id:
            raise ValueError("mode=cmp 时必须提供 --cmp-id")
        base.append(f'message: "{cmp_id}"')
    if mode == "hit_false":
        base.append('message: "hit=false"')
    return " and ".join(base)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def validate_kql(kql: str, request_id: str, target_id: str, mode: str, cmp_id: str | None) -> tuple[bool, list[str]]:
    kql_norm = _norm(kql)
    req = request_id.lower()
    tgt = target_id.lower()
    cmp_l = (cmp_id or "").lower()

    errors: list[str] = []

    has_req = req in kql_norm
    has_tgt = tgt in kql_norm
    has_trace = "trace_target_es" in kql_norm

    if not has_req:
        errors.append("缺少 requestId（必须 requestId-first）")
    if not has_tgt:
        errors.append("缺少 targetId")
    if not has_trace:
        errors.append("缺少 TRACE_TARGET_ES")

    req_exact = (f'message: "{req}"' in kql_norm) or (f'message:"{req}"' in kql_norm)
    tgt_exact = (f'message: "{tgt}"' in kql_norm) or (f'message:"{tgt}"' in kql_norm)
    trace_exact = ('message: "trace_target_es"' in kql_norm) or ('message:"trace_target_es"' in kql_norm)

    # 首条查询强约束：必须三元组精确匹配，且禁止使用通配符
    if mode == "first":
        if "*" in kql_norm:
            errors.append("首条查询禁止使用通配符 *（例如 replay_*）")
        if not req_exact:
            errors.append("首条查询 requestId 必须完整精确匹配（不得截断/前缀/后缀）")
        if not tgt_exact:
            errors.append("首条查询 targetId 必须完整精确匹配")
        if not trace_exact:
            errors.append("首条查询必须包含精确 TRACE_TARGET_ES 条件")
        if kql_norm.count(" and ") < 2:
            errors.append("首条查询必须使用 requestId + targetId + TRACE_TARGET_ES 三条件 AND 组合")

    # 禁止 broad search：target-only 或 request-only
    if has_tgt and not has_req:
        errors.append("禁止 targetId-only broad search")
    if has_req and not has_tgt:
        errors.append("禁止 requestId-only broad search")

    # 常见偏离：只加 logger_name 的模糊检索
    if "logger_name" in kql_norm and (not has_req or not has_tgt):
        errors.append("logger_name 过滤不能替代 requestId+targetId 精确检索")

    if mode == "cmp":
        if not cmp_l:
            errors.append("mode=cmp 缺少 cmpId")
        elif cmp_l not in kql_norm:
            errors.append("mode=cmp 缺少 cmpId 条件")

    if mode == "hit_false" and "hit=false" not in kql_norm:
        errors.append("mode=hit_false 缺少 hit=false 条件")

    return (len(errors) == 0, errors)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ELK KQL 约束门禁")
    p.add_argument("--request-id", required=True)
    p.add_argument("--target-id", required=True)
    p.add_argument("--mode", choices=MODES, default="first")
    p.add_argument("--cmp-id", default=None)
    p.add_argument("--kql", default=None, help="待校验 KQL")
    p.add_argument("--emit-template", action="store_true", help="输出推荐 KQL 模板")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    if args.emit_template:
        try:
            print(build_kql(args.request_id, args.target_id, args.mode, args.cmp_id))
        except ValueError as e:
            print(f"FAIL: {e}")
            return 2

    if args.kql:
        ok, errs = validate_kql(args.kql, args.request_id, args.target_id, args.mode, args.cmp_id)
        if ok:
            print("PASS: KQL 通过门禁校验")
            return 0
        print("FAIL: KQL 未通过门禁校验")
        for e in errs:
            print(f"- {e}")
        return 2

    if not args.emit_template and not args.kql:
        print("FAIL: 至少使用 --emit-template 或 --kql 其一")
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
