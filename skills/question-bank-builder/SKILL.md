---
name: "question-bank-builder"
description: "Turns course materials (PDF, Word, PowerPoint, Excel, notes, web pages) into a reviewed, source-cited question bank of quiz questions, flashcards, key terms, recall prompts and matching sets, ready to become an Interactive Learning Studio site. Use when the user asks to \"make questions from these notes\", \"build a question bank\", \"extract quiz questions / flashcards from this PDF\", \"check the questions before building the course\", \"φτιάξε ερωτήσεις από το υλικό\", or when the site builder is given large materials (more than ~15 pages or several documents)."
---

# Question bank builder

Produce a question bank that is complete, accurate to its sources, and checked before
anyone builds a site from it. The bank is a course JSON file in exactly the format the
site builder uses (`../interactive-learning-studio/references/data-schema.md`), with
modules, key terms and practice items; lessons may stay empty until the site is built.

Paths below are relative to this skill's base directory.

## 1. Extract the sources

Copy the user's files into a working folder (never edit their originals), then:

```bash
python3 scripts/extract_sources.py <files or folder> -o sources/
```

This writes one page-marked text file per source (`=== page 12 ===`, `=== slide 3 ===`)
plus `sources/sources.json`, and prints a ready-made `sources` array for the bank.
Rename source titles to something a learner would recognise ("Lecture 3 – Registration"
rather than "lecture3_final_v2").

- Pages reported as having little or no text are usually scans. OCR them (the pdf skill
  covers OCR) or tell the user which pages cannot be read and ask for a text version.
  Never write items for unread pages.
- For links, fetch the page and save its text as a `.txt` file in the working folder,
  then include it like any other source with its `url`.

## 2. Read everything and map it

Read every source text file in full. Then write a coverage map (in your notes, not for
the user): the topics in order, with their source and page ranges, and what in each is
important enough to test. Group topics into 3–8 modules — each one coherent idea,
foundations first. Note any contradictions or unclear passages between sources.

## 3. Write the bank, one module at a time

Create the bank file with `schemaVersion`, `course` (kebab-case `id` that will never
change, `title`, `language` of the materials), `sources`, and the module list. Then fill
one module per step:

- `keyTerms`: 3–8 per module, each with `source`.
- Items following `references/question-writing.md`. Per module aim for 6–10 choice
  items, 2–4 extra flashcards, 2–3 recall prompts, 1 matching set; about 15–25 items per
  10 dense pages overall.
- Every item and key term gets `source: {"ref", "loc"}` with the page, slide, article or
  section it came from. Item ids like `m2-q5`, unique and stable.

## 4. Check it

```bash
python3 ../interactive-learning-studio/scripts/build_site.py bank.json --bank
python3 scripts/bank_report.py bank.json --sources sources/sources.json -o review.md
```

The first command validates the structure. The report lists coverage by module and
type, source pages no item cites, near-duplicates, answers guessable by length,
unbalanced true/false, negatively worded prompts and missing explanations, followed by
a full answer key.

Fix every validation error and work through the findings: write items for uncited
pages that contain testable content, rewrite giveaways and duplicates. Some gaps are
fine (title pages, tables of contents, references) — leave those. Re-run both commands
until only deliberate findings remain. Then re-read a sample of items against their
cited pages to confirm facts, numbers and answer indexes.

## 5. Review with the user

When the user is present, send `review.md` (the answer key with findings) and give a
short summary in the reply: modules, item counts by type, anything not covered and
why, and any contradictions found in the sources. Ask whether to adjust anything or
build the site. Apply requested changes to the bank, re-run step 4, and repeat.

When the user is not present (scheduled or unattended work), skip the wait: note the
summary at the top of the final message and continue to step 6.

## 6. Hand off

- **To build the learning site**: load the `interactive-learning-studio` skill and
  continue from its step 3 with this bank — it adds lessons, builds and checks the site.
- **Bank only**: deliver `bank.json` and `review.md`. The answer key in `review.md` is
  printable and works as a paper quiz or an exam-prep sheet.

## Updating an existing bank or site

To add material to a course built earlier, extract its data
(`../interactive-learning-studio/scripts/build_site.py --extract site.html -o bank.json`),
number new sources after the existing ones (`extract_sources.py --start N`), add new
modules or items with new ids, and keep every existing id unchanged so learners keep
their progress.
