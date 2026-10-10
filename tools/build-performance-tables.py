#!/usr/bin/env python3
"""Render each machine's performance rows into the generated table of its performance page.

`machines/<name>/performance.yaml` is the canonical home of a machine's performance references
(ARCHITECTURE.md, performance references). `machines/<name>/performance.md` holds their
interpretation and, between two marker lines, a table generated from the YAML, so the numbers
have one home and the page cannot drift from it. This tool writes that block, or with --check
reports every page whose block is missing or stale; the validator runs --check.

Rows are grouped by the application stack they name, in file order within each group, so a page
shows what each build achieved.

Usage:
    build-performance-tables.py [--root HANDBOOK] [--check]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

VERSION = "1.0.0"
BEGIN = (
    "<!-- BEGIN GENERATED performance table: tools/build-performance-tables.py renders "
    "this from performance.yaml; edit the YAML, never this block -->"
)
END = "<!-- END GENERATED performance table -->"


def number(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"{value:,}" if isinstance(value, int) else str(value)


def volume(values: list[int]) -> str:
    return "×".join(str(v) for v in values)


def render(record: dict[str, Any]) -> str:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in record.get("rows", []):
        groups.setdefault(row["stack"], []).append(row)
    lines = [BEGIN, ""]
    for stack, rows in groups.items():
        name = stack.split("/")[3]
        lines += [
            f"#### `{name}`",
            "",
            "| Row | Kind | Solver | Masses | RHS | Precision (sloppy) | Nodes | Ranks | "
            "`node_geometry` | Local volume | Off-node dims | Metric | Value (min–max) | "
            "Solves / runs | Iterations | Observed |",
            "|---|---|---|---:|---:|---|---:|---:|---|---|---|---|---|---|---|---|",
        ]
        for row in rows:
            placement, metric = row["placement"], row["metric"]
            kind = (
                f"probe {row['probe']['name']} {row['probe']['version']}"
                if row["kind"] == "probe"
                else "campaign"
            )
            off_node = ", ".join(placement["dimensions_off_node"]) or "none"
            lines.append(
                f"| `{row['id']}` | {kind} | `{row['solver']['path']}` | {row['solver']['masses']} | "
                f"{row['solver']['rhs']} | {row['precision']['precise']} "
                f"({row['precision']['sloppy']}) | {placement['nodes']} | {placement['ranks']} | "
                f"{' '.join(str(v) for v in placement['node_geometry'])} | "
                f"{volume(placement['local_volume'])} | {off_node} | `{metric['name']}` "
                f"({metric['unit']}) | {number(metric['value'])} ({number(metric['min'])}–"
                f"{number(metric['max'])}) | {metric['solves']} / {metric['runs']} | "
                f"{number(row['iterations']['value'])} | {row['observed']} |"
            )
        lines.append("")
    lines += [
        "Each row's full record — workload or probe version, warm state, binding, statistic and",
        "evidence — is in `performance.yaml`; build options are read from the named stack.",
        "",
        END,
    ]
    return "\n".join(lines)


def replace_block(text: str, block: str) -> str | None:
    if text.count(BEGIN) != 1 or text.count(END) != 1 or text.index(BEGIN) > text.index(END):
        return None
    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    return head + block + tail


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check", action="store_true", help="report stale pages; write nothing")
    parser.add_argument("--version", action="version", version=VERSION)
    args = parser.parse_args(argv)
    problems = 0
    for data in sorted(args.root.glob("machines/*/performance.yaml")):
        page = data.with_suffix(".md")
        rel = page.relative_to(args.root)
        if not page.is_file():
            print(f"{rel}: missing; performance.yaml needs a page holding the generated table")
            problems += 1
            continue
        record = yaml.safe_load(data.read_text())
        text = page.read_text()
        updated = replace_block(text, render(record if isinstance(record, dict) else {}))
        if updated is None:
            print(f"{rel}: needs exactly one generated-table block, opened and closed by the marker lines")
            problems += 1
        elif updated != text:
            if args.check:
                print(f"{rel}: generated table is stale; run tools/build-performance-tables.py")
                problems += 1
            else:
                page.write_text(updated)
                print(f"{rel}: generated table rewritten")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
