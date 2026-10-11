# Course data format (schemaVersion 1)

One JSON file describes a whole course. The question-bank-builder skill writes it,
the site builder (`scripts/build_site.py`) validates it and embeds it in the site
template. Keep every course in this exact shape so the two skills stay compatible.

## Top level

```json
{
  "schemaVersion": 1,
  "course":  { ... },
  "sources": [ ... ],
  "modules": [ ... ],
  "items":   [ ... ]
}
```

## course

| Field         | Required | Notes |
|---------------|----------|-------|
| `id`          | yes      | kebab-case slug, e.g. `cyprus-property-law-basics`. Used as the browser storage key for progress — never change it between rebuilds of the same course or learners lose progress. |
| `title`       | yes      | Shown in the header and browser tab. |
| `subtitle`    | no       | One line under the title. |
| `description` | no       | 1–3 sentences on the dashboard. |
| `language`    | no       | BCP-47 code of the content, default `en`. `el` switches the interface to Greek. Any other language keeps English interface labels unless `ui` overrides them. |
| `version`     | no       | Free text, e.g. `"2026-10"`. Bump when content changes. |
| `author`      | no       | Shown in the footer. |
| `ui`          | no       | Map of interface-label overrides (keys listed in `ui-strings.md`). Use for languages other than English/Greek. |

## sources

Every document or reference the content came from. Items and key terms point here.

```json
{ "id": "s1", "title": "Lecture 3 – Mortgages", "file": "lecture3.pdf" }
{ "id": "s2", "title": "Land Registry FAQ", "url": "https://..." }
```

`id` is required and unique; give `file` and/or `url` when known. For a topic built
from general knowledge with no documents, use one source
`{ "id": "gk", "title": "General knowledge (not from supplied materials)" }`.

## modules

```json
{
  "id": "m1",
  "title": "What a mortgage is",
  "summary": "One or two sentences shown on the module card.",
  "objectives": ["Define a mortgage", "Name the parties"],
  "lesson": [ <lesson blocks> ],
  "keyTerms": [
    { "term": "Mortgagor", "definition": "The borrower who grants the mortgage.", "source": { "ref": "s1", "loc": "p. 4" } }
  ]
}
```

- `id`, `title` required; ids unique (`m1`, `m2`, … is fine).
- `lesson` may be empty in a question bank that has not been turned into a site yet;
  the site builder fills it before building.
- Every key term automatically becomes a flashcard (term on the front, definition on the back).
  Do not also add a `flashcard` item with the same front.

### Lesson blocks

Text fields accept a small inline syntax: `**bold**`, `*italic*`, `` `code` ``,
`==highlight==`, `[label](https://link)`. A lone `*` (as in `2*3`) can be read as
italics, so write multiplication as `×`. HTML is not allowed and is shown as plain text.

| Block | Shape |
|-------|-------|
| heading   | `{ "type": "heading", "text": "..." }` |
| paragraph | `{ "type": "paragraph", "text": "..." }` |
| list      | `{ "type": "list", "ordered": false, "items": ["...", "..."] }` |
| callout   | `{ "type": "callout", "tone": "info" \| "tip" \| "warning" \| "example", "title": "optional", "text": "..." }` |
| table     | `{ "type": "table", "headers": ["A", "B"], "rows": [["1", "2"]] }` |
| quote     | `{ "type": "quote", "text": "...", "cite": "optional" }` |
| code      | `{ "type": "code", "text": "preformatted text" }` |
| divider   | `{ "type": "divider" }` |

## items

Practice items. Common fields:

| Field         | Required | Notes |
|---------------|----------|-------|
| `id`          | yes      | Unique across the course, e.g. `m1-q3`. Never reuse an id for a different question — progress is stored per id. |
| `module`      | yes      | A module `id`. |
| `type`        | yes      | `mcq`, `multi`, `truefalse`, `flashcard`, `recall`, `matching`. |
| `difficulty`  | no       | 1 = recall a fact, 2 = understand/apply (default), 3 = analyse/combine. |
| `source`      | no*      | `{ "ref": "<source id>", "loc": "p. 12" }`. *Required when the course was built from supplied materials. |
| `explanation` | no       | Shown after answering. Say why the right answer is right and, for choice items, why the tempting wrong one is wrong. |
| `tags`        | no       | Array of short strings. |

### Type-specific fields

```json
{ "type": "mcq", "prompt": "...", "options": ["A", "B", "C", "D"], "answer": 2 }
```
2–6 options, `answer` is the 0-based index. Options are shuffled in the site; add
`"shuffle": false` only when order matters (e.g. "Both A and B").

```json
{ "type": "multi", "prompt": "Select all that apply: ...", "options": ["..."], "answer": [0, 3] }
```
3–6 options, `answer` lists every correct index (at least one, not all).

```json
{ "type": "truefalse", "prompt": "Statement to judge.", "answer": false }
```

```json
{ "type": "flashcard", "front": "Question or cue", "back": "Answer" }
```
For facts that are not key terms (dates, steps, formulas, cause → effect).

```json
{ "type": "recall", "prompt": "Explain ...", "answer": "Model answer in 2–5 sentences.",
  "keyPoints": ["point the learner must mention", "second point"] }
```
The learner types an answer, then ticks which key points they covered. 2–5 key points.

```json
{ "type": "matching", "prompt": "Match each term to its meaning.",
  "pairs": [ { "left": "Term", "right": "Meaning" }, ... ] }
```
3–8 pairs; every `left` and every `right` must be unique within the set.

## Progress data (inside the site)

The site stores progress in the browser under `ils:<course.id>` and can export it
as a JSON file. Learners move progress between devices with Export / Import.
Key-term flashcards use the id `kt:<module id>:<term index>`.

```json
{
  "courseId": "...", "format": 1, "updated": 1791700000000,
  "items":   { "<item id>": { "box": 0-5, "due": "YYYY-MM-DD", "seen": 3, "right": 2, "wrong": 1 } },
  "lessons": { "<module id>": true },
  "quizBest":{ "<module id>": 80 }
}
```

Spaced repetition uses six boxes (0–5) with intervals of 0, 1, 2, 4, 8 and 16 days.
Wrong / Again sends an item to box 0 (due today). Hard drops it one box (never
below 1). Good moves it up one box (at least to box 2). Easy moves it up two
(at least to box 3). A correct quiz, matching or fully covered recall answer
counts as Good; a recall answer covering at least half the key points counts as
Hard. An item counts as mastered from box 3, so it needs two successful reviews.
