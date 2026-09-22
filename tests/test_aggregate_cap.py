"""The 1024 aggregate cap binds the executed block product, at every aggregation.

Three properties of that cap have each been stated wrongly somewhere, and each is pinned here.

It binds `block_volume`, not `aggregate_space_capacity`. QUDA calls both "aggregate size" --
block orthogonalization means the bare geometric product, the transfer constructor means that
product times the fine colour and spin factors -- and their errors both say so. A four-level
candidate was once recorded as `∏block1 = 256 <= 1024` when its first-aggregation block volume
was 1024, exactly at the cap; the 256 was the second aggregation's space capacity.

It binds the EXECUTED block, after QUDA's halving, so a requested product above 1024 is not by
itself illegal.

It binds EVERY aggregation transfer, not only the first.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DECOMPOSITION = ROOT / "tools/quda-staggered-decomposition.py"


def run(*args: str):
    result = subprocess.run(
        [sys.executable, str(DECOMPOSITION), *args],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    return result, json.loads(result.stdout)


class AggregateCapTests(unittest.TestCase):
    def test_cap_and_margin_travel_with_block_volume(self):
        """The candidate whose margin was misread: level 1 sits exactly at the cap."""
        _, payload = run(
            "--global", "96", "96", "96", "192", "--ranks", "2", "3", "2", "12",
            "--levels", "4", "--block1", "4", "4", "8", "8", "--block2", "2", "2", "1", "1",
            "--nvec1", "64", "--nvec2", "96", "--mma",
        )
        self.assertEqual(payload["source_status"], "pass")
        first, second = payload["levels"]
        self.assertEqual(first["block_volume"], 1024)
        self.assertEqual(first["block_volume_cap"], 1024)
        self.assertEqual(first["block_volume_headroom"], 0)
        # The number that was read instead. It is a different quantity, at a different level,
        # and it carries no cap field of its own.
        self.assertEqual(second["aggregate_space_capacity"], 256)
        self.assertNotIn("aggregate_space_capacity_headroom", second)
        self.assertEqual(second["block_volume_headroom"], 1020)

    def test_a_requested_product_above_the_cap_can_still_be_legal(self):
        """Same block, two placements: halving rescues it at one of them."""
        base = ("--global", "96", "96", "96", "192", "--levels", "3",
                "--block1", "4", "6", "6", "8", "--nvec1", "64", "--mma")
        strict, strict_payload = run(*base, "--ranks", "2", "2", "2", "4")
        loose, loose_payload = run(*base, "--ranks", "2", "2", "2", "8")

        self.assertEqual(strict_payload["source_status"], "error")
        self.assertEqual(strict.returncode, 2)
        self.assertEqual(strict_payload["levels"][0]["effective_block"], [4, 6, 6, 8])
        self.assertEqual(strict_payload["levels"][0]["block_volume"], 1152)

        self.assertEqual(loose_payload["source_status"], "pass")
        self.assertEqual(loose.returncode, 0)
        self.assertEqual(loose_payload["levels"][0]["requested_block"], [4, 6, 6, 8])
        self.assertEqual(loose_payload["levels"][0]["effective_block"], [4, 6, 6, 4])
        self.assertEqual(loose_payload["levels"][0]["block_volume"], 576)
        self.assertEqual(loose_payload["levels"][0]["block_volume_headroom"], 448)

    def test_the_cap_binds_the_second_aggregation_too(self):
        _, payload = run(
            "--global", "96", "96", "96", "192", "--ranks", "2", "2", "2", "4",
            "--levels", "4", "--block1", "4", "4", "4", "4", "--block2", "6", "6", "6", "6",
            "--nvec1", "64", "--nvec2", "96", "--mma",
        )
        self.assertEqual(payload["source_status"], "error")
        self.assertEqual(
            payload["source_errors"], ["level 2: MG aggregate size 1296 must be <= 1024"]
        )
        self.assertEqual(payload["levels"][0]["block_volume_headroom"], 768)
        self.assertEqual(payload["levels"][1]["block_volume_headroom"], -272)

    def test_headroom_is_reported_for_every_level(self):
        """A per-level field that appears at only one level invites the original mistake."""
        _, payload = run(
            "--global", "96", "96", "96", "192", "--ranks", "2", "3", "2", "12",
            "--levels", "4", "--block1", "4", "4", "8", "8", "--block2", "2", "2", "1", "1",
            "--nvec1", "64", "--nvec2", "96", "--mma",
        )
        for level in payload["levels"]:
            self.assertIn("block_volume_cap", level)
            self.assertIn("block_volume_headroom", level)
            self.assertEqual(
                level["block_volume_headroom"],
                level["block_volume_cap"] - level["block_volume"],
            )


if __name__ == "__main__":
    unittest.main()
