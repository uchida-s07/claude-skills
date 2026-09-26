#!/usr/bin/env python3
"""仕様駆動ワークフロー（docs/product・docs/specs）の機械点検。

雛形（product-vision/template.md、product-requirements/template-*.md、
spec-new/template-spec.md、spec-setup/template-review-notes.md）の書式に依存して
Markdown を読む。雛形の書式を変えたら、このスクリプトも直すこと。

使い方:
    python spec_check.py [all | spec <番号> | area <領域コード>] [--root DIR]
                         [--with-tests] [--tests GLOB ...] [--today YYYY-MM-DD]

終了コード: 0 = 未解決の矛盾・欠落なし / 1 = あり / 2 = 実行できない（docs が無いなど）
Python 3.8 以降の標準ライブラリだけで動く。
"""

import argparse
import datetime as dt
import fnmatch
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------- 正規表現

CODE = r"[A-Z][A-Z0-9]{1,7}"
REQ_ID = rf"{CODE}-[FN]-\d{{3}}"
REQ_RE = re.compile(rf"(?<![A-Za-z0-9-])({REQ_ID})(?![0-9])")
VISION_RE = re.compile(r"(?<![A-Za-z0-9-])([PGJ]-\d+)(?![0-9])")
TAG_RE = re.compile(rf"\[({REQ_ID})/AC-(\d+)\]")
HEAD_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
AC_LINE_RE = re.compile(r"^\s*[-*]\s*AC-(\d+)\s*[:：]\s*(.*)$")
LABEL_RE = re.compile(r"^\s*[-*]\s*\*\*(.+?)\*\*\s*[:：]?\s*(.*)$")
CHECK_RE = re.compile(r"^\s*[-*]\s*\[( |x|X)\]\s*(.*)$")
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
SEP_CELL_RE = re.compile(r"^:?-{2,}:?$")
TBD_RE = re.compile(r"未定|TBD|要検討")
RETIRED_MARK_RE = re.compile(r"^[（(]\s*廃止")
STRIKE_RE = re.compile(r"^~~(.+)~~$")

REQUIRED_ITEMS = ["概要", "事前条件", "正常フロー", "例外・バリデーション", "受入基準", "対応する要求"]
EXCLUDE_DIRS = {
    ".git", "node_modules", "vendor", "dist", "build", ".venv", "venv", "__pycache__",
    ".next", ".nuxt", "target", "coverage", ".idea", ".vscode", "docs",
}
MAX_TEST_FILE_BYTES = 2_000_000

SEV_ORDER = {"矛盾": 0, "欠落": 1, "注意": 2}


# ---------------------------------------------------------------- 読み込みの道具

def read_text(path):
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""


def strip_comments(text):
    """HTML コメントを消す（行数は保つ）。雛形の例がコメントの中にあるため。"""
    return re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)


