#!/usr/bin/env python3
"""Quality report and readable answer key for a question bank (course JSON).

Usage:
  bank_report.py bank.json [--sources sources/sources.json] [-o review.md]

Runs the site builder's validation, then checks coverage (items per module and type,
difficulty mix, source pages no item cites), near-duplicate prompts, giveaway options,
true/false balance and negatively worded prompts. Writes a Markdown review with the
findings followed by every item and its answer, for a human to check.
Exit 0 = no validation errors, 1 = validation errors.
"""
import argparse
import difflib
import json
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "interactive-learning-studio", "scripts")))
try:
    from build_site import validate  # shared validator from the site-builder skill
except Exception:  # pragma: no cover
    validate = None

TYPE_ORDER = ["mcq", "multi", "truefalse", "flashcard", "recall", "matching"]
TYPE_LABEL = {"mcq": "Multiple choice", "multi": "Select all", "truefalse": "True/false",
              "flashcard": "Flashcard", "recall": "Recall", "matching": "Matching", "term": "Key terms"}
NEGATIVE = re.compile(r"\b(not|except|never|least|false)\b|\bδεν\b|\bεκτός\b|\bμη\b", re.I)


def prompt_of(it):
    return (it.get("prompt") or it.get("front") or "").strip()


def pages_from_loc(loc):
    """'p. 12', 'pp. 12-14', 'slide 3', 'pages 4, 7' -> set of ints. Article refs return nothing."""
    if not loc:
        return set()
    s = str(loc).lower()
    if not re.search(r"\b(p|pp|page|pages|slide|slides|σελ|σ)\b\.?", s) and not re.fullmatch(r"[\d\s,\-–]+", s):
        return set()
    out = set()
    for a, b in re.findall(r"(\d+)\s*(?:[-–]\s*(\d+))?", s):
        a = int(a)
        b = int(b) if b else a
        if b >= a and b - a < 200:
            out.update(range(a, b + 1))
    return out


