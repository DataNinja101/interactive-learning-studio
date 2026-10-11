#!/usr/bin/env python3
"""Validate course data and build a single-file, offline learning site.

Usage:
  build_site.py course.json -o site.html        validate, then build
  build_site.py course.json --check             validate only
  build_site.py --extract site.html -o course.json
                                                recover the course data from a built site

Exit code 0 = ok (warnings allowed), 1 = validation errors, 2 = usage/IO error.
Standard library only.
"""
import argparse
import html
import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TEMPLATE = os.path.normpath(os.path.join(HERE, "..", "assets", "template.html"))
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ITEM_TYPES = {"mcq", "multi", "truefalse", "flashcard", "recall", "matching"}
BLOCK_TYPES = {"heading", "paragraph", "list", "callout", "table", "quote", "code", "divider"}
TONES = {"info", "tip", "warning", "example"}
HTML_TAG = re.compile(r"<\s*/?\s*[a-zA-Z][a-zA-Z0-9]*(\s[^<>]*)?>")
WEAK_OPTIONS = re.compile(
    r"^(all|none|both|neither) of (the )?(above|these|them)\b|^(όλα|κανένα) (τα )?(παραπάνω|από τα παραπάνω)",
    re.I,
)


class Report:
    def __init__(self):
        self.errors, self.warnings = [], []

    def err(self, where, msg):
        self.errors.append(f"{where}: {msg}")

    def warn(self, where, msg):
        self.warnings.append(f"{where}: {msg}")


def nonempty_str(v):
    return isinstance(v, str) and v.strip() != ""


def check_text(rep, where, value, field="text"):
    if not nonempty_str(value):
        rep.err(where, f"'{field}' must be a non-empty string")
        return
    if HTML_TAG.search(value):
        rep.warn(where, f"'{field}' contains HTML-like tags; they will show as plain text")


def check_source(rep, where, src, source_ids):
    if src is None:
        return
    if not isinstance(src, dict) or not nonempty_str(src.get("ref")):
        rep.err(where, "'source' must be an object with a 'ref'")
    elif src["ref"] not in source_ids:
        rep.err(where, f"source ref '{src['ref']}' is not in 'sources'")


def check_block(rep, where, b):
    if not isinstance(b, dict) or b.get("type") not in BLOCK_TYPES:
        rep.err(where, f"unknown lesson block type {b.get('type') if isinstance(b, dict) else b!r}")
        return
    t = b["type"]
    if t in ("heading", "paragraph", "quote", "code"):
        check_text(rep, where, b.get("text"))
    elif t == "callout":
        check_text(rep, where, b.get("text"))
        if b.get("tone", "info") not in TONES:
            rep.err(where, f"callout tone must be one of {sorted(TONES)}")
    elif t == "list":
        items = b.get("items")
        if not isinstance(items, list) or not items:
            rep.err(where, "list needs a non-empty 'items' array")
        else:
            for i, x in enumerate(items):
                check_text(rep, f"{where} item {i + 1}", x, "item")
    elif t == "table":
        hdr, rows = b.get("headers"), b.get("rows")
        if not isinstance(hdr, list) or not hdr:
            rep.err(where, "table needs 'headers'")
        if not isinstance(rows, list) or not rows:
            rep.err(where, "table needs 'rows'")
        elif isinstance(hdr, list):
            for i, r in enumerate(rows):
                if not isinstance(r, list) or len(r) != len(hdr):
                    rep.err(where, f"table row {i + 1} must have {len(hdr)} cells")


