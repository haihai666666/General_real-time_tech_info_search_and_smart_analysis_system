"""Helpers for interpreting crawler subprocess output."""

from __future__ import annotations

import re


_FINISH_RE = re.compile(r"Spider\s+\S+\s+finished:\s+(\d+)\s+total,\s+(\d+)\s+new")


def extract_spider_counts(stdout: str, stderr: str) -> dict[str, int]:
    """Return total/new item counts from Scrapy logs when available."""
    for stream in (stderr or "", stdout or ""):
        for line in reversed(stream.splitlines()):
            match = _FINISH_RE.search(line)
            if match:
                return {
                    "total_items": int(match.group(1)),
                    "new_items": int(match.group(2)),
                }
    return {"total_items": 0, "new_items": 0}