def iter_lines(text):
    """コメントとコードブロックを除いた (行番号, 行) を返す。"""
    in_fence = False
    for i, line in enumerate(strip_comments(text).splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            yield i, line


def split_cells(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def unstrike(cell):
    m = STRIKE_RE.match(cell.strip())
    return (m.group(1).strip(), True) if m else (cell.strip(), False)


def col(header, row, name):
    """見出しに name を含む列の値を返す。無ければ None。"""
    for idx, h in enumerate(header):
        if name in h and idx < len(row):
            return row[idx]
    return None


def first_date(value):
    m = DATE_RE.search(value or "")
    if not m:
        return None
    try:
        return dt.date.fromisoformat(m.group(1))
    except ValueError:
        return None


def area_of(req_id):
    return req_id.rsplit("-", 2)[0]


class TableWalker:
    """Markdown を1行ずつ読み、見出しと表の行を追いかける。"""

    def __init__(self):
        self.heads = {}  # level -> title
        self.header = None
        self.in_table = False

    def feed(self, line):
        """戻り値: ("head", level, title) / ("row", header, cells) / ("sep",) / ("text", line)"""
        m = HEAD_RE.match(line)
        if m:
            level = len(m.group(1))
            self.heads[level] = m.group(2)
            for deeper in [k for k in self.heads if k > level]:
                del self.heads[deeper]
            self.in_table = False
            return ("head", level, m.group(2))
        if line.strip().startswith("|"):
            cells = split_cells(line)
            if not self.in_table:
                self.in_table = True
                self.header = cells
                return ("sep",)
            if all(SEP_CELL_RE.match(c) or c == "" for c in cells):
                return ("sep",)
            return ("row", self.header, cells)
        self.in_table = False
        return ("text", line)

    def h(self, level):
        return self.heads.get(level, "")


# ---------------------------------------------------------------- データ

class Req:
    def __init__(self, rid, file, line, kind, marker=""):
        self.id = rid
        self.area = area_of(rid)
        self.file = file
        self.line = line
        self.kind = kind  # heading / table
        self.marker = marker  # spec の見出しの（新規）（変更）
        self.acs = {}  # 番号 -> 有効か
        self.ac_dups = []
        self.vision_refs = []
        self.pre_refs = []
        self.items = set()
        self.text = []

    @property
    def active_acs(self):
        return sorted(n for n, ok in self.acs.items() if ok)

    def add_line(self, line):
        self.text.append(line)
        m = AC_LINE_RE.match(line)
        if m:
            n = int(m.group(1))
            if n in self.acs:
                self.ac_dups.append(n)
            self.acs[n] = not RETIRED_MARK_RE.match(m.group(2).strip())
            return
        m = LABEL_RE.match(line)
        if m:
            label = re.sub(r"[（(].*?[）)]", "", m.group(1)).strip()
            self.items.add(label)
            if label == "対応する要求":
                self.vision_refs += VISION_RE.findall(m.group(2))
            elif label == "事前条件":
                self.pre_refs += REQ_RE.findall(m.group(2))


class Finding:
    def __init__(self, check, target, sev, loc, msg, areas=(), specs=()):
        self.key = f"SC:{check}:{target}"
        self.check = check
        self.sev = sev
        self.loc = loc
        self.msg = msg
        self.areas = set(areas)
        self.specs = set(specs)


# ---------------------------------------------------------------- 各文書の読み込み

def parse_vision(path, rel):
    info = {"exists": path.exists(), "active": {}, "retired": {}, "dups": [], "refs": [], "tbd": []}
    if not info["exists"]:
        return info
    text = read_text(path)
    w = TableWalker()
    for i, line in iter_lines(text):
        if TBD_RE.search(line):
            info["tbd"].append(i)
        ev = w.feed(line)
        if ev[0] != "row":
            continue
        header, row = ev[1], ev[2]
        cell, struck = unstrike(row[0])
        if not re.fullmatch(r"[PGJ]-\d+", cell):
            # 成功指標の表などは1列目が ID ではない
            goal_ref = col(header, row, "対応するゴール")
            if goal_ref:
                for ref in VISION_RE.findall(goal_ref):
                    info["refs"].append((f"成功指標({row[0]})", ref, i))
            continue
        bucket = info["retired"] if struck else info["active"]
        if cell in info["active"] or cell in info["retired"]:
            info["dups"].append((cell, i))
        bucket[cell] = i
        solves = col(header, row, "解決する課題")
        if solves:
            for ref in VISION_RE.findall(solves):
                info["refs"].append((cell, ref, i))
    return info


def parse_area_file(path, rel):
    info = {"reqs": [], "index": [], "retired": [], "notdo_refs": [], "h2": set(), "tbd": []}
    w = TableWalker()
    block = None
    for i, line in iter_lines(read_text(path)):
        if TBD_RE.search(line):
            info["tbd"].append(i)
        ev = w.feed(line)
        if ev[0] == "head":
            level, title = ev[1], ev[2]
            if level <= 3:
                block = None
            if level == 2:
                info["h2"].add(title)
            if level == 3 and "廃止" not in w.h(2):
                m = re.match(rf"^({REQ_ID})\b", title)
                if m:
                    block = Req(m.group(1), rel, i, "heading")
                    info["reqs"].append(block)
            continue
        if ev[0] == "row":
            header, row = ev[1], ev[2]
            cell, _ = unstrike(row[0])
            h2 = w.h(2)
            if "やらない" in h2:
                ref_cell = col(header, row, "対応する要求") or " ".join(row)
                info["notdo_refs"] += VISION_RE.findall(ref_cell)
                continue
            if not re.fullmatch(REQ_ID, cell):
                continue
            if "廃止" in h2:
                info["retired"].append((cell, i))
            elif "要件一覧" in h2:
                refs = VISION_RE.findall(col(header, row, "対応する要求") or "")
                info["index"].append((cell, i, refs))
            else:
                r = Req(cell, rel, i, "table")
                r.vision_refs = VISION_RE.findall(col(header, row, "対応する要求") or "")
                r.items = {"概要", "事前条件", "正常フロー", "例外・バリデーション", "受入基準"}
                if col(header, row, "対応する要求"):
                    r.items.add("対応する要求")
                src = col(header, row, "出典")
                if src:
                    r.items.add("出典")
                r.text = [" ".join(row)]
                info["reqs"].append(r)
            continue
        if ev[0] == "text" and block is not None:
            block.add_line(ev[1])
    return info


def parse_readme(path):
    info = {"exists": path.exists(), "areas": {}}
    if not info["exists"]:
        return info
    w = TableWalker()
    for i, line in iter_lines(read_text(path)):
        ev = w.feed(line)
        if ev[0] == "row" and "領域一覧" in w.h(2):
            code = ev[2][0]
            file_ = col(ev[1], ev[2], "ファイル")
            if re.fullmatch(CODE, code):
                info["areas"][code] = ((file_ or "").strip("` "), i)
    return info


def parse_spec(path, rel, num):
    spec = {
        "num": num, "file": rel, "fields": {}, "targets": [], "new_areas": [],
        "blocks": {}, "open": [], "h2": [], "h3": [], "related": [], "tbd": [],
    }
    w = TableWalker()
    block = None
    in_questions = False
    for i, line in iter_lines(read_text(path)):
        m = re.match(r"^(tier|status|created|approved|done|review)\s*:\s*(.*)$", line)
        if m and not w.heads.get(2):
            spec["fields"][m.group(1)] = m.group(2).strip()
            continue
        ev = w.feed(line)
        if ev[0] == "head":
            level, title = ev[1], ev[2]
            if level <= 4:
                block = None
            if level == 2:
                spec["h2"].append(title)
                in_questions = "未決事項" in title
            if level == 3:
                spec["h3"].append(title)
            if level == 4:
                m2 = re.match(rf"^({REQ_ID})\b", title)
                if m2:
                    marker = "新規" if "新規" in title else "変更" if "変更" in title else ""
                    block = Req(m2.group(1), rel, i, "heading", marker)
                    if block.id in spec["blocks"]:
                        spec.setdefault("block_dups", []).append((block.id, i))
                    spec["blocks"][block.id] = block
            continue
        if ev[0] == "row":
            header, row = ev[1], ev[2]
            h3 = w.h(3)
            cell, _ = unstrike(row[0])
            if "新しい領域" in h3 and re.fullmatch(CODE, cell):
                spec["new_areas"].append(cell)
            elif re.fullmatch(REQ_ID, cell) and ("対象の要件" in h3 or "非機能要件" in h3 or "廃止する要件" in h3):
                kind = "廃止" if "廃止する要件" in h3 else (col(header, row, "区分") or "").strip()
                refs = VISION_RE.findall(col(header, row, "対応する要求") or "")
                spec["targets"].append({"id": cell, "kind": kind, "refs": refs, "line": i})
            continue
        if ev[0] != "text":
            continue
        text = ev[1]
        if in_questions:
            m3 = CHECK_RE.match(text)
            if m3 and m3.group(1) == " " and m3.group(2).strip():
                spec["open"].append((i, m3.group(2).strip()))
            continue
        if block is not None:
            block.add_line(text)
            continue
        m4 = re.match(r"^\s*[-*]\s*関連する要求\s*[:：]\s*(.*)$", text)
        if m4:
            spec["related"] += VISION_RE.findall(m4.group(1))
    spec["status"] = (spec["fields"].get("status", "").split() or [""])[0]
    return spec


def parse_notes(path):
    info = {"exists": path.exists(), "keys": [], "last_full": None}
    if not info["exists"]:
        return info
    text = read_text(path)
    m = re.search(r"最後の全体レビュー\s*[:：]\s*(\S+)", strip_comments(text))
    if m:
        info["last_full"] = first_date(m.group(1))
    # 表の見出し行に頼らない（行の追記位置がずれても読めるように）。SC: で始まるセルをキーとみなす。
    for _, line in iter_lines(text):
        if line.strip().startswith("|"):
            for cell in split_cells(line):
                key = cell.strip("` ")
                if key.startswith("SC:"):
                    info["keys"].append(key)
    return info


def parse_config(path):
    cfg = {"done_threshold": 3, "open_threshold": 2, "stale_days": 30, "test_globs": []}
    if not path.exists():
        return cfg
    text = strip_comments(read_text(path))
    for key, pat in [
        ("done_threshold", r"全体レビューを勧める\s*done\s*の件数\s*[:：]\s*(\d+)"),
        ("open_threshold", r"全体レビューを勧める進行中\s*spec\s*の件数\s*[:：]\s*(\d+)"),
        ("stale_days", r"approved\s*のまま注意を出す日数\s*[:：]\s*(\d+)"),
    ]:
        m = re.search(pat, text)
        if m:
            cfg[key] = int(m.group(1))
    m = re.search(r"テストの置き場所\s*[:：]\s*(.*)", text)
    if m:
        cfg["test_globs"] = re.findall(r"`([^`]+)`", m.group(1))
    return cfg


def collect_test_tags(root, globs):
    """テストのタグ [<要件ID>/AC-n] を集める。-> {(要件ID, n): [場所, ...]}"""
    tags = {}
    if globs:
        files = set()
        for g in globs:
            files.update(p for p in root.glob(g) if p.is_file())
    else:
        files = set()
        stack = [root]
        while stack:
            d = stack.pop()
            try:
                entries = list(d.iterdir())
            except OSError:
                continue
            for p in entries:
                if p.is_dir():
                    if p.name not in EXCLUDE_DIRS and not p.name.startswith("."):
                        stack.append(p)
                elif p.is_file():
                    files.add(p)
    for p in sorted(files):
        if p.suffix.lower() in {".md", ".markdown"}:
            continue
        try:
            if p.stat().st_size > MAX_TEST_FILE_BYTES:
                continue
            data = p.read_bytes()
        except OSError:
            continue
        if b"\x00" in data[:4096]:
            continue
        text = data.decode("utf-8", errors="replace")
        for m in TAG_RE.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            rel = p.relative_to(root).as_posix()
            tags.setdefault((m.group(1), int(m.group(2))), []).append(f"{rel}:{line}")
    return tags


# ---------------------------------------------------------------- 点検

def run_checks(root, mode, target, with_tests, extra_globs, today):
    docs = root / "docs"
    if not docs.is_dir():
        raise SystemExit(f"docs/ が見つかりません: {docs}")
    req_dir = docs / "product" / "requirements"
    F = []

    def add(*args, **kw):
        F.append(Finding(*args, **kw))

    cfg = parse_config(root / "CLAUDE.md")
    vision = parse_vision(docs / "product" / "vision.md", "docs/product/vision.md")
    readme = parse_readme(req_dir / "README.md")
    notes = parse_notes(docs / "review-notes.md")

    # ---- 常設要件
    area_files = {}
    if req_dir.is_dir():
        for p in sorted(req_dir.glob("*.md")):
            if p.name.lower() == "readme.md":
                continue
            rel = p.relative_to(root).as_posix()
            area_files[p.name] = (rel, parse_area_file(p, rel))

    standing = {}  # id -> Req
    retired = {}  # id -> 場所
    notdo_refs = set()
    index_refs = set()
    for fname, (rel, info) in area_files.items():
        for rid, line in info["retired"]:
            retired[rid] = f"{rel}:{line}"
        notdo_refs.update(info["notdo_refs"])
        for r in info["reqs"]:
            if r.id in standing:
                prev = standing[r.id]
                add("dup-id", r.id, "矛盾", f"{rel}:{r.line}",
                    f"{r.id} が2か所で定義されている（もう1か所: {prev.file}:{prev.line}）", areas=[r.area])
                continue
            standing[r.id] = r
        for rid, line, refs in info["index"]:
            index_refs.update(refs)

    for rid, loc in retired.items():
        if rid in standing:
            add("dup-id", f"{rid}:廃止", "矛盾", loc,
                f"{rid} が「廃止した要件」にあるのに、有効な要件としても定義されている（{standing[rid].file}:{standing[rid].line}）",
                areas=[area_of(rid)])

    vision_ids = set(vision["active"]) | set(vision["retired"])

    def check_vision_ref(owner, ref, loc, areas=(), specs=()):
        if not vision["exists"]:
            return
        if ref in vision["retired"]:
            add("ref-retired", f"{owner}->{ref}", "欠落", loc,
                f"{owner} が廃止済みの vision 項目 {ref} を参照している", areas=areas, specs=specs)
        elif ref not in vision_ids:
            add("ref-missing", f"{owner}->{ref}", "欠落", loc,
                f"{owner} が vision.md に無い {ref} を参照している", areas=areas, specs=specs)

    # vision の中
    for rid, line in vision["dups"]:
        add("dup-id", rid, "矛盾", f"docs/product/vision.md:{line}", f"vision.md で {rid} が重複している")
    for owner, ref, line in vision["refs"]:
        check_vision_ref(owner, ref, f"docs/product/vision.md:{line}")

    for r in standing.values():
        loc = f"{r.file}:{r.line}"
        # 項目の揃い
        if r.kind == "heading":
            needed = REQUIRED_ITEMS + ["出典"]
            if r.id.split("-")[-2] == "N":
                needed = ["概要", "受入基準", "対応する要求", "出典"]
            for item in needed:
                if item not in r.items:
                    add("section-missing", f"{r.id}:{item}", "欠落", loc,
                        f"{r.id} に「{item}」が無い", areas=[r.area])
        else:
            for item in ("対応する要求", "出典"):
                if item not in r.items:
                    add("section-missing", f"{r.id}:{item}", "欠落", loc,
                        f"{r.id} の「{item}」列が空", areas=[r.area])
        for n in r.ac_dups:
            add("dup-id", f"{r.id}/AC-{n}", "矛盾", loc, f"{r.id} の AC-{n} が重複している", areas=[r.area])
        # 受入基準
        if r.id.split("-")[-2] == "F" and not r.active_acs:
            add("no-ac", r.id, "欠落", loc, f"機能要件 {r.id} に有効な受入基準が無い", areas=[r.area])
        # 参照
        for ref in r.vision_refs:
            check_vision_ref(r.id, ref, loc, areas=[r.area])
        for ref in r.pre_refs:
            if ref == r.id:
                continue
            if ref in retired and ref not in standing:
                add("ref-retired", f"{r.id}->{ref}", "欠落", loc,
                    f"{r.id} の事前条件が廃止済みの要件 {ref} を参照している", areas=[r.area])
            elif ref not in standing:
                add("ref-missing", f"{r.id}->{ref}", "欠落", loc,
                    f"{r.id} の事前条件が存在しない要件 {ref} を参照している", areas=[r.area])

    # 要件一覧と本文の一致
    for fname, (rel, info) in area_files.items():
        listed = {rid for rid, _, _ in info["index"]}
        defined = {r.id for r in info["reqs"] if r.kind == "heading"}
        if "要件一覧" in " ".join(info["h2"]):
            for rid, line, _ in info["index"]:
                if rid not in defined:
                    add("index-mismatch", rid, "欠落", f"{rel}:{line}",
                        f"{rid} が要件一覧にあるのに、本文に見出しが無い", areas=[area_of(rid)])
            for rid in sorted(defined - listed):
                r = standing.get(rid)
                if r and r.file == rel:
                    add("index-mismatch", rid, "欠落", f"{rel}:{r.line}",
                        f"{rid} の見出しがあるのに、要件一覧に無い", areas=[area_of(rid)])
        # 節の揃い
        is_common = fname.lower() == "common.md"
        needed = ["非機能要件", "廃止した要件"] if is_common else ["要件一覧", "機能要件", "非機能要件", "やらないこと", "廃止した要件"]
        for sec in needed:
            if not any(sec in h for h in info["h2"]):
                add("section-missing", f"{rel}:{sec}", "欠落", rel, f"節「{sec}」が無い",
                    areas=[a for a in {r.area for r in info["reqs"]}] or ["?"])
        if info["tbd"]:
            add("tbd", rel, "欠落", f"{rel}:{','.join(map(str, info['tbd'][:10]))}",
                "常設要件に「未定」「TBD」「要検討」が残っている",
                areas=[a for a in {r.area for r in info["reqs"]}])
    if vision["tbd"]:
        add("tbd", "docs/product/vision.md", "欠落",
            f"docs/product/vision.md:{','.join(map(str, vision['tbd'][:10]))}",
            "vision.md に「未定」「TBD」「要検討」が残っている")

    # ---- spec
    specs = {}
    specs_dir = docs / "specs"
    if specs_dir.is_dir():
        for d in sorted(specs_dir.iterdir()):
            m = re.match(r"^(\d{3})", d.name)
            if d.is_dir() and m and (d / "spec.md").exists():
                rel = (d / "spec.md").relative_to(root).as_posix()
                specs[m.group(1)] = parse_spec(d / "spec.md", rel, m.group(1))
    open_specs = {n: s for n, s in specs.items() if s["status"] in ("draft", "approved")}
    open_new_areas = {a for s in open_specs.values() for a in s["new_areas"]}

    # 予約の重なり
    reserved = {}
    for n, s in open_specs.items():
        for t in s["targets"]:
            if t["kind"] == "新規":
                reserved.setdefault(t["id"], []).append((n, t["line"]))
    for rid, owners in reserved.items():
        for n, line in owners:
            loc = f"{specs[n]['file']}:{line}"
            # /spec-close の途中（常設要件へ移した後、done にする前）は、出典がこの spec なら衝突ではない
            merged_from_this = rid in standing and f"specs/{n}" in "\n".join(standing[rid].text)
            if (rid in standing and not merged_from_this) or rid in retired:
                add("id-reserve-clash", f"{rid}@{n}", "矛盾", loc,
                    f"spec {n} が新規として予約した {rid} は、常設要件ですでに使われている",
                    areas=[area_of(rid)], specs=[n])
        if len(owners) > 1:
            nums = [n for n, _ in owners]
            add("id-reserve-clash", rid, "矛盾", ", ".join(f"{specs[n]['file']}:{l}" for n, l in owners),
                f"{rid} を複数の spec（{', '.join(nums)}）が新規として予約している",
                areas=[area_of(rid)], specs=nums)

    all_open_new = set(reserved)
    for n, s in specs.items():
        sp = [n]
        rel = s["file"]
        # 節の揃い
        for sec in ("要求", "要件", "変更差分", "未決事項"):
            if not any(sec in h for h in s["h2"]):
                add("section-missing", f"{n}:{sec}", "欠落", rel, f"spec {n} に節「{sec}」が無い", specs=sp)
        if not any("対象の要件" in h for h in s["h3"]):
            add("section-missing", f"{n}:対象の要件", "欠落", rel, f"spec {n} に「対象の要件」の表が無い", specs=sp)
        for fld in ("tier", "status"):
            if not s["fields"].get(fld):
                add("section-missing", f"{n}:{fld}", "欠落", rel, f"spec {n} の {fld}: が空", specs=sp)
        for rid, line in s.get("block_dups", []):
            add("dup-id", f"{n}:{rid}", "矛盾", f"{rel}:{line}", f"spec {n} で {rid} の見出しが重複している", specs=sp)

        # 未決事項
        if s["open"]:
            sev = "注意" if s["status"] == "draft" else "欠落"
            add("open-question", n, sev, f"{rel}:{s['open'][0][0]}",
                f"spec {n}（{s['status'] or '状態不明'}）に未決事項が {len(s['open'])} 件残っている", specs=sp)

        if s["status"] == "done":
            # done なのに常設要件に移されていない
            for t in s["targets"]:
                rid, kind = t["id"], t["kind"]
                loc = f"{rel}:{t['line']}"
                if kind in ("新規", "変更"):
                    r = standing.get(rid)
                    if r is None:
                        add("done-not-merged", f"{n}:{rid}", "欠落", loc,
                            f"done の spec {n} の {rid}（{kind}）が常設要件に無い", areas=[area_of(rid)], specs=sp)
                    elif f"specs/{n}" not in "\n".join(r.text):
                        add("done-not-merged", f"{n}:{rid}", "欠落", loc,
                            f"done の spec {n} の {rid}（{kind}）の出典に specs/{n} が無い", areas=[area_of(rid)], specs=sp)
                elif kind == "廃止" and rid not in retired:
                    add("done-not-merged", f"{n}:{rid}", "欠落", loc,
                        f"done の spec {n} で廃止した {rid} が「廃止した要件」表に無い", areas=[area_of(rid)], specs=sp)
            continue  # done の spec の中身は常設要件側で点検する

        # 参照（draft / approved）
        for ref in s["related"]:
            check_vision_ref(f"spec {n}", ref, rel, specs=sp)
        target_ids = {t["id"] for t in s["targets"]}
        for t in s["targets"]:
            rid, kind = t["id"], t["kind"]
            loc = f"{rel}:{t['line']}"
            for ref in t["refs"]:
                check_vision_ref(rid, ref, loc, areas=[area_of(rid)], specs=sp)
            if kind not in ("新規", "変更", "廃止"):
                add("section-missing", f"{n}:{rid}:区分", "欠落", loc,
                    f"spec {n} の {rid} の区分が「新規 / 変更 / 廃止」のどれでもない（{kind or '空'}）",
                    areas=[area_of(rid)], specs=sp)
            if kind in ("変更", "廃止"):
                if rid in retired and rid not in standing:
                    add("ref-retired", f"{n}:{rid}", "欠落", loc,
                        f"spec {n} が{kind}しようとしている {rid} はすでに廃止されている", areas=[area_of(rid)], specs=sp)
                elif rid not in standing:
                    add("ref-missing", f"{n}:{rid}", "欠落", loc,
                        f"spec {n} が{kind}しようとしている {rid} が常設要件に無い", areas=[area_of(rid)], specs=sp)
            if kind in ("新規", "変更") and rid.split("-")[-2] == "F" and rid not in s["blocks"]:
                add("section-missing", f"{n}:{rid}:変更後の姿", "欠落", loc,
                    f"spec {n} に {rid} の「変更後の姿」の見出しが無い", areas=[area_of(rid)], specs=sp)
            code = area_of(rid)
            if readme["exists"] and code not in readme["areas"] and code not in s["new_areas"]:
                add("area-registry", f"{n}:{code}", "欠落", loc,
                    f"spec {n} が未登録の領域コード {code} を使っている（「新しい領域」にも無い）", areas=[code], specs=sp)
        for rid, b in s["blocks"].items():
            loc = f"{rel}:{b.line}"
            if rid not in target_ids:
                add("section-missing", f"{n}:{rid}:対象の要件", "欠落", loc,
                    f"spec {n} の {rid} の見出しがあるのに「対象の要件」の表に無い", areas=[b.area], specs=sp)
            needed = REQUIRED_ITEMS if rid.split("-")[-2] == "F" else ["概要", "受入基準", "対応する要求"]
            for item in needed:
                if item not in b.items:
                    add("section-missing", f"{n}:{rid}:{item}", "欠落", loc,
                        f"spec {n} の {rid} に「{item}」が無い", areas=[b.area], specs=sp)
            if rid.split("-")[-2] == "F" and not b.active_acs:
                add("no-ac", f"{n}:{rid}", "欠落", loc, f"spec {n} の {rid} に有効な受入基準が無い", areas=[b.area], specs=sp)
            for dn in b.ac_dups:
                add("dup-id", f"{n}:{rid}/AC-{dn}", "矛盾", loc, f"spec {n} の {rid} で AC-{dn} が重複している", specs=sp)
            for ref in b.vision_refs:
                check_vision_ref(rid, ref, loc, areas=[b.area], specs=sp)
            for ref in b.pre_refs:
                if ref == rid or ref in target_ids or ref in all_open_new:
                    continue
                if ref in retired and ref not in standing:
                    add("ref-retired", f"{n}:{rid}->{ref}", "欠落", loc,
                        f"spec {n} の {rid} の事前条件が廃止済みの要件 {ref} を参照している", areas=[b.area], specs=sp)
                elif ref not in standing:
                    add("ref-missing", f"{n}:{rid}->{ref}", "欠落", loc,
                        f"spec {n} の {rid} の事前条件が存在しない要件 {ref} を参照している", areas=[b.area], specs=sp)
            # 変更した要件で、常設要件にあった AC が黙って消えていないか
            if b.marker == "変更" and rid in standing:
                for an in standing[rid].acs:
                    if an not in b.acs:
                        add("section-missing", f"{n}:{rid}/AC-{an}", "欠落", loc,
                            f"spec {n} の {rid} に、常設要件の AC-{an} が無い（残すなら書き写し、無くすなら「（廃止）」と書く）",
                            areas=[b.area], specs=sp)

        # 承認後に長く放置
        if s["status"] == "approved":
            ad = first_date(s["fields"].get("approved"))
            if ad and (today - ad).days >= cfg["stale_days"]:
                add("stale-approved", n, "注意", rel,
                    f"spec {n} が approved のまま {(today - ad).days} 日経っている", specs=sp)
            if not ad:
                add("section-missing", f"{n}:approved", "欠落", rel, f"spec {n} が approved なのに approved: が空", specs=sp)
        if s["status"] == "done" and not first_date(s["fields"].get("done")):
            add("section-missing", f"{n}:done", "欠落", rel, f"spec {n} が done なのに done: が空", specs=sp)

    # ---- 領域の登録
    if req_dir.is_dir():
        if not readme["exists"]:
            add("area-registry", "README", "欠落", "docs/product/requirements/README.md", "requirements/README.md が無い")
        else:
            reg_files = {f: c for c, (f, _) in readme["areas"].items()}
            for code, (f, line) in readme["areas"].items():
                if f and f not in area_files:
                    add("area-registry", code, "欠落", f"docs/product/requirements/README.md:{line}",
                        f"領域一覧の {code} のファイル {f} が無い", areas=[code])
            for fname, (rel, info) in area_files.items():
                if fname not in reg_files:
                    add("area-registry", fname, "欠落", rel, f"{fname} が README の領域一覧に無い",
                        areas=[r.area for r in info["reqs"]])
            for r in standing.values():
                if r.area not in readme["areas"]:
                    add("area-registry", r.id, "欠落", f"{r.file}:{r.line}",
                        f"{r.id} の領域コード {r.area} が README の領域一覧に無い", areas=[r.area])

    # ---- テスト
    tags = None
    need_tests = mode in ("all", "area") or (mode == "spec" and with_tests)
    if need_tests:
        tags = collect_test_tags(root, extra_globs or cfg["test_globs"])
    if tags is not None and mode in ("all", "area"):
        for r in standing.values():
            for an in r.active_acs:
                if (r.id, an) not in tags:
                    add("ac-no-test", f"{r.id}/AC-{an}", "欠落", f"{r.file}:{r.line}",
                        f"{r.id}/AC-{an} に対応するテスト（[{r.id}/AC-{an}]）が無い", areas=[r.area])
        open_acs = {(rid, an) for s in open_specs.values() for rid, b in s["blocks"].items() for an in b.active_acs}
        for (rid, an), locs in sorted(tags.items()):
            r = standing.get(rid)
            if (r is not None and r.acs.get(an)) or (rid, an) in open_acs:
                continue
            why = "廃止された" if (r is not None and an in r.acs) or rid in retired else "存在しない"
            add("test-orphan", f"{rid}/AC-{an}", "欠落", ", ".join(locs[:3]),
                f"テストのタグ [{rid}/AC-{an}] が{why} AC を指している", areas=[area_of(rid)])
    if tags is not None and mode == "spec":
        s = specs.get(target)
        if s:
            for rid, b in s["blocks"].items():
                for an in b.active_acs:
                    if (rid, an) not in tags:
                        add("ac-no-test", f"{rid}/AC-{an}", "欠落", f"{s['file']}:{b.line}",
                            f"{rid}/AC-{an} に対応するテスト（[{rid}/AC-{an}]）が無い", areas=[b.area], specs=[target])

    # ---- vision の拾い漏れ
    if mode == "all" and vision["exists"]:
        used = set(notdo_refs) | index_refs
        for r in standing.values():
            used.update(r.vision_refs)
        sev = "欠落" if standing else "注意"
        for vid, line in sorted(vision["active"].items(), key=lambda kv: kv[1]):
            if vid not in used:
                add("vision-unused", vid, sev, f"docs/product/vision.md:{line}",
                    f"{vid} がどの要件の「対応する要求」にも「やらないこと」にも出てこない")

    # ---- 情報
    info = []
    info.append(f"進行中の spec: {len(open_specs)} 件"
                + (f"（{', '.join(sorted(open_specs))}）" if open_specs else "")
                + f" / 全体レビューを勧める基準: {cfg['open_threshold']} 件")
    last = notes["last_full"]
    done_since = sorted(n for n, s in specs.items() if s["status"] == "done"
                        and (last is None or (first_date(s["fields"].get("done")) or dt.date.min) > last))
    info.append(f"最後の全体レビュー: {last.isoformat() if last else '未実施'}"
                f" / それ以降に done になった spec: {len(done_since)} 件"
                + (f"（{', '.join(done_since)}）" if done_since else "")
                + f" / 全体レビューを勧める基準: {cfg['done_threshold']} 件")
    if len(open_specs) >= cfg["open_threshold"]:
        info.append("→ 進行中の spec が基準に達している（タイミング⑨: docs-review all を勧める）")
    if len(done_since) >= cfg["done_threshold"]:
        info.append("→ done の spec が基準に達している（タイミング⑧: docs-review all を勧める）")
    if not vision["exists"]:
        info.append("vision.md が無いため、vision への参照は点検していない")
    if not req_dir.is_dir():
        info.append("docs/product/requirements/ が無いため、常設要件は点検していない")
    if mode == "spec" and not with_tests:
        info.append("AC とテストの対応は点検していない（--with-tests を付けると点検する）")
    if tags is not None:
        info.append(f"見つかったテストのタグ: {len(tags)} 種類")

    return F, info, notes, specs, readme


# ---------------------------------------------------------------- 出力

def select(findings, mode, target):
    if mode == "all":
        return findings
    if mode == "spec":
        return [f for f in findings if target in f.specs]
    return [f for f in findings if target in f.areas]


def suppressed(f, patterns):
    return any(f.key == p or fnmatch.fnmatchcase(f.key, p) for p in patterns)


def render(root, mode, target, findings, info, notes):
    kept = [f for f in findings if not suppressed(f, notes["keys"])]
    dropped = len(findings) - len(kept)
    kept.sort(key=lambda f: (SEV_ORDER[f.sev], f.check, f.key))
    counts = {s: sum(1 for f in kept if f.sev == s) for s in SEV_ORDER}
    passed = counts["矛盾"] == 0 and counts["欠落"] == 0
    scope = "all（全体）" if mode == "all" else f"{mode} {target}"
    out = ["# spec-check 結果", "",
           f"- 範囲: {scope}",
           f"- ルート: {root}",
           f"- 除外済み: {dropped} 件（docs/review-notes.md）", "",
           f"| 矛盾 | 欠落 | 注意 |", "|---|---|---|",
           f"| {counts['矛盾']} | {counts['欠落']} | {counts['注意']} |", ""]
    if kept:
        out += ["## 指摘", "", "| キー | 重大度 | 場所 | 内容 |", "|---|---|---|---|"]
        for f in kept:
            out.append(f"| `{f.key}` | {f.sev} | {f.loc} | {f.msg} |")
        out.append("")
    else:
        out += ["## 指摘", "", "なし", ""]
    out += ["## 情報", ""] + [f"- {line}" for line in info] + [""]
    out.append(f"判定: {'合格' if passed else '不合格'}")
    return "\n".join(out), passed


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="仕様駆動ワークフローの機械点検")
    ap.add_argument("mode", nargs="?", default="all", choices=["all", "spec", "area"])
    ap.add_argument("target", nargs="?")
    ap.add_argument("--root", default=".")
    ap.add_argument("--with-tests", action="store_true", help="spec モードで AC とテストの対応も点検する")
    ap.add_argument("--tests", nargs="*", default=[], help="テストを探す glob（CLAUDE.md の設定より優先）")
    ap.add_argument("--today", help="今日の日付（YYYY-MM-DD。試験用）")
    a = ap.parse_args(argv)

    if a.mode in ("spec", "area") and not a.target:
        print(f"{a.mode} には対象（spec 番号 / 領域コード）が要る", file=sys.stderr)
        return 2
    target = a.target
    if a.mode == "spec":
        target = target.zfill(3)
    root = Path(a.root).resolve()
    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    try:
        findings, info, notes, specs, readme = run_checks(root, a.mode, target, a.with_tests, a.tests, today)
    except SystemExit as e:
        print(str(e), file=sys.stderr)
        return 2
    if a.mode == "spec" and target not in specs:
        print(f"spec {target} が docs/specs/ に見つからない", file=sys.stderr)
        return 2
    text, passed = render(root, a.mode, target, select(findings, a.mode, target), info, notes)
    print(text)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
