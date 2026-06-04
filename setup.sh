#!/bin/bash
mkdir -p scopekit

cat > scopekit/__init__.py << 'EOF'
"""ScopeKit — Select project scope before debugging with Claude Code."""
__version__ = "0.1.0"
EOF

cat > scopekit/tree.py << 'EOF'
import os
from pathlib import Path

DEFAULT_IGNORE = {
    ".git", ".idea", ".vscode", "__pycache__", "node_modules",
    ".dart_tool", ".flutter-plugins", "build", "dist", ".gradle",
    ".cache", "Pods", ".symlinks", "coverage", ".scope",
    "graphify-out", ".pub-cache", ".pub", "vendor",
}

def load_scopeignore(root):
    ignore = set()
    f = root / ".scopeignore"
    if f.exists():
        for line in f.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                ignore.add(line)
    return ignore

def build_tree(root, max_depth=4, extra_ignore=None):
    ignore = DEFAULT_IGNORE | (extra_ignore or set())
    def _walk(path, depth):
        if depth > max_depth:
            return {}
        result = {}
        try:
            for entry in sorted(path.iterdir()):
                if not entry.is_dir(): continue
                if entry.name in ignore or entry.name.startswith("."): continue
                result[entry.name] = _walk(entry, depth + 1)
        except PermissionError:
            pass
        return result
    return _walk(root, 0)

def flatten_tree(tree, prefix=""):
    paths = []
    for key, subtree in tree.items():
        full = f"{prefix}/{key}" if prefix else key
        paths.append(full)
        if subtree:
            paths.extend(flatten_tree(subtree, full))
    return paths

def get_project_name(root):
    pubspec = root / "pubspec.yaml"
    if pubspec.exists():
        for line in pubspec.read_text().splitlines():
            if line.startswith("name:"):
                return line.split(":", 1)[1].strip()
    pjson = root / "package.json"
    if pjson.exists():
        import json
        try:
            return json.loads(pjson.read_text()).get("name", root.name)
        except: pass
    return root.name

def detect_framework(root):
    if (root / "pubspec.yaml").exists(): return "Flutter/Dart"
    if (root / "package.json").exists(): return "Node.js"
    if (root / "Cargo.toml").exists(): return "Rust"
    if (root / "go.mod").exists(): return "Go"
    if (root / "requirements.txt").exists(): return "Python"
    return "Unknown"
EOF

cat > scopekit/presets.py << 'EOF'
import json
from pathlib import Path

SCOPE_DIR = ".scope"
PRESETS_DIR = ".scope/presets"

def ensure_scope_dir(root):
    (root / SCOPE_DIR).mkdir(exist_ok=True)
    (root / PRESETS_DIR).mkdir(exist_ok=True)
    gitkeep = root / PRESETS_DIR / ".gitkeep"
    if not gitkeep.exists(): gitkeep.touch()

def list_presets(root):
    d = root / PRESETS_DIR
    if not d.exists(): return []
    return sorted([p.stem for p in d.glob("*.json")])

def load_preset(root, name):
    f = root / PRESETS_DIR / f"{name}.json"
    if not f.exists(): return []
    return json.loads(f.read_text()).get("paths", [])

def save_preset(root, name, paths):
    ensure_scope_dir(root)
    f = root / PRESETS_DIR / f"{name}.json"
    f.write_text(json.dumps({"name": name, "paths": sorted(paths)}, indent=2))

def delete_preset(root, name):
    f = root / PRESETS_DIR / f"{name}.json"
    if f.exists():
        f.unlink()
        return True
    return False
EOF

cat > scopekit/prompt.py << 'EOF'
import subprocess, sys

PROMPT_TEMPLATE = """Only look at these folders:
{paths}

If you find references to code OUTSIDE this scope that are relevant to the bug, let me know before expanding.

Do not read files outside the selected scope without asking me first."""

def generate_prompt(paths):
    if not paths: return ""
    formatted = "\n".join(f"  • {p}/" for p in sorted(paths))
    return PROMPT_TEMPLATE.format(paths=formatted)

def copy_to_clipboard(text):
    try:
        if sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text.encode(), check=True)
            return True
    except: pass
    return False
EOF

cat > scopekit/cli.py << 'EOF'
import sys
from pathlib import Path

try:
    import questionary
    from questionary import Style
except ImportError:
    print("Run: pip3 install questionary")
    sys.exit(1)

