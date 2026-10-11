---
name: "interactive-learning-studio"
description: "Turn supplied course materials or any learning topic into a downloadable, offline-capable interactive HTML learning website with quizzes, flashcards, active recall, matching practice and progress tracking. Use when the user asks to \"make a learning site\", \"turn my notes / slides / PDF into a course\", \"build an interactive course\", \"make a study website with quizzes and flashcards\", \"create an e-learning module\", \"φτιάξε μάθημα / κουίζ / κάρτες μελέτης\", or wants to update or extend a learning site this plugin built before."
---

# Interactive Learning Studio — site builder

Build one self-contained `.html` file that works offline (opens from disk, no internet,
no installs) and contains, for every module: a lesson, a quiz, flashcards with spaced
repetition, active-recall prompts and matching practice. A dashboard shows what is due
today, weak spots and progress. Progress is saved in the learner's browser and can be
exported/imported as a file. Light and dark themes; English or Greek interface.

The engine is fixed and tested (`assets/template.html`). The work in this skill is the
**content**: write it as course JSON in the shape described in
`references/data-schema.md`, then let `scripts/build_site.py` validate and embed it.
Never hand-write the site's HTML, CSS or JavaScript.

Paths below are relative to this skill's base directory. The companion skill
`question-bank-builder` lives in the sibling folder `../question-bank-builder/`.

## 1. Settle the inputs

Work out which of these applies and start; ask at most one question, and only when
the answer would change what gets built (usually audience level or language).

| Situation | What to do |
|-----------|------------|
| Materials attached (PDF, Word, slides, notes, links) | Content comes only from them. Every item and key term cites its source and page/slide. |
| Large materials: more than ~15 pages, several documents, or the user wants to check the questions first | Run the **question-bank-builder** skill first (load it with the Skill tool), then return here at step 3 with the approved bank. |
| Topic only, no materials | Build from knowledge. For anything that changes over time (laws, rules, prices, statistics, current officeholders, software versions) look it up first and cite the URLs as sources. Otherwise use the single source `{"id":"gk","title":"General knowledge (not from supplied materials)"}`. |
| A question bank JSON from question-bank-builder | Skip to step 3. |
| An existing site built by this plugin, to change or extend | `python3 scripts/build_site.py --extract site.html -o course.json`, edit, rebuild. Keep `course.id` and every existing item `id` unchanged, or learners lose progress on those items. Bump `course.version`. |

Defaults when nothing is said: content in the language of the materials (else the
user's language); audience is an adult self-learner; course size scaled to the
material (see step 3).

## 2. Read before writing

Read the whole source, not a skim. For PDFs, Word and slides use
`../question-bank-builder/scripts/extract_sources.py` to get page-marked text. If pages
come back empty (a scanned document), OCR them or ask for a text version — never write
items for pages that could not be read.

Images and diagrams are not supported in the site. When a source relies on a diagram,
explain it in words or as a table in the lesson.

## 3. Plan the course

Draft the outline into the course JSON skeleton: `course`, `sources`, and `modules`
with `id`, `title`, `summary`, `objectives` (2–4, verb-led) — no lessons or items yet.

- 3–8 modules; each one coherent idea, ordered from foundations to application.
- Size guide: ~15–25 practice items per 10 pages of dense material, at least 8 per module.
- Per module, aim for: 6–10 choice items (`mcq`, `multi`, `truefalse`), 3–8 key terms,
  2–4 extra flashcards for facts that are not terms, 2–3 `recall` prompts, 1 `matching`
  set of 4–6 pairs. Difficulty mix roughly 35% level 1, 45% level 2, 20% level 3.
- Choose `course.id` once (kebab-case) and never change it for this course.

If the user is present and the course is big (6+ modules), share the outline in two or
three lines and continue unless they redirect.

## 4. Write the content, one module at a time

Write each module into the JSON file in its own step (edit the file or merge with a
short Python script) rather than one giant write.

**Lesson** (`lesson` blocks, 300–900 words per module): teach, do not paste the
source. Short paragraphs; lead with the idea, then an example. Use a `table` for
comparisons, `callout` for a definition, tip, warning or worked example, and a `list`
for steps. Bold only the few words a learner must not miss. Put the module's key terms
in `keyTerms` — they appear as a glossary under the lesson and become flashcards
automatically, so do not repeat them as `flashcard` items.

**Practice items**: follow `../question-bank-builder/references/question-writing.md`
(distractors, explanations, true/false balance, recall key points, matching sets,
fidelity to sources). Give every item a stable id such as `m3-q4`.

**Language**: write everything in the course language and set `course.language`.
Greek content: `"language": "el"` switches the interface to Greek; keep accents and
final sigma correct and keep official terms exactly as the source writes them. Any
other language: translate the labels in `references/ui-strings.md` into `course.ui`.

**Accuracy**: with supplied materials, do not add facts the sources do not contain. If
sources contradict each other or are unclear, follow the more authoritative one, note
it in the explanation, and mention it to the user at the end. For legal, regulatory,
medical or financial material, keep wording close to the source and cite the article,
section or page in `source.loc`.

`examples/sample-course.json` is a complete, valid course to copy patterns from.

## 5. Build

```bash
python3 scripts/build_site.py course.json -o <course-id>.html
```

Fix every ERROR. Fix warnings too unless there is a reason (for example, a deliberately
long correct option). Re-run until clean.

## 6. Check before delivering

1. Run the browser check (takes ~10 seconds):
   ```bash
   python3 scripts/smoke_test.py <course-id>.html --shots shots/
   ```
   Exit 3 means no headless browser is available — continue without it. On FAIL, fix
   the course data (not the template) and rebuild. Look at the screenshots.
2. Spot-check content: for each module, re-read two or three items against the source
   page they cite, and confirm each `mcq` answer index points at the intended option.

## 7. Deliver

Send the `.html` file to the user. In one or two sentences say what is in it (modules,
item counts) and that it is a single file: download it, double-click to open, works
without internet, progress stays in that browser and moves between devices with
Export/Import progress. Mention any source problems found in step 4.

Keep the course JSON in the working folder. To change the site later, either edit that
JSON or extract it from the site (step 1) and rebuild to the same file name.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Learners lost progress after an update | `course.id` or item ids changed. Restore the old ids. |
| Text shows `<b>` tags literally | HTML is not allowed; use `**bold**` etc. (see data-schema.md). |
| Italics appear in the middle of a formula | A lone `*` was read as italics; use `×`. |
| "This page has no course data" | The template was opened directly; always build with `build_site.py`. |
| Interface labels in English for a non-English course | Add translated labels in `course.ui` (`references/ui-strings.md`). |