def check_item(rep, it, module_ids, source_ids, strict_sources):
    iid = it.get("id", "?")
    where = f"item {iid}"
    t = it.get("type")
    if t not in ITEM_TYPES:
        rep.err(where, f"type must be one of {sorted(ITEM_TYPES)}")
        return
    if it.get("module") not in module_ids:
        rep.err(where, f"module '{it.get('module')}' does not exist")
    d = it.get("difficulty", 2)
    if d not in (1, 2, 3):
        rep.err(where, "difficulty must be 1, 2 or 3")
    check_source(rep, where, it.get("source"), source_ids)
    if strict_sources and it.get("source") is None:
        rep.warn(where, "no source reference")
    if "explanation" in it and it["explanation"] is not None:
        check_text(rep, where, it["explanation"], "explanation")

    if t in ("mcq", "multi"):
        check_text(rep, where, it.get("prompt"), "prompt")
        opts = it.get("options")
        lo = 2 if t == "mcq" else 3
        if not isinstance(opts, list) or not (lo <= len(opts) <= 6):
            rep.err(where, f"'options' must be a list of {lo}–6 strings")
            return
        for i, o in enumerate(opts):
            check_text(rep, f"{where} option {i + 1}", o, "option")
        norm = [str(o).strip().lower() for o in opts]
        if len(set(norm)) != len(norm):
            rep.err(where, "duplicate options")
        if it.get("shuffle", True) and any(WEAK_OPTIONS.search(str(o).strip()) for o in opts):
            rep.warn(where, "'all/none of the above' style option is shuffled; rewrite it or set \"shuffle\": false")
        ans = it.get("answer")
        if t == "mcq":
            if not isinstance(ans, int) or isinstance(ans, bool) or not (0 <= ans < len(opts)):
                rep.err(where, f"'answer' must be an option index 0–{len(opts) - 1}")
            else:
                lens = [len(str(o)) for o in opts]
                if len(opts) >= 3 and lens[ans] == max(lens) and lens[ans] > 1.6 * (sum(lens) - lens[ans]) / (len(lens) - 1):
                    rep.warn(where, "correct option is much longer than the others (a giveaway)")
        else:
            if (not isinstance(ans, list) or not ans
                    or any(not isinstance(a, int) or isinstance(a, bool) or not (0 <= a < len(opts)) for a in ans)):
                rep.err(where, "'answer' must be a non-empty list of option indexes")
            elif len(set(ans)) != len(ans):
                rep.err(where, "'answer' repeats an index")
            elif len(set(ans)) == len(opts):
                rep.err(where, "every option is correct; drop one or use a different type")
    elif t == "truefalse":
        check_text(rep, where, it.get("prompt"), "prompt")
        if not isinstance(it.get("answer"), bool):
            rep.err(where, "'answer' must be true or false")
    elif t == "flashcard":
        check_text(rep, where, it.get("front"), "front")
        check_text(rep, where, it.get("back"), "back")
    elif t == "recall":
        check_text(rep, where, it.get("prompt"), "prompt")
        check_text(rep, where, it.get("answer"), "answer")
        kp = it.get("keyPoints")
        if not isinstance(kp, list) or not kp:
            rep.err(where, "'keyPoints' must be a non-empty list")
        else:
            if len(kp) > 6:
                rep.warn(where, "more than 6 key points; learners rarely tick that many honestly")
            for i, k in enumerate(kp):
                check_text(rep, f"{where} key point {i + 1}", k, "keyPoint")
    elif t == "matching":
        if it.get("prompt") is not None:
            check_text(rep, where, it.get("prompt"), "prompt")
        pairs = it.get("pairs")
        if not isinstance(pairs, list) or not (3 <= len(pairs) <= 8):
            rep.err(where, "'pairs' must have 3–8 entries")
            return
        lefts, rights = [], []
        for i, p in enumerate(pairs):
            if not isinstance(p, dict):
                rep.err(where, f"pair {i + 1} must be an object")
                continue
            check_text(rep, f"{where} pair {i + 1}", p.get("left"), "left")
            check_text(rep, f"{where} pair {i + 1}", p.get("right"), "right")
            lefts.append(str(p.get("left", "")).strip().lower())
            rights.append(str(p.get("right", "")).strip().lower())
        if len(set(lefts)) != len(lefts):
            rep.err(where, "duplicate 'left' values")
        if len(set(rights)) != len(rights):
            rep.err(where, "duplicate 'right' values")


