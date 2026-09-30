# Sourced, not executed: the one definition of where the handbook tool Python lives.
# tools/select-python probes it and tools/setup-tool-python builds it, so the location
# has a single home and the two cannot drift about it.
#
# A per-user default, never a path inside a clone: global hooks resolve their interpreter
# through select-python, and an unrelated session must not fail because a clone moved
# (§session-logging). LQCD_HANDBOOK_TOOL_PYTHON overrides the default.

lqcd_tool_python_dir() {
    if [[ -n "${LQCD_HANDBOOK_TOOL_PYTHON:-}" ]]; then
        printf '%s\n' "$LQCD_HANDBOOK_TOOL_PYTHON"
        return 0
    fi
    local data="${XDG_DATA_HOME:-}"
    # The XDG specification says a relative value is invalid and must be ignored.
    if [[ "$data" != /* ]]; then
        [[ -n "${HOME:-}" ]] || return 1
        data="$HOME/.local/share"
    fi
    printf '%s\n' "$data/lqcd-agent-handbook/tool-python"
}
