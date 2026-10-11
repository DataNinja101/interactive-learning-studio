# Writing good practice items

Applies to every item in a question bank or course. The aim is items that test
understanding of the source, that a careful learner cannot pass by spotting patterns,
and that teach something when answered wrong.

## Everything

- **One idea per item.** If an item tests two things, split it.
- **Stand-alone prompts.** Never "according to the passage above" or "as shown in the
  slide" — the learner may meet the item weeks later in a mixed review.
- **Test what matters.** Weight by importance in the source: section headings,
  definitions, emphasised text, repeated ideas, rules with conditions, steps, numbers
  that drive decisions. Do not test introductions, anecdotes or trivia (an author's
  name, a page's example company) unless the source treats them as essential.
- **Cover everything.** Every section of the source gets at least one item. The bank
  report lists pages that no item cites.
- **Prefer application.** For professional or technical material, a short realistic
  scenario ("A borrower misses three payments and then…") followed by "what happens /
  what should be done" beats a definition question.
- **Avoid negatives.** Prefer "Which is required…" over "Which is NOT required…". If a
  negative is unavoidable, bold it: `**not**`.
- **Explanations always.** Say why the right answer is right and, for choice items,
  why the most tempting wrong answer is wrong. One to three sentences.
- **Cite.** `source: {"ref": "s2", "loc": "p. 14"}`. Use the most specific location
  available: `p. 14`, `pp. 14–15`, `slide 7`, `Art. 44(2)`, `§3.1`, `sheet Rates`.

## Fidelity to sources

- Only facts the sources state. No outside facts in a materials-based course unless the
  user asks; if added, cite the `gk` source so they are visibly separate.
- Keep technical and official terms exactly as the source writes them (including
  Greek legal/administrative terms). For bilingual audiences, add a translation in
  parentheses rather than replacing the term.
- Numbers, dates, deadlines and thresholds must match the source exactly. Re-check them.
- If the source is ambiguous, either do not test that point or test only the
  unambiguous part. Never make the answer depend on an interpretation.

## Multiple choice (`mcq`)

- 4 options by default (3 is fine when only two plausible distractors exist).
- **Distractors are real alternatives**: common misconceptions, a neighbouring concept
  from the same material, the right rule applied to the wrong condition, a nearby
  number. Never joke options or obviously absurd ones.
- Options are parallel: same grammatical form, similar length and specificity. The
  correct option must not be the longest, most qualified or most technical by habit.
- No overlapping options (if B is true whenever A is, the item is broken).
- No "all of the above / none of the above". If it is truly needed, set
  `"shuffle": false` so its position stays last.
- Numeric options: list in ascending order with `"shuffle": false`.
- Where the correct option appears in the authored list does not matter — the site
  shuffles options.

## Select all that apply (`multi`)

- 4–5 options, 2–3 correct. Never all correct, never only one (use `mcq` then).
- Start the prompt with "Which of these…" and keep each option independently true or
  false.

## True / false (`truefalse`)

- An unambiguous statement, entirely true or entirely false.
- Make false statements plausible: change one element of a true fact (a number, the
  party responsible, a condition, the order of steps).
- Avoid giveaway absolutes ("always", "never", "only") unless the source uses them.
- Balance across the bank: roughly half true, half false.
- Use sparingly: about one in five choice items. They are good for misconceptions.

## Flashcards (`flashcard`) and key terms

- Key terms (module `keyTerms`): the vocabulary of the subject. Definition in one or
  two sentences, in the source's own sense of the term.
- Extra flashcards: atomic facts that are not definitions — a deadline, a sequence, a
  cause → effect, a formula, who does what. Front is a clear cue or question; back is
  short (under ~25 words).
- One fact per card. "List the five steps" is a recall prompt, not a flashcard.

## Active recall (`recall`)

- Open questions that require producing an explanation: explain why, compare, apply
  to a case, list and justify steps, predict an outcome.
- `answer`: a model answer of 2–5 sentences in plain language.
- `keyPoints`: 2–5 points the answer must contain, each checkable on its own and
  phrased as content ("Notice must be served before the sale"), not as instructions.
  The learner ticks the points they covered; that self-grade drives the schedule.

## Matching (`matching`)

- Homogeneous sets only: all terms → definitions, or all situations → outcomes, or
  all documents → purposes. Mixing kinds lets learners match by category.
- 4–6 pairs (3 minimum, 8 maximum). Right-hand sides short and similar in length.
- No pair should be guessable from grammar or shared words between left and right.
- `prompt` says what is being matched: "Match each document to what it proves."

## Difficulty

| Level | Tests | Example form |
|-------|-------|--------------|
| 1 | Recall a fact or term | "What is the deadline for…?" |
| 2 | Understand or apply one idea | "Which situation is an example of…?" |
| 3 | Analyse, combine ideas, judge a scenario | "Given these facts, what is the next step and why?" |

Aim for roughly 35% / 45% / 20% across the bank; recall prompts are usually 2–3.

## Quick self-check before saving an item

1. Could a learner who never read the source get it right by elimination or length? Rewrite.
2. Is there exactly one defensible answer (or exactly the listed set for `multi`)?
3. Does the explanation teach the point to someone who got it wrong?
4. Does the source location really contain this fact?
