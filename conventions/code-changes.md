---
title: References in software changes must be durable and public
summary: Comments, messages, test descriptions, and commit messages in a software change may cite durable public sources such as published papers, DOIs, or upstream issues, but never working-directory notes, plans, validation directories, local paths, or the handbook.
scope: [universal]
load_when: Writing or reviewing a source change to any software repository, including its comments, log and error messages, test descriptions, and commit message.
evidence: operator
observed: "2026-10-07"
observed_on:
  requirements: durable-references-in-software-changes
review_by: "2027-10-07"
---

# References in software changes must be durable and public

A source change outlives the session that made it and is read by people who never see the
working directory it was made in: reviewers, upstream maintainers, and later sessions on other
machines. A reference in the change is acceptable only if every one of those readers can follow
it, now and later. `[operator]`

**Allowed: durable public sources.** A published paper, by citation, DOI or arXiv identifier;
an upstream issue, pull request or commit; public documentation; a file in the same repository.

**Never: anything that exists only where the change was made.**

- working-directory notes, plans, design documents, validation or run directories, and session
  logs. A comment reading `see <topic>-notes.md` resolves for its author on one machine and
  dangles for every other reader;
- absolute or user-specific paths, scratch locations, allocation codes and job IDs, which in a
  public repository are a privacy defect as well;
- the handbook. It is not part of the software, and its leaves move between revisions, so code
  does not cite `$LQCD_HANDBOOK` paths or leaf names;
- a session, a conversation, or "the plan".

The defect is silent because the reference looks helpful to the person who wrote it.

**When the source is not public, write the mechanism in place.** State what the code guards and
why, in as few lines as it takes. Notes and validation evidence stay in the working directory,
and a commit or pull-request description may summarise what they established.

**Check before handoff.** Search the diff's added lines for the working directory's own
filenames and for path fragments such as `.md` or `/home`, and confirm that every hit is in the
same repository or is a durable public source.

## Evidence and limits

Operator policy, from a correction of one change in which a new function's comment named a
design note kept in the working directory. The mechanism is reachability: a reference is only as
durable as its target. No tool enforces it yet.