def validate(data, for_site=True):
    rep = Report()
    if not isinstance(data, dict):
        rep.err("file", "top level must be a JSON object")
        return rep
    if data.get("schemaVersion") != 1:
        rep.warn("file", "schemaVersion should be 1")
    c = data.get("course")
    if not isinstance(c, dict):
        rep.err("course", "missing 'course' object")
        c = {}
    if not nonempty_str(c.get("id")) or not SLUG.match(c.get("id", "")):
        rep.err("course", "'id' must be a kebab-case slug, e.g. intro-to-mortgages")
    if not nonempty_str(c.get("title")):
        rep.err("course", "'title' is required")
    if "ui" in c and not isinstance(c["ui"], dict):
        rep.err("course", "'ui' must be an object of label overrides")

    sources = data.get("sources", [])
    source_ids = set()
    if not isinstance(sources, list):
        rep.err("sources", "must be a list")
        sources = []
    for i, s in enumerate(sources):
        if not isinstance(s, dict) or not nonempty_str(s.get("id")):
            rep.err(f"source {i + 1}", "needs an 'id'")
            continue
        if s["id"] in source_ids:
            rep.err(f"source {s['id']}", "duplicate id")
        source_ids.add(s["id"])
        if not nonempty_str(s.get("title")):
            rep.err(f"source {s['id']}", "needs a 'title'")
        if s.get("url") and not re.match(r"^https?://", str(s["url"])):
            rep.err(f"source {s['id']}", "url must start with http:// or https://")
    strict_sources = bool(source_ids - {"gk"})

    mods = data.get("modules")
    module_ids = set()
    if not isinstance(mods, list) or not mods:
        rep.err("modules", "need at least one module")
        mods = []
    for i, m in enumerate(mods):
        if not isinstance(m, dict) or not nonempty_str(m.get("id")):
            rep.err(f"module {i + 1}", "needs an 'id'")
            continue
        mid = m["id"]
        where = f"module {mid}"
        if mid in module_ids:
            rep.err(where, "duplicate id")
        module_ids.add(mid)
        if not nonempty_str(m.get("title")):
            rep.err(where, "needs a 'title'")
        lesson = m.get("lesson", [])
        if not isinstance(lesson, list):
            rep.err(where, "'lesson' must be a list of blocks")
            lesson = []
        if for_site and not lesson:
            rep.warn(where, "no lesson content; the Lesson tab will only show key terms")
        for j, b in enumerate(lesson):
            check_block(rep, f"{where} lesson block {j + 1}", b)
        obj = m.get("objectives", [])
        if not isinstance(obj, list):
            rep.err(where, "'objectives' must be a list")
        seen_terms = set()
        for j, k in enumerate(m.get("keyTerms", []) or []):
            w = f"{where} key term {j + 1}"
            if not isinstance(k, dict):
                rep.err(w, "must be an object")
                continue
            check_text(rep, w, k.get("term"), "term")
            check_text(rep, w, k.get("definition"), "definition")
            check_source(rep, w, k.get("source"), source_ids)
            key = str(k.get("term", "")).strip().lower()
            if key in seen_terms:
                rep.err(w, f"duplicate term '{k.get('term')}'")
            seen_terms.add(key)

    items = data.get("items", [])
    if not isinstance(items, list):
        rep.err("items", "must be a list")
        items = []
    ids = Counter()
    for it in items:
        if not isinstance(it, dict) or not nonempty_str(it.get("id")):
            rep.err("items", f"item without an 'id': {str(it)[:60]}")
            continue
        ids[it["id"]] += 1
        if it["id"].startswith("kt:"):
            rep.err(f"item {it['id']}", "ids starting with 'kt:' are reserved for key terms")
        check_item(rep, it, module_ids, source_ids, strict_sources)
    for k, n in ids.items():
        if n > 1:
            rep.err(f"item {k}", f"id used {n} times")

    # cross-checks
    prompts = Counter()
    for it in items:
        if isinstance(it, dict):
            p = (it.get("prompt") or it.get("front") or "").strip().lower()
            if p:
                prompts[p] += 1
    for p, n in prompts.items():
        if n > 1:
            rep.warn("items", f"same prompt used {n} times: '{p[:70]}'")
    terms_by_mod = {m.get("id"): {str(k.get("term", "")).strip().lower() for k in (m.get("keyTerms") or []) if isinstance(k, dict)}
                    for m in mods if isinstance(m, dict)}
    for it in items:
        if isinstance(it, dict) and it.get("type") == "flashcard":
            if str(it.get("front", "")).strip().lower() in terms_by_mod.get(it.get("module"), set()):
                rep.warn(f"item {it.get('id')}", "duplicates a key term (key terms already become flashcards)")
    per_mod = Counter(it.get("module") for it in items if isinstance(it, dict))
    for m in mods:
        if isinstance(m, dict) and m.get("id") in module_ids and per_mod[m["id"]] == 0 and not m.get("keyTerms"):
            rep.warn(f"module {m['id']}", "has no practice items or key terms")
    tf = [it.get("answer") for it in items if isinstance(it, dict) and it.get("type") == "truefalse"]
    if len(tf) >= 6 and (tf.count(True) / len(tf) > 0.75 or tf.count(False) / len(tf) > 0.75):
        rep.warn("items", f"true/false answers are lopsided ({tf.count(True)} true, {tf.count(False)} false)")
    return rep


