#!/usr/bin/env python3
"""Normalize Xiaohongshu '谁是卧底' lines into 4-word groups."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

SEP_RE = re.compile(r"[|｜,，、/\\\t ]+")
PREFIX_RE = re.compile(r"^\s*\d+\s*[\.\):：、-]*\s*")
BRACKET_NOTE_RE = re.compile(r"[（(][^）)]*[）)]")


def clean_line(line: str) -> str:
    text = line.strip()
    text = PREFIX_RE.sub("", text)
    text = BRACKET_NOTE_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def split_words(text: str) -> list[str]:
    words = [p.strip() for p in SEP_RE.split(text) if p.strip()]
    if len(words) == 1 and " " in words[0]:
        words = [p for p in words[0].split(" ") if p]
    return words


def detect_odd(words: list[str]) -> str | None:
    if len(words) != 4:
        return None
    counts = Counter(words)
    if len(counts) != 2:
        return None
    odd, odd_count = counts.most_common()[-1]
    common, common_count = counts.most_common()[0]
    if common_count == 3 and odd_count == 1:
        return odd
    return None


def parse_lines(lines: list[str]) -> list[dict]:
    groups = []
    for idx, raw in enumerate(lines, start=1):
        text = clean_line(raw)
        if not text:
            continue
        words = split_words(text)
        item = {
            "id": idx,
            "raw": raw.rstrip("\n"),
            "cleaned": text,
            "words": words,
            "odd": detect_odd(words),
            "valid": len(words) == 4,
        }
        groups.append(item)
    return groups


def load_lines(args: argparse.Namespace) -> list[str]:
    lines: list[str] = []
    if args.line:
        lines.extend(args.line)
    if args.file:
        lines.extend(Path(args.file).read_text(encoding="utf-8").splitlines())
    if not lines and not sys.stdin.isatty():
        lines.extend(sys.stdin.read().splitlines())
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse 4-word undercover groups from plain text lines."
    )
    parser.add_argument("--file", help="Input text file, one group per line.")
    parser.add_argument(
        "--line",
        action="append",
        help="Single input line, repeatable.",
    )
    parser.add_argument(
        "--only-valid",
        action="store_true",
        help="Output only rows with exactly four words.",
    )
    args = parser.parse_args()

    lines = load_lines(args)
    if not lines:
        print("[]")
        return 0

    groups = parse_lines(lines)
    if args.only_valid:
        groups = [g for g in groups if g["valid"]]

    print(json.dumps(groups, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
