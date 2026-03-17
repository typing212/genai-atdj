"""
PreToolUse hook: blocks Read/Grep access to .env files.
Run via: uv run python .claude/hooks/check_env_access.py
Allows .env.example — only blocks the real secrets file.
"""
import sys
import json
import re

data = json.load(sys.stdin)
inp = data.get("tool_input", {})

file_path = str(inp.get("file_path", ""))
path = str(inp.get("path", ""))
combined = file_path + path

# Match .env exactly (not .env.example, .env.test, etc.)
if re.search(r"(^|[/\\])\.env$", combined):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                ".env is protected and must not be read directly. "
                "Use .env.example to reference available variable names."
            )
        }
    }))