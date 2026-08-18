#!/usr/bin/env python3
"""Check or apply clang-format to changed QUDA lines."""

import argparse
import difflib
import os
from pathlib import Path
import shutil
import subprocess
import sys


EXTENSIONS = ("c", "cc", "cpp", "cxx", "h", "hh", "hpp", "hxx", "inc", "cu", "cuh")
EXCLUDED_PREFIXES = ("tests/googletest/", "lib/generate/")
EXCLUDED_PATHSPECS = (":(exclude)tests/googletest/**", ":(exclude)lib/generate/**")
QUDA_MARKERS = (".clang-format", "CMakeLists.txt", "include/quda.h")


class ToolError(RuntimeError):
    pass


def run(command, *, cwd, capture=False, check=True):
    result = subprocess.run(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    if check and result.returncode:
        detail = ""
        if capture:
            detail = os.fsdecode(result.stderr or result.stdout).strip()
        raise ToolError("command failed: {}{}".format(" ".join(command), ": " + detail if detail else ""))
    return result


def output(command, *, cwd):
    return os.fsdecode(run(command, cwd=cwd, capture=True).stdout).strip()


def git_root():
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if result.returncode:
        raise ToolError("run this command inside a QUDA Git checkout")
    return Path(os.fsdecode(result.stdout).strip()).resolve()


def require_quda(root):
    missing = [marker for marker in QUDA_MARKERS if not (root / marker).exists()]
    if missing:
        raise ToolError("checkout does not look like QUDA; missing {}".format(", ".join(missing)))
    unresolved = output(["git", "diff", "--name-only", "--diff-filter=U"], cwd=root)
    if unresolved:
        raise ToolError("resolve unmerged paths before formatting:\n{}".format(unresolved))


def resolve_binary(name):
    candidate = shutil.which(name)
    if candidate is None:
        raise ToolError("clang-format binary not found: {}".format(name))
    return str(Path(candidate).resolve())


def require_git_clang_format(root):
    result = run(["git", "clang-format", "-h"], cwd=root, capture=True, check=False)
    if result.returncode:
        raise ToolError("git-clang-format is not available on PATH")


def reference_for_scope(root, scope, base):
    if scope == "worktree":
        if base is not None:
            raise ToolError("--base is valid only with --scope branch")
        reference = output(["git", "rev-parse", "--verify", "HEAD^{commit}"], cwd=root)
        print("scope: worktree")
        print("reference: HEAD ({})".format(reference))
        return reference

    if base is None:
        raise ToolError("--scope branch requires the intended pull-request target as --base")
    base_commit = output(["git", "rev-parse", "--verify", base + "^{commit}"], cwd=root)
    head = output(["git", "rev-parse", "--verify", "HEAD^{commit}"], cwd=root)
    merge_base = output(["git", "merge-base", base_commit, head], cwd=root)
    print("scope: branch")
    print("base: {} ({})".format(base, base_commit))
    print("merge-base: {}".format(merge_base))
    return merge_base


def eligible(path):
    normalized = path.as_posix()
    if any(normalized.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
        return False
    return path.suffix.lower().lstrip(".") in EXTENSIONS


def validate_paths(root, values):
    paths = []
    for value in values:
        relative = Path(value)
        if relative.is_absolute() or ".." in relative.parts:
            raise ToolError("paths must be repository-relative and may not contain '..': {}".format(value))
        normalized = relative.as_posix()
        if normalized in ("", ".") or value.startswith(":") or any(
            character in value for character in "*?["
        ):
            raise ToolError("use explicit literal repository-relative paths: {}".format(value))
        if any(normalized.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
            raise ToolError("QUDA formatter excludes {}".format(value))
        resolved = (root / relative).resolve()
        if resolved != root and root not in resolved.parents:
            raise ToolError("path resolves outside the QUDA checkout: {}".format(value))
        if resolved.is_dir():
            raise ToolError("use explicit file paths, not directories: {}".format(value))
        paths.append(normalized)
    return paths


def path_selected(path, selected):
    normalized = path.as_posix()
    return any(normalized == value or normalized.startswith(value.rstrip("/") + "/") for value in selected)


def untracked_files(root, selected):
    if not selected:
        return []
    raw = run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=root, capture=True
    ).stdout
    paths = []
    for value in raw.split(b"\0"):
        if not value:
            continue
        relative = Path(os.fsdecode(value))
        target = root / relative
        if path_selected(relative, selected) and eligible(relative) and target.is_file() and not target.is_symlink():
            paths.append(relative)
    return sorted(paths, key=lambda path: path.as_posix())


def run_git_clang_format(root, binary, reference, apply, paths):
    command = [
        "git",
        "clang-format",
        "--binary",
        binary,
        "--extensions",
        ",".join(EXTENSIONS),
        "--style",
        "file",
    ]
    if apply:
        command.append("--force")
    else:
        command.append("--diff")
    command.extend([reference, "--"])
    command.extend(paths or ["."])
    command.extend(EXCLUDED_PATHSPECS)
    result = run(command, cwd=root, check=False)
    if result.returncode not in (0, 1):
        raise ToolError("git-clang-format failed with status {}".format(result.returncode))
    return result.returncode == 1


def format_untracked(root, binary, paths, apply):
    changed = False
    for relative in paths:
        target = root / relative
        if apply:
            before = target.read_bytes()
            run([binary, "--style=file", "-i", str(relative)], cwd=root)
            if target.read_bytes() != before:
                changed = True
                print("formatted untracked file: {}".format(relative.as_posix()))
            continue

        before = target.read_bytes()
        formatted = run(
            [binary, "--style=file", str(relative)], cwd=root, capture=True
        ).stdout
        if formatted == before:
            continue
        changed = True
        before_text = before.decode("utf-8", errors="replace").splitlines(True)
        after_text = formatted.decode("utf-8", errors="replace").splitlines(True)
        sys.stdout.writelines(
            difflib.unified_diff(
                before_text,
                after_text,
                "a/" + relative.as_posix(),
                "b/" + relative.as_posix(),
            )
        )
    return changed


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check or apply QUDA clang-format to changed lines. Check mode is the default."
    )
    parser.add_argument("--scope", choices=("worktree", "branch"), required=True)
    parser.add_argument("--base", help="intended pull-request target ref")
    parser.add_argument("--apply", action="store_true", help="apply formatting in place")
    parser.add_argument("--binary", default="clang-format", help="clang-format executable")
    parser.add_argument("paths", nargs="*", help="repository-relative paths to format")
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        root = git_root()
        require_quda(root)
        paths = validate_paths(root, args.paths)
        if args.scope == "worktree" and not paths:
            raise ToolError("--scope worktree requires the paths changed by the current task")
        binary = resolve_binary(args.binary)
        require_git_clang_format(root)
        version = output([binary, "--version"], cwd=root)
        reference = reference_for_scope(root, args.scope, args.base)
        print("clang-format: {}".format(version))
        print("paths: {}".format(", ".join(paths) if paths else "full branch diff"))
        sys.stdout.flush()
        tracked_changed = run_git_clang_format(root, binary, reference, args.apply, paths)
        new_files = untracked_files(root, paths)
        untracked_changed = format_untracked(root, binary, new_files, args.apply)
        changed = tracked_changed or untracked_changed
        if args.apply:
            print("formatting applied" if changed else "formatting already clean")
            return 0
        print("formatting changes required" if changed else "formatting check clean")
        return 1 if changed else 0
    except ToolError as error:
        print("error: {}".format(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
