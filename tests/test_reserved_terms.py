"""`configuration` means a gauge configuration; the parameter set is a `candidate`.

ARCHITECTURE.md 5.5. In lattice QCD a configuration is an element of the gauge ensemble, so
using the word for a parameter set invites a reader to think a different gauge field was
used. `setup` is likewise reserved for a solver's setup phase, which is why the parameter
set is not called a "candidate setup".

This is a word-level heuristic, not a parser. It checks the phrasings that actually recurred.
"""

import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
# Only where a *gauge* configuration is a live reading. In playbooks/session-logging.md or
# modes/debugging.md, "configuration" means a config file and no LQCD reader is misled, so
# policing it there would force awkward rewording for no gain.
SCOPES = (
    "software/quda",
    "software/milc",
    "playbooks/tune-solver.md",
    "modes/tuning.md",
    "modes/benchmarking.md",
    "conventions/measurement.md",
)

# `configuration` is admissible only in these senses.
ALLOWED = re.compile(
    # "gauge" anywhere in the window, on either side: the qualifier is written both as
    # "gauge configuration" and as "per-configuration gauge loads".
    r"gauge"
    r"|configuration[- ]specific"
    r"|misconfiguration"
    r"|configuration error"
    # Build/CMake senses: unambiguous in context and standard usage.
    r"|(build|CMake|JIT|out-of-source|resolved) configuration",
    re.IGNORECASE,
)

RETIRED = re.compile(r"candidate setup", re.IGNORECASE)


def docs():
    for scope in SCOPES:
        target = ROOT / scope
        if target.is_file():
            yield target
        else:
            for f in sorted(target.rglob("*.md")):
                yield f


class ReservedTermTests(unittest.TestCase):
    def test_configuration_means_gauge_configuration(self):
        offenders = []
        for f in docs():
            text = f.read_text()
            for m in re.finditer(r"\bconfigurations?\b", text):
                # Normalize: the qualifier often wraps onto the previous line.
                window = " ".join(
                    text[max(0, m.start() - 40) : m.end() + 20].split()
                )
                if ALLOWED.search(window):
                    continue
                line = text[: m.start()].count("\n") + 1
                offenders.append(f"{f.relative_to(ROOT)}:{line}")
        self.assertEqual(
            offenders,
            [],
            "`configuration` used for something other than a gauge configuration. "
            "The parameter set is a `candidate` — see ARCHITECTURE.md 5.5:\n"
            + "\n".join(offenders),
        )

    def test_candidate_setup_is_retired(self):
        offenders = [
            str(f.relative_to(ROOT)) for f in docs() if RETIRED.search(f.read_text())
        ]
        self.assertEqual(
            offenders,
            [],
            "`candidate setup` is retired: `setup` means a solver setup phase. "
            f"Use `candidate`. Found in: {offenders}",
        )

    def test_the_rule_is_stated_and_names_this_test(self):
        arch = (ROOT / "ARCHITECTURE.md").read_text()
        self.assertIn('<a id="reserved-terms"></a>', arch)
        self.assertIn("tests/test_reserved_terms.py", arch)


if __name__ == "__main__":
    unittest.main()
