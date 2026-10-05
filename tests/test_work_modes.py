"""The work-mode list is stated in three places that must agree.

Canonical `AGENTS.md` (and its mirror) names the modes, `playbooks/start-session.md` asks the
operator to choose among them, and `modes/` holds one document per mode. A mode added to one
place and not the others is silent: the session either never offers it or offers one it
cannot load.
"""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDBOOK_MODES = {"user", "developer"}


def mode_list(text: str, lead: str) -> set:
    normalized = " ".join(text.split())
    match = re.search(re.escape(lead) + r" ([a-z, ]+?)[.?]", normalized)
    if match is None:
        raise AssertionError(f"no mode list after {lead!r}")
    return {word for word in re.split(r",\s*(?:or\s+)?|\s+or\s+", match.group(1)) if word}


class WorkModeListTests(unittest.TestCase):
    def test_entrypoint_playbook_and_mode_documents_agree(self):
        entrypoint = mode_list((ROOT / "AGENTS.md").read_text(), "Exactly one work mode is current:")
        playbook = mode_list(
            (ROOT / "playbooks/start-session.md").read_text(),
            "which current work mode applies —",
        )
        documents = {path.stem for path in (ROOT / "modes").glob("*.md")} - HANDBOOK_MODES
        self.assertEqual(entrypoint, playbook)
        self.assertEqual(entrypoint, documents)

    def test_list_parser_is_not_vacuous(self):
        self.assertEqual(
            mode_list("Exactly one work mode is current: a, b, or c.", "Exactly one work mode is current:"),
            {"a", "b", "c"},
        )
        with self.assertRaises(AssertionError):
            mode_list("no list here", "Exactly one work mode is current:")

    def test_work_mode_names_do_not_echo_the_handbook_modes(self):
        # A work mode whose name shares a stem with a handbook mode lets a work-mode
        # declaration be read as a grant of handbook write access.
        documents = {path.stem for path in (ROOT / "modes").glob("*.md")} - HANDBOOK_MODES
        for work_mode in documents:
            for handbook_mode in HANDBOOK_MODES:
                self.assertNotEqual(work_mode[:5], handbook_mode[:5], work_mode)

    def test_every_work_mode_routes_to_batch_scripts_and_repeated_work(self):
        documents = {path.stem for path in (ROOT / "modes").glob("*.md")} - HANDBOOK_MODES
        for mode in documents:
            text = (ROOT / "modes" / f"{mode}.md").read_text()
            self.assertIn("conventions/batch-scripts.md", text, mode)
            self.assertIn("conventions/repeated-work.md", text, mode)


if __name__ == "__main__":
    unittest.main()
