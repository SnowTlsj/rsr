# -*- coding: utf-8 -*-
"""
Fix frontend source file encodings to UTF-8 (no BOM) on Windows.

Usage:
  python C:\fix_frontend_encoding.py --root "C:\path\to\rsr" --frontend "frontend"

What it does:
  - Scans frontend source files (*.vue, *.ts, *.js, *.html, *.css) under <root>/<frontend>
  - Tries to decode with a set of candidate encodings and pick the "best" one
  - Writes back as UTF-8 (no BOM) if needed
  - Creates .bak backups for any modified files (only once)
  - Inserts <meta charset="UTF-8" /> into index.html if missing
  - Prints a report, including files that contain U+FFFD replacement characters (�)
"""

from __future__ import annotations
import argparse
import os
import re
import sys
from pathlib import Path
from datetime import datetime

TEXT_EXTS = {".vue", ".ts", ".js", ".html", ".css"}

# Candidate encodings, ordered by "most likely" in CN Windows projects.
# gb18030 is a superset that can decode GBK content safely.
CANDIDATE_ENCODINGS = [
    "utf-8",
    "utf-8-sig",   # handles BOM
    "gb18030",
    "gbk",
    "cp936",       # Windows simplified Chinese
    "big5",
    "shift_jis",
    "cp1252",
    "latin1",
]

# Keywords to help decide whether decode is "plausible" for your UI.
CHINESE_KEYWORDS = [
    "中国农业大学", "肉苁蓉", "播种", "地图定位", "通道", "作业里程", "缺种", "堵塞",
]

META_CHARSET_RE = re.compile(r"<meta\s+charset\s*=\s*['\"]?utf-?8['\"]?\s*/?\s*>", re.I)

def is_text_file(p: Path) -> bool:
    if p.suffix.lower() not in TEXT_EXTS:
        return False
    # Skip common build dirs
    parts = {x.lower() for x in p.parts}
    if "node_modules" in parts or "dist" in parts or ".git" in parts:
        return False
    return True

def read_bytes(p: Path) -> bytes:
    return p.read_bytes()

def score_text(text: str) -> int:
    """
    Higher score means "more plausible".
    Penalize replacement chars and too many control chars.
    Reward presence of Chinese keywords.
    """
    score = 0
    # Penalize U+FFFD replacement chars (�)
    score -= text.count("\uFFFD") * 50

    # Penalize lots of non-whitespace control chars
    ctrl = sum(1 for ch in text if ord(ch) < 32 and ch not in "\r\n\t")
    score -= ctrl * 5

    # Reward presence of known UI keywords
    for kw in CHINESE_KEYWORDS:
        if kw in text:
            score += 200

    # Reward "normal" HTML/Vue structure
    if "<template" in text: score += 20
    if "<script" in text: score += 10
    if "<style" in text: score += 10
    if "export default" in text: score += 5

    # Very short files: small penalty to reduce false positives
    if len(text) < 50:
        score -= 5

    return score

def best_decode(data: bytes) -> tuple[str, str] | None:
    """
    Try candidate encodings and choose the decode with best score.
    Returns (encoding, text) or None if nothing works.
    """
    best = None
    best_score = -10**9
    for enc in CANDIDATE_ENCODINGS:
        try:
            txt = data.decode(enc, errors="replace")
        except Exception:
            continue
        s = score_text(txt)
        if s > best_score:
            best_score = s
            best = (enc, txt)
    return best

def write_utf8_no_bom(p: Path, text: str) -> None:
    p.write_bytes(text.encode("utf-8"))

def ensure_backup(p: Path) -> Path:
    bak = p.with_suffix(p.suffix + ".bak")
    if not bak.exists():
        bak.write_bytes(p.read_bytes())
    return bak