from .tree import build_tree, flatten_tree, get_project_name, detect_framework, load_scopeignore
from .presets import list_presets, load_preset, save_preset, delete_preset, ensure_scope_dir
from .prompt import generate_prompt, copy_to_clipboard

STYLE = Style([
    ("qmark",       "fg:#58a6ff bold"),
    ("question",    "fg:#c9d1d9 bold"),
    ("answer",      "fg:#7ee787 bold"),
    ("pointer",     "fg:#58a6ff bold"),
    ("highlighted", "fg:#58a6ff bold"),
    ("selected",    "fg:#7ee787"),
    ("instruction", "fg:#6e7681"),
])

def print_header(name, fw):
    print(f"\n  \033[1;34m🎯 ScopeKit\033[0m  \033[2m{name} · {fw}\033[0m")
    print(f"  \033[2mSelect scope before sending the bug to Claude Code\033[0m\n")

def run(root=None):
    root = root or Path.cwd()
    print_header(get_project_name(root), detect_framework(root))
    extra_ignore = load_scopeignore(root)

    mode = questionary.select(
        "Where is the bug?",
        choices=[
            questionary.Choice("🔍  Select specific folders", value="select"),
            questionary.Choice("⚡  Load a saved preset",     value="preset"),
            questionary.Choice("📁  Entire project",          value="all"),
        ],
        style=STYLE,
    ).ask()

    if mode is None:
        print("\n  Cancelled.\n"); return

    selected = []

    if mode == "select":
        tree = build_tree(root, extra_ignore=extra_ignore)
        paths = flatten_tree(tree)
        if not paths:
            print("  No folders found.\n"); return

        choices = [
            questionary.Choice(
                title=("  " * p.count("/")) + "📁 " + p.split("/")[-1] + f"  \033[2m({p})\033[0m",
                value=p
            ) for p in paths
        ]
        selected = questionary.checkbox(
            "Select folders (space to toggle, enter to confirm):",
            choices=choices,
            style=STYLE,
        ).ask()
        if not selected:
            print("\n  Nothing selected. Cancelled.\n"); return

    elif mode == "preset":
        presets = list_presets(root)
        if not presets:
            print("  No presets yet. Select folders first and save a preset.\n"); return
        chosen = questionary.select("Choose a preset:", choices=presets, style=STYLE).ask()
        if not chosen: return
        selected = load_preset(root, chosen)

    elif mode == "all":
        selected = [p for p in flatten_tree(build_tree(root, max_depth=1, extra_ignore=extra_ignore)) if "/" not in p]

    prompt = generate_prompt(selected)
    copied = copy_to_clipboard(prompt)

    print("\n  \033[1;32m✓ Scope set:\033[0m")
    for p in sorted(selected):
        print(f"    \033[32m• {p}/\033[0m")

    if copied:
        print("\n  \033[1;32m✓ Prompt copied to clipboard — paste it in Claude Code\033[0m\n")
    else:
        print(f"\n{prompt}\n")

    if mode == "select":
        if questionary.confirm("Save as preset?", default=False, style=STYLE).ask():
            name = questionary.text("Preset name:", style=STYLE).ask()
            if name and name.strip():
                ensure_scope_dir(root)
                save_preset(root, name.strip(), selected)
                print(f"\n  \033[32m✓ Preset '{name.strip()}' saved.\033[0m\n")

def main():
    import argparse
    parser = argparse.ArgumentParser(prog="scopekit", description="Select project scope before debugging")
    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--list-presets", action="store_true")
    args = parser.parse_args()

    if args.version:
        from . import __version__
        print(f"scopekit {__version__}"); return

    root = Path(args.path).resolve()
    if not root.exists():
        print(f"  Error: '{root}' not found."); return

    if args.list_presets:
        presets = list_presets(root)
        if presets:
            print("\n  Saved presets:")
            for p in presets: print(f"    • {p}")
            print()
        else:
            print("\n  No presets yet.\n")
        return

    run(root)

if __name__ == "__main__":
    main()
EOF

cat > pyproject.toml << 'EOF'
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "scopekit"
version = "0.1.0"
description = "Select project scope before debugging with Claude Code — save tokens, debug faster."
readme = "README.md"
requires-python = ">=3.10"
dependencies = ["questionary>=2.0.0"]

[project.scripts]
scopekit = "scopekit.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["scopekit"]
EOF

echo "✅ All files created"
