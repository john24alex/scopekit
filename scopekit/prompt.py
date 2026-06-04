import subprocess
import sys

# ── templates ─────────────────────────────────────────────────────────────────

_CLAUDE = """\
Only look at these folders:
{paths}

If you find references to code OUTSIDE this scope that are relevant to the bug, let me know before expanding.

Do not read files outside the selected scope without asking me first.\
"""

_CURSOR = """\
# ScopeKit — Active debug scope
# Only read files inside these folders:
{paths}
# If you find relevant references outside this scope, ask before expanding.\
"""

_COPILOT = """\
## Active debug scope (set by ScopeKit)

Only read and suggest changes inside these folders:
{paths}

Ask before reading files outside this scope.\
"""


def generate_prompt(paths, fmt="claude"):
    if not paths:
        return ""
    fmt = fmt.lower()
    if fmt == "cursor":
        formatted = "\n".join(f"{p}/" for p in sorted(paths))
        return _CURSOR.format(paths=formatted)
    elif fmt == "copilot":
        formatted = "\n".join(f"- `{p}/`" for p in sorted(paths))
        return _COPILOT.format(paths=formatted)
    else:
        formatted = "\n".join(f"  • {p}/" for p in sorted(paths))
        return _CLAUDE.format(paths=formatted)


# ── clipboard ─────────────────────────────────────────────────────────────────

def copy_to_clipboard(text):
    encoded = text.encode()
    try:
        if sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=encoded, check=True)
            return True
        elif sys.platform == "win32":
            subprocess.run(["clip"], input=encoded, check=True, shell=True)
            return True
        else:
            # Linux: try xclip then xsel
            for cmd in (["xclip", "-selection", "clipboard"],
                        ["xsel", "--clipboard", "--input"]):
                try:
                    subprocess.run(cmd, input=encoded, check=True)
                    return True
                except FileNotFoundError:
                    continue
    except Exception:
        pass
    return False