def ensure_index_meta_charset(index_path: Path) -> bool:
    """
    Ensure <meta charset="UTF-8" /> exists in <head>.
    Returns True if modified.
    """
    data = index_path.read_bytes()
    dec = best_decode(data)
    if not dec:
        return False
    _, txt = dec
    if META_CHARSET_RE.search(txt):
        return False

    # Insert right after <head> if present, else prepend to file.
    modified = False
    head_match = re.search(r"<head[^>]*>", txt, flags=re.I)
    meta_line = '    <meta charset="UTF-8" />\n'
    if head_match:
        insert_pos = head_match.end()
        txt2 = txt[:insert_pos] + "\n" + meta_line + txt[insert_pos:]
        txt = txt2
        modified = True
    else:
        txt = meta_line + txt
        modified = True

    if modified:
        ensure_backup(index_path)
        write_utf8_no_bom(index_path, txt)
    return modified

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="Project root directory, e.g. C:\\rsr")
    ap.add_argument("--frontend", default="frontend", help="Frontend dir name under root (default: frontend)")
    ap.add_argument("--dry-run", action="store_true", help="Scan and report only, do not modify files")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    fe = (root / args.frontend).resolve()
    if not root.exists():
        print(f"[ERROR] root does not exist: {root}")
        return 2
    if not fe.exists():
        print(f"[ERROR] frontend dir does not exist: {fe}")
        return 2

    files = [p for p in fe.rglob("*") if p.is_file() and is_text_file(p)]
    # Also consider root/index.html if exists (some Vite projects place it at root)
    root_index = root / "index.html"
    if root_index.exists():
        files.append(root_index)

    changed = []
    flagged_fffd = []
    decode_fail = []

    for p in sorted(set(files)):
        data = read_bytes(p)
        dec = best_decode(data)
        if not dec:
            decode_fail.append(str(p))
            continue

        enc, txt = dec

        # Flag if file contains replacement chars (means already corrupted or wrong encoding)
        if "\uFFFD" in txt:
            flagged_fffd.append(str(p))

        # Determine if the on-disk bytes are already UTF-8 without BOM
        # We'll re-encode and compare bytes
        utf8_bytes = txt.encode("utf-8")
        if data == utf8_bytes:
            # Already UTF-8 (or ASCII subset) with identical bytes
            continue

        if args.dry_run:
            changed.append((str(p), enc))
            continue

        ensure_backup(p)
        write_utf8_no_bom(p, txt)
        changed.append((str(p), enc))

    # Ensure meta charset in index.html files
    modified_indexes = []
    for idx in [fe / "index.html", root / "index.html"]:
        if idx.exists():
            if args.dry_run:
                # In dry run, just report whether missing
                data = idx.read_bytes()
                dec = best_decode(data)
                if dec and not META_CHARSET_RE.search(dec[1]):
                    modified_indexes.append(str(idx) + " (would insert meta charset)")
            else:
                if ensure_index_meta_charset(idx):
                    modified_indexes.append(str(idx))

    print("========== Fix Frontend Encoding Report ==========")
    print(f"Project root: {root}")
    print(f"Frontend dir : {fe}")
    print(f"Scanned files: {len(set(files))}")
    print(f"Dry run      : {args.dry_run}")
    print()

    if changed:
        print(f"[CHANGED] {len(changed)} file(s) rewritten to UTF-8 (source decode used shown):")
        for path, enc in changed[:200]:
            print(f"  - {path}  (decoded as {enc})")
        if len(changed) > 200:
            print(f"  ... {len(changed)-200} more")
        print()
    else:
        print("[CHANGED] 0 files rewritten (already UTF-8/ASCII or no changes needed).")
        print()

    if modified_indexes:
        print("[INDEX] ensured meta charset UTF-8 in:")
        for x in modified_indexes:
            print(f"  - {x}")
        print()
    else:
        print("[INDEX] no index.html modifications needed.")
        print()

    if flagged_fffd:
        print("[WARNING] These files contain U+FFFD replacement chars (�).")
        print("This usually means the original Chinese text was already corrupted at save time.")
        print("If the UI is still garbled after conversion, restore these files from git or an earlier correct copy.")
        for x in flagged_fffd[:200]:
            print(f"  - {x}")
        if len(flagged_fffd) > 200:
            print(f"  ... {len(flagged_fffd)-200} more")
        print()

    if decode_fail:
        print("[ERROR] Could not decode these files with candidate encodings:")
        for x in decode_fail[:200]:
            print(f"  - {x}")
        if len(decode_fail) > 200:
            print(f"  ... {len(decode_fail)-200} more")
        print()

    print("Backups created as: <filename>.<ext>.bak (only if modified).")
    print("==================================================")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
