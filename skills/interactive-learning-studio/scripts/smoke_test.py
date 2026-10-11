#!/usr/bin/env python3
"""Open a built learning site in headless Chromium and exercise every module and tab.

Usage:
  smoke_test.py site.html [--shots DIR]

Checks: no JavaScript errors, every module's lesson renders, the first item of each
practice tab can be answered, and nothing scrolls sideways on a 380px phone screen.
With --shots, saves screenshots to look at before delivering.
Exit 0 = passed, 1 = failed, 3 = Playwright/Chromium not available (skip, not a failure).
"""
import argparse
import json
import os
import sys

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("SKIP: playwright is not installed (pip install playwright && playwright install chromium)")
    sys.exit(3)

TABS = [("quiz", ("mcq", "multi", "truefalse")), ("cards", ("flashcard",)), ("recall", ("recall",)), ("match", ("matching",))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("site")
    ap.add_argument("--shots")
    a = ap.parse_args()
    url = "file://" + os.path.abspath(a.site)
    problems, notes = [], []
    if a.shots:
        os.makedirs(a.shots, exist_ok=True)

    def shot(page, name):
        if a.shots:
            page.screenshot(path=os.path.join(a.shots, name + ".png"), full_page=True)

    try:
        pw = sync_playwright().start()
        browser = pw.chromium.launch()
    except Exception as e:  # browser binaries missing
        print(f"SKIP: could not start Chromium ({str(e).splitlines()[0]})")
        sys.exit(3)

    try:
        ctx = browser.new_context(viewport={"width": 1200, "height": 900})
        page = ctx.new_page()
        page.on("pageerror", lambda e: problems.append(f"JavaScript error: {e}"))
        page.on("console", lambda m: problems.append(f"console {m.type}: {m.text}") if m.type == "error" else None)
        page.goto(url)
        try:
            page.wait_for_selector("h1", timeout=8000)
        except Exception:
            print("FAIL the site did not render a dashboard", *problems, sep="\n")
            sys.exit(1)
        data = json.loads(page.eval_on_selector("#course-data", "e => e.textContent"))
        title = page.inner_text("h1")
        if title.strip() != data["course"]["title"].strip():
            problems.append(f"dashboard title is '{title}', expected '{data['course']['title']}'")
        shot(page, "dashboard")

        items = data.get("items", [])
        for m in data["modules"]:
            mid = m["id"]
            page.goto(f"{url}#/m/{mid}")
            try:
                page.wait_for_selector(".lesson", state="attached", timeout=5000)
                if page.eval_on_selector(".lesson", "e => e.children.length") == 0:
                    problems.append(f"module {mid}: lesson is empty")
            except Exception as e:
                problems.append(f"module {mid}: lesson did not render ({str(e).splitlines()[0]})")
                continue
            if mid == data["modules"][0]["id"]:
                shot(page, "lesson-first-module")
            has_terms = bool(m.get("keyTerms"))
            for tab, types in TABS:
                n = sum(1 for it in items if it.get("module") == mid and it.get("type") in types)
                if tab == "cards" and has_terms:
                    n += 1
                if not n:
                    continue
                page.goto(f"{url}#/m/{mid}/{tab}")
                try:
                    if tab == "quiz":
                        page.wait_for_selector(".opt", timeout=4000)
                        page.click(".opt >> nth=0")
                        page.click(".actions .btn")
                        page.wait_for_selector(".feedback .verdict", timeout=3000)
                    elif tab == "cards":
                        page.wait_for_selector(".flip", timeout=4000)
                        page.click(".flip")
                        page.wait_for_selector(".rate:not([hidden])", timeout=3000)
                    elif tab == "recall":
                        page.wait_for_selector("textarea", timeout=4000)
                        page.fill("textarea", "test answer")
                        page.click(".actions .btn")
                        page.wait_for_selector(".model", timeout=3000)
                    elif tab == "match":
                        page.wait_for_selector(".match .mitem", timeout=4000)
                        page.click(".match .col:first-child .mitem >> nth=0")
                        page.click(".match .col:last-child .mitem >> nth=0")
                        if not page.query_selector(".mitem.is-paired"):
                            problems.append(f"module {mid}: matching did not pair items")
                except Exception as e:
                    problems.append(f"module {mid} {tab}: {str(e).splitlines()[0]}")
        notes.append(f"{len(data['modules'])} modules checked")

        mob = browser.new_context(viewport={"width": 380, "height": 800}).new_page()
        mob.on("pageerror", lambda e: problems.append(f"JavaScript error (mobile): {e}"))
        for frag in ["", f"#/m/{data['modules'][0]['id']}"]:
            mob.goto(url + frag)
            mob.wait_for_selector("h1", timeout=5000)
            sw = mob.evaluate("document.documentElement.scrollWidth")
            if sw > 382:
                problems.append(f"page scrolls sideways on a phone ({sw}px wide) at '{frag or 'dashboard'}'")
        shot(mob, "mobile-lesson")
    finally:
        browser.close()
        pw.stop()

    for n in notes:
        print(n)
    if problems:
        for p in problems:
            print("FAIL", p)
        sys.exit(1)
    print("PASS")


if __name__ == "__main__":
    main()
