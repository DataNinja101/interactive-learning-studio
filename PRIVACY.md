# Privacy

Interactive Learning Studio collects no data. It has no servers, analytics,
telemetry or tracking, and makes no network requests of its own.

**While the plugin runs**, its skills and scripts work only on the files you give
Claude, inside your own Claude session. Source materials are read locally to write
the course; nothing is sent anywhere by the plugin. When building a course from a
topic rather than from your materials, Claude may use its normal web search to check
facts, as in any other conversation.

**The learning sites it produces** are single HTML files with everything built in.
They load no fonts, scripts or images from the internet. Learner progress is stored
only in the learner's own browser (`localStorage`) and leaves it only when the learner
chooses Export progress, which saves a file to their own device.

**Ask Claude.** Sites have an Ask Claude button on lessons and answered items. It does
nothing until a learner uses it, and the learner's progress is never included.

- In a downloaded site, *Open in Claude* opens claude.ai in a new tab, with the learner's
  question, the item or lesson text and the learner's answer to that item in the link,
  and copies the same text to the clipboard. Nothing reaches Claude until the learner sends the message there, under
  their own Claude account and Anthropic's terms.
- In a site published as a claude.ai Artifact with Claude access, the question, the
  item or lesson text and the learner's answer to that item go to Claude through
  claude.ai, after the learner allows it, using the learner's own Claude account.

Course authors can remove the button by setting `"askClaude": false` in the course.

Questions: open an issue at
https://github.com/DataNinja101/interactive-learning-studio/issues