def ranges(nums):
    nums = sorted(nums)
    out, i = [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out.append(str(nums[i]) if i == j else f"{nums[i]}–{nums[j]}")
        i = j + 1
    return ", ".join(out)


def md(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bank")
    ap.add_argument("--sources", help="sources.json written by extract_sources.py")
    ap.add_argument("-o", "--out", default="review.md")
    a = ap.parse_args()

    with open(a.bank, encoding="utf-8") as f:
        data = json.load(f)
    mods = data.get("modules", [])
    items = [it for it in data.get("items", []) if isinstance(it, dict)]
    srcs = {s["id"]: s for s in data.get("sources", []) if isinstance(s, dict) and "id" in s}
    title = data.get("course", {}).get("title", "Question bank")
    L, findings = [], []

    errors, warnings = [], []
    if validate:
        rep = validate(data, for_site=False)
        errors = rep.errors
        warnings = [w for w in rep.warnings if not w.endswith("no source reference")]  # summarised below
    else:
        findings.append("Validation skipped: the site-builder skill's build_site.py was not found next to this skill.")

    # coverage table
    counts = defaultdict(Counter)
    for it in items:
        counts[it.get("module")][it.get("type")] += 1
    for m in mods:
        counts[m["id"]]["term"] = len(m.get("keyTerms") or [])
    for m in mods:
        c = counts[m["id"]]
        practice = sum(v for k, v in c.items() if k != "term")
        if practice + c["term"] < 8:
            findings.append(f"Module **{m.get('title')}** has only {practice} items and {c['term']} key terms (aim for 8+ in total).")
        if not c["recall"]:
            findings.append(f"Module **{m.get('title')}** has no recall prompt.")
        if c["mcq"] + c["multi"] + c["truefalse"] < 4:
            findings.append(f"Module **{m.get('title')}** has fewer than 4 quiz questions.")

    diff = Counter(it.get("difficulty", 2) for it in items)
    tot = max(1, len(items))
    if items and diff[3] / tot < 0.1:
        findings.append(f"Few hard items: {diff[3]} of {len(items)} are level 3 (aim for about 20%).")
    if items and diff[1] / tot > 0.55:
        findings.append(f"Mostly fact recall: {diff[1]} of {len(items)} are level 1 (aim for about 35%).")

    nosrc = [it["id"] for it in items if not it.get("source")]
    real_sources = set(srcs) - {"gk"}
    if nosrc and real_sources:
        findings.append(f"{len(nosrc)} {'item has' if len(nosrc) == 1 else 'items have'} no source reference: {', '.join(nosrc[:15])}{' …' if len(nosrc) > 15 else ''}")

    # page coverage
    gap_lines = []
    if a.sources:
        with open(a.sources, encoding="utf-8") as f:
            manifest = {m["id"]: m for m in json.load(f)}
        cited = defaultdict(set)
        for it in items:
            s = it.get("source") or {}
            cited[s.get("ref")] |= pages_from_loc(s.get("loc"))
        for m in mods:
            for k in m.get("keyTerms") or []:
                s = k.get("source") or {}
                cited[s.get("ref")] |= pages_from_loc(s.get("loc"))
        for sid, man in manifest.items():
            if man.get("unit") not in ("page", "slide"):
                continue
            allp = set(range(1, man["units"] + 1)) - set(man.get("emptyUnits", []))
            missing = sorted(allp - cited.get(sid, set()))
            share = 1 - len(missing) / max(1, len(allp))
            gap_lines.append(f"| {sid} | {md(man.get('title', ''))} | {man['units']} {man['unit']}s | {share:.0%} | {ranges(missing) or '—'} |")
            if man.get("emptyUnits"):
                findings.append(f"{sid}: {man['unit']} {ranges(man['emptyUnits'])} had no readable text (scanned?) and is not covered.")
            if share < 0.6:
                findings.append(f"{sid} ({man.get('title')}): only {share:.0%} of {man['unit']}s are cited by any item. Check the gaps.")

    # near-duplicates
    ps = [(it["id"], prompt_of(it).lower()) for it in items if prompt_of(it)]
    dups = []
    for i in range(len(ps)):
        for j in range(i + 1, len(ps)):
            if abs(len(ps[i][1]) - len(ps[j][1])) > 0.4 * max(len(ps[i][1]), len(ps[j][1])):
                continue
            r = difflib.SequenceMatcher(None, ps[i][1], ps[j][1]).ratio()
            if r >= 0.85:
                dups.append(f"{ps[i][0]} and {ps[j][0]} ({r:.0%} similar)")
    if dups:
        findings.append("Near-duplicate prompts: " + "; ".join(dups[:12]))

    # giveaways and wording
    longest = []
    for it in items:
        if it.get("type") == "mcq" and isinstance(it.get("answer"), int) and len(it.get("options", [])) >= 3:
            lens = [len(str(o)) for o in it["options"]]
            if 0 <= it["answer"] < len(lens) and lens[it["answer"]] == max(lens) and lens.count(max(lens)) == 1:
                longest.append(it["id"])
    mcqs = sum(1 for it in items if it.get("type") == "mcq")
    if mcqs >= 6 and len(longest) / mcqs > 0.4:
        findings.append(f"The correct option is the longest in {len(longest)} of {mcqs} multiple-choice items — learners can guess by length. Items: {', '.join(longest[:12])}")
    tf = [it.get("answer") for it in items if it.get("type") == "truefalse"]
    if len(tf) >= 4 and abs(tf.count(True) - tf.count(False)) > max(2, len(tf) * 0.3):
        findings.append(f"True/false answers are unbalanced: {tf.count(True)} true, {tf.count(False)} false.")
    neg = [it["id"] for it in items if it.get("type") in ("mcq", "multi") and NEGATIVE.search(prompt_of(it)) and "**" not in prompt_of(it)]
    if neg:
        findings.append(f"Negatively worded prompts without bold emphasis (check wording, bold the negative): {', '.join(neg[:12])}")
    noexp = [it["id"] for it in items if it.get("type") in ("mcq", "multi", "truefalse") and not it.get("explanation")]
    if noexp:
        findings.append(f"{len(noexp)} choice {'item has' if len(noexp) == 1 else 'items have'} no explanation: {', '.join(noexp[:12])}{' …' if len(noexp) > 12 else ''}")

    # ---------- write ----------
    L.append(f"# Question bank review: {title}\n")
    terms = sum(len(m.get("keyTerms") or []) for m in mods)
    L.append(f"{len(mods)} modules, {len(items)} practice items, {terms} key terms. "
             f"Difficulty: {diff[1]} easy, {diff[2]} medium, {diff[3]} hard.\n")
    L.append("## Needs attention\n")
    if errors:
        L.append("**Validation errors (must fix before building a site):**\n")
        L += [f"- {e}" for e in errors]
        L.append("")
    issues = findings + warnings
    L += [f"- {x}" for x in issues] if issues else ["- Nothing flagged."]
    L.append("")
    L.append("## Coverage by module\n")
    cols = ["term"] + TYPE_ORDER
    L.append("| Module | " + " | ".join(TYPE_LABEL[c] for c in cols) + " | Total |")
    L.append("|---" * (len(cols) + 2) + "|")
    for m in mods:
        c = counts[m["id"]]
        L.append(f"| {md(m.get('title', m['id']))} | " + " | ".join(str(c[k]) for k in cols) + f" | {sum(c.values())} |")
    L.append("")
    if gap_lines:
        L.append("## Source coverage\n")
        L.append("| Source | Title | Length | Cited | Not cited by any item |")
        L.append("|---|---|---|---|---|")
        L += gap_lines
        L.append("")

    L.append("## Answer key\n")
    for m in mods:
        L.append(f"### {m.get('title', m['id'])}\n")
        if m.get("keyTerms"):
            L.append("**Key terms**\n")
            for k in m["keyTerms"]:
                L.append(f"- **{k.get('term')}**: {k.get('definition')}{cite(k.get('source'), srcs)}")
            L.append("")
        for it in [x for x in items if x.get("module") == m["id"]]:
            L.append(f"**{it['id']}** · {TYPE_LABEL.get(it.get('type'), it.get('type'))} · level {it.get('difficulty', 2)}{cite(it.get('source'), srcs)}  ")
            t = it.get("type")
            if t in ("mcq", "multi"):
                L.append(f"{it.get('prompt')}\n")
                ans = it.get("answer")
                ans = ans if isinstance(ans, list) else [ans]
                for i, o in enumerate(it.get("options", [])):
                    L.append(f"- {'✅' if i in ans else '▫️'} {o}")
            elif t == "truefalse":
                L.append(f"{it.get('prompt')}  \nAnswer: **{'True' if it.get('answer') else 'False'}**")
            elif t == "flashcard":
                L.append(f"Front: {it.get('front')}  \nBack: {it.get('back')}")
            elif t == "recall":
                L.append(f"{it.get('prompt')}  \nModel answer: {it.get('answer')}  \nKey points:")
                L += [f"  - {k}" for k in it.get("keyPoints", [])]
            elif t == "matching":
                L.append(f"{it.get('prompt', 'Match the pairs.')}\n")
                L += [f"- {p.get('left')} → {p.get('right')}" for p in it.get("pairs", [])]
            if it.get("explanation"):
                L.append(f"\n*Why:* {it['explanation']}")
            L.append("")
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")

    print(f"{len(errors)} validation errors, {len(issues)} findings; wrote {a.out}")
    for e in errors:
        print("ERROR  ", e)
    for x in issues:
        print("-", re.sub(r"\*\*", "", x))
    return 1 if errors else 0


def cite(src, srcs):
    if not src or not src.get("ref"):
        return ""
    s = srcs.get(src["ref"], {})
    name = s.get("title", src["ref"])
    return f" · *{name}{', ' + src['loc'] if src.get('loc') else ''}*"


if __name__ == "__main__":
    sys.exit(main())
