#!/usr/bin/env python3
"""Open a built learning site in headless Chromium and exercise every module and tab.

Usage:
  smoke_test.py site.html [--shots DIR]

Checks: no JavaScript errors, no network requests, every module's lesson renders, the
first item of each practice tab can be answered, Ask Claude works both as a link out
(downloaded file) and inline (with a stand-in for the claude.ai runtime), and nothing
scrolls sideways on a 380px phone screen.
With --shots, saves screenshots to look at before delivering.
Exit 0 = passed, 1 = failed, 3 = Playwright/Chromium not available (skip, not a failure).
"""
import argparse
import json
import os
import sys
from urllib.parse import parse_qs, urlparse

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("SKIP: playwright is not installed (pip install playwright && playwright install chromium)")
    sys.exit(3)

TABS = [("quiz", ("mcq", "multi", "truefalse")), ("cards", ("flashcard",)), ("recall", ("recall",)), ("match", ("matching",))]
CHOICE = ("mcq", "multi", "truefalse")
LOCAL = ("file:", "data:", "blob:", "about:")

# Stand-in for the claude.ai Artifact runtime: the first call answers, later calls are refused
# as if the viewer said no, so both the inline answer and the fallback to a link can be checked.
FAKE_CLAUDE = """
window.__askLog = [];
window.claude = { use: function (name) {
  if (name !== "sample") return Promise.resolve(null);
  var n = 0;
  var sample = function (input, opts) {
    window.__askLog.push(input); n++;
    return new Promise(function (resolve, reject) {
      setTimeout(function () {
        if (n > 1) return reject({ code: "not_granted", message: "test" });
        var text = "**Because** the lesson says so.\\n\\n- first reason\\n- second reason";
        if (opts && opts.onText) opts.onText({ text: text, delta: text });
        resolve({ text: text, truncated: false, modelTierApplied: "default" });
      }, 60);
    });
  };
  return Promise.resolve(sample);
} };
"""


def answer_first_quiz_item(page, url, mid):
    page.goto(f"{url}#/m/{mid}/quiz")
    page.wait_for_selector(".opt", timeout=4000)
    page.click(".opt >> nth=0")
    page.click(".actions .btn")
    page.wait_for_selector(".feedback .verdict", timeout=3000)


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
        page.on("request", lambda r: None if r.url.startswith(LOCAL) else problems.append(f"network request to {r.url}"))
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

        ask_on = data["course"].get("askClaude", True) is not False
        first = data["modules"][0]
        first_q = next((it for it in items if it.get("module") == first["id"] and it.get("type") in CHOICE), None)
        page.goto(f"{url}#/m/{first['id']}")
        page.wait_for_selector(".lesson", state="attached", timeout=5000)
        has_btn = page.query_selector(".lesson-foot .ask-open") is not None
        if not ask_on:
            if has_btn:
                problems.append("course.askClaude is false but the lesson shows Ask Claude")
            else:
                notes.append("Ask Claude is turned off for this course")
        elif not has_btn:
            problems.append("lesson has no Ask Claude button")
        elif first_q:
            try:
                # Downloaded file: no claude.ai runtime, so the panel links out.
                answer_first_quiz_item(page, url, first["id"])
                page.click(".actions .ask-open")
                page.wait_for_selector(".ask:not([hidden]) a.ask-go", state="visible", timeout=3000)
                page.fill(".ask textarea", "Why is that?")
                href = page.get_attribute(".ask a.ask-go", "href") or ""
                q = parse_qs(urlparse(href).query).get("q", [""])[0]
                if not href.startswith("https://claude.ai/new?q="):
                    problems.append(f"Ask Claude link is '{href[:60]}', expected https://claude.ai/new?q=...")
                elif "Why is that?" not in q or first_q["prompt"] not in q:
                    problems.append("Ask Claude link does not carry the question and the quiz item")
                elif len(href) > 8000:
                    problems.append(f"Ask Claude link is {len(href)} characters long")
                shot(page, "ask-link-out")

                # Inside claude.ai: answers come back in the page.
                ictx = browser.new_context(viewport={"width": 1200, "height": 900})
                ictx.add_init_script(FAKE_CLAUDE)
                ip = ictx.new_page()
                ip.on("pageerror", lambda e: problems.append(f"JavaScript error (Ask Claude): {e}"))
                ip.on("request", lambda r: None if r.url.startswith(LOCAL) else problems.append(f"network request to {r.url}"))
                answer_first_quiz_item(ip, url, first["id"])
                ip.click(".actions .ask-open")
                ip.wait_for_selector(".ask .chip", state="visible", timeout=3000)
                ip.wait_for_selector(".ask .ask-row:not([hidden]) .btn", timeout=3000)
                ip.click(".ask .chip >> nth=0")
                ip.wait_for_selector(".ask-a:not(.is-wait) li", timeout=5000)
                sent = ip.evaluate("window.__askLog[0]")
                if not (isinstance(sent, list) and sent and sent[0]["role"] == "user" and sent[-1]["role"] == "user"):
                    problems.append("Ask Claude sent a malformed conversation")
                elif first_q["prompt"] not in sent[0]["content"]:
                    problems.append("Ask Claude did not send the quiz item to Claude")
                shot(ip, "ask-inline")
                ip.fill(".ask textarea", "And another thing?")
                ip.press(".ask textarea", "Enter")
                ip.wait_for_selector(".ask:not([hidden]) a.ask-go", state="visible", timeout=5000)
                if not ip.inner_text(".ask .ask-msg").strip():
                    problems.append("Ask Claude did not explain why it switched to a link")
                if len(ip.query_selector_all(".ask-q")) != 1:
                    problems.append("a refused Ask Claude question was left in the conversation")
                ictx.close()
                notes.append("Ask Claude checked inline and as a link")
            except Exception as e:
                problems.append(f"Ask Claude: {str(e).splitlines()[0]}")

        mob = browser.new_context(viewport={"width": 380, "height": 800}).new_page()
        mob.on("pageerror", lambda e: problems.append(f"JavaScript error (mobile): {e}"))
        for frag in ["", f"#/m/{data['modules'][0]['id']}"]:
            mob.goto(url + frag)
            mob.wait_for_selector("h1", timeout=5000)
            if frag and mob.query_selector(".lesson-foot .ask-open"):
                mob.click(".lesson-foot .ask-open")
                mob.wait_for_selector(".ask:not([hidden])", timeout=3000)
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
