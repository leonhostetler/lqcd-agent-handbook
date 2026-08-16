#!/usr/bin/env bash
set -euo pipefail

# Regenerate a user/assistant-only Claude Code session log after each turn.
umask 077

input=$(cat)
transcript=$(printf '%s' "$input" | jq -r '.transcript_path // empty')
[[ -n "$transcript" && -f "$transcript" ]] || exit 0

launch_dir="${CLAUDE_PROJECT_DIR:-}"
[[ -n "$launch_dir" ]] || launch_dir=$(printf '%s' "$input" | jq -r '.cwd // empty')
[[ -n "$launch_dir" ]] || launch_dir="$PWD"

session_id=$(printf '%s' "$input" | jq -r '.session_id // empty | gsub("[^A-Za-z0-9._-]"; "_")')
name="session_$(date +%Y-%m-%d)"
[[ -n "$session_id" ]] && name="${name}_${session_id}"
output="$launch_dir/${name}.log"

read -r -d '' jq_program <<'JQ' || true
def texts: [ .[] | select(.type=="text") | .text ] | join("\n\n");
[ .[]
  | select(.type=="user" or .type=="assistant")
  | select((.isMeta // false) | not)
  | if .type=="user" then
      ( (.message.content) as $content
        | if ($content|type)=="string" then $content
          elif ($content|type)=="array"
               and (any($content[]; .type=="tool_result")|not)
            then ($content | texts)
          else "" end ) as $text
      | select(($text|gsub("\\s";""))|length > 0)
      | {role:"User", text:$text}
    else
      (.message.content | texts) as $text
      | select(($text|gsub("\\s";""))|length > 0)
      | {role:"Assistant", text:$text}
    end ]
JQ

# Stop can fire before the final transcript block finishes flushing. Wait for
# three unchanged size samples, capped at about five seconds.
previous=-1
stable=0
for ((sample = 0; sample < 20; sample++)); do
  size=$(stat -c %s "$transcript" 2>/dev/null || stat -f %z "$transcript" 2>/dev/null || echo 0)
  if [[ "$size" == "$previous" ]]; then
    stable=$((stable + 1))
    [[ "$stable" -ge 3 ]] && break
  else
    stable=0
  fi
  previous=$size
  sleep 0.25
done

temporary=$(mktemp "$launch_dir/.${name}.XXXXXX")
cleanup() {
  rm -f "$temporary"
}
trap cleanup EXIT
jq -rs "$jq_program"' | map("## " + .role + "\n\n" + .text) | join("\n\n")' \
  "$transcript" > "$temporary"
chmod 600 "$temporary"
mv -f "$temporary" "$output"
trap - EXIT
