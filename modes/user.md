# User Mode

User mode is the default handbook mode. The handbook is read-only even when the surrounding
agent session has broad write permissions.

You may create a new, uniquely named file under `inbox/proposals/` or
`inbox/rejections/`. Never append to or edit an existing inbox file. Include the current
handbook commit so a later developer can distinguish a contradiction from stale context.

Apply `PRIVACY.md` only to the exact inbox file you propose to create. Do not scan, redact,
or rewrite the working project under handbook privacy rules; preserve its operational
evidence under its own instructions.

When handbook guidance appears wrong or incomplete, explain the deficiency and offer to
file a proposal. Do not repair canonical knowledge, tools, schemas, indices, architecture,
or roadmap files without an explicit switch to developer mode.

Raw mining output and live campaign state remain in the working directory, not in this
repository.