def stats(data):
    items = data.get("items", [])
    by_type = Counter(it.get("type") for it in items)
    terms = sum(len(m.get("keyTerms") or []) for m in data.get("modules", []))
    parts = [f"{len(data.get('modules', []))} modules", f"{len(items)} items"]
    parts += [f"{n} {t}" for t, n in sorted(by_type.items())]
    parts.append(f"{terms} key terms")
    return ", ".join(parts)


def print_report(rep):
    for e in rep.errors:
        print(f"ERROR   {e}")
    for w in rep.warnings:
        print(f"warning {w}")
    print(f"{len(rep.errors)} errors, {len(rep.warnings)} warnings")


def embed(data, template_path):
    with open(template_path, encoding="utf-8") as f:
        tpl = f.read()
    if tpl.count("__COURSE_DATA__") != 1 or "__COURSE_TITLE__" not in tpl:
        raise SystemExit("template is missing its placeholders")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    out = tpl.replace("__COURSE_TITLE__", html.escape(data["course"]["title"]), 1)
    return out.replace("__COURSE_DATA__", payload, 1)


def extract(site_path):
    with open(site_path, encoding="utf-8") as f:
        s = f.read()
    m = re.search(r'<script type="application/json" id="course-data">(.*?)</script>', s, re.S)
    if not m:
        raise SystemExit("no course data found in that file")
    return json.loads(m.group(1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("course", nargs="?", help="course JSON file")
    ap.add_argument("-o", "--output", help="output path")
    ap.add_argument("--template", default=DEFAULT_TEMPLATE)
    ap.add_argument("--check", action="store_true", help="validate only")
    ap.add_argument("--bank", action="store_true", help="validate as a question bank (lessons may be empty)")
    ap.add_argument("--extract", metavar="SITE_HTML", help="recover course JSON from a built site")
    a = ap.parse_args()

    if a.extract:
        data = extract(a.extract)
        out = a.output or os.path.splitext(a.extract)[0] + ".course.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"wrote {out} ({stats(data)})")
        return 0
    if not a.course:
        ap.print_usage()
        return 2
    try:
        with open(a.course, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR   cannot read {a.course}: {e}")
        return 2

    rep = validate(data, for_site=not a.bank)
    print_report(rep)
    if rep.errors:
        return 1
    print(stats(data))
    if a.check or a.bank:
        return 0
    out = a.output or (data["course"]["id"] + ".html")
    page = embed(data, a.template)
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"wrote {out} ({len(page.encode('utf-8')) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
