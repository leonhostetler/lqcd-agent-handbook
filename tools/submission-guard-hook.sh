#!/usr/bin/env bash
# LQCD handbook submission guard -- PreToolUse shim, installed into the user's frontend
# configuration (Claude Code or Codex; both speak the same command-hook protocol) by
# tools/install-submission-guard.py. Do not edit the installed copy; the startup checker
# compares it with the handbook and offers repair when they drift.
#
# It carries no handbook path. In a session launched through the handbook, LQCD_HANDBOOK
# names the live clone and the decision is delegated to that clone's tools; anywhere else
# this shim has no opinion and exits 0, so an unrelated session cannot fail because a
# clone moved. Inside a handbook session it fails CLOSED: a guard that waves a submission
# through because it could not run is not a guard.
set -u

input=$(cat)
hb="${LQCD_HANDBOOK:-}"
if [[ -z "$hb" ]]; then
  exit 0
fi
guard="$hb/tools/run-submission-guard"
surfaces="$hb/conventions/scheduler-surfaces.yaml"

# Cheap pre-filter: only a command that names a recorded submit command costs an interpreter.
# If the surface file cannot be read, skip the filter rather than skip the guard.
if [[ -r "$surfaces" ]]; then
  commands=$(sed -n 's/^[[:space:]]*submit_command:[[:space:]]*//p' "$surfaces" | tr -d '"' | tr '\n' '|')
  commands=${commands%|}
  if [[ -n "$commands" ]] && ! grep -qE "(^|[^A-Za-z0-9_./-])(${commands})([^A-Za-z0-9_-]|$)" <<< "$input"; then
    exit 0
  fi
fi

if [[ ! -x "$guard" ]]; then
  echo "submission refused: LQCD_HANDBOOK=$hb names no runnable tools/run-submission-guard; the handbook session is misconfigured" >&2
  exit 2
fi

reason=$(printf '%s' "$input" | "$guard" 2>&1)
rc=$?
if [[ $rc -eq 0 ]]; then
  exit 0
fi
if [[ $rc -ne 2 ]]; then
  echo "submission refused: the submission guard could not run (exit $rc):" >&2
fi
printf '%s\n' "$reason" >&2
exit 2
