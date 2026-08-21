# Public-Repository Privacy Rules

These rules apply only to the exact material proposed for this public repository, whether as
a user-mode inbox entry or a direct developer-mode change. They do not govern the working
project that holds source evidence: do not scan, redact, or rewrite that workspace under
handbook privacy rules. A successful automated check is never permission to publish.

Every inbox entry is public-repository content and must satisfy `PRIVACY.md` before
creation. The inbox is not a quarantine: raw, confidential, unpublished, or
not-yet-cleared material remains outside the repository.

## Never commit

- allocation, account, or project codes;
- usernames or user-specific paths;
- internal hostnames beyond documented public login hosts;
- email addresses, tokens, keys, credentials, ticket numbers, or job IDs;
- material from private repositories or collaborators' unshared work;
- embargoed datasets, unpublished ensemble parameters, or unpublished measurements;
- live campaign state, budgets, ledgers, retry counts, or raw run evidence.

Use portable placeholders such as `$SCRATCH`, `$PROJWORK`, `<user>`, and `<account>`.
Describe non-public evidence by class without giving a local path. Keep raw extractions in
the working directory beside their source; there is no `local/` or private overlay.

## Before admitting a fact

1. Decide whether it is durable knowledge or an episode.
2. Declare its scope and evidence kind; record observation conditions.
3. For mined material, obtain an affirmative publishability decision for the whole fact
   class. No decision means it stays out.
4. Check that the text reveals no category above, including indirectly.
5. Run `python3 tools/validate-knowledge.py` and report its limited checks accurately.

The validator detects patterns, schemas, provenance, and stale review dates. It cannot
recognize unpublished science or confidential context.
