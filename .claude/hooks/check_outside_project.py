"""
PreToolUse hook: block Edit/Write/Bash if target path is outside the project folder.
Forces 'ask' permission even when auto/bypass mode is active.
"""
import json
import sys
import os
import shlex


PROJECT_DIR = r"C:\Users\Vanessa\Desktop\Columbia\Spring 26\GenAI\Project\genai_atdj"


def normalize(p: str) -> str:
    """Normalize both /c/Users/... and C:\\Users\\... to a comparable form."""
    p = p.replace("\\", "/")
    # Convert /c/Users/... → C:/Users/...
    if len(p) > 2 and p[0] == "/" and p[2] == "/":
        p = p[1].upper() + ":" + p[2:]
    return os.path.normcase(os.path.normpath(p))


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    # For Bash, do a best-effort scan for out-of-project paths in the command
    if not file_path:
        command = tool_input.get("command", "")
        if not command:
            sys.exit(0)
        # Extract any tokens that look like absolute paths
        tokens = shlex.split(command)
        candidates = [
            t for t in tokens
            if t.startswith("/") or (len(t) > 2 and t[1] == ":")
        ]
        # Flag if any candidate is outside project
        outside = [
            t for t in candidates
            if not normalize(t).startswith(normalize(PROJECT_DIR))
        ]
        if outside:
            result = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "ask",
                    "permissionDecisionReason": (
                        f"Bash command references path(s) outside the project folder: "
                        f"{', '.join(outside)}. Explicit permission required."
                    ),
                }
            }
            print(json.dumps(result))
        sys.exit(0)

    file_path = os.path.abspath(file_path)
    norm_file = normalize(file_path)
    norm_project = normalize(PROJECT_DIR)

    if not norm_file.startswith(norm_project):
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": (
                    f"'{file_path}' is outside the project folder "
                    f"({PROJECT_DIR}). Explicit permission required even in auto/bypass mode."
                ),
            }
        }
        print(json.dumps(result))


if __name__ == "__main__":
    main()
