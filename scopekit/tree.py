import os
import subprocess
from pathlib import Path

DEFAULT_IGNORE = {
    ".git", ".idea", ".vscode", "__pycache__", "node_modules",
    ".dart_tool", ".flutter-plugins", "build", "dist", ".gradle",
    ".cache", "Pods", ".symlinks", "coverage", ".scope",
    "graphify-out", ".pub-cache", ".pub", "vendor",
}

CODE_EXTENSIONS = {
    ".dart", ".js", ".ts", ".jsx", ".tsx", ".py", ".rb", ".go",
    ".rs", ".swift", ".kt", ".java", ".c", ".cpp", ".h", ".cs",
    ".vue", ".svelte", ".html", ".css", ".scss", ".json", ".yaml",
    ".yml", ".md", ".sh", ".env",
}

AVG_TOKENS_PER_FILE = 150


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
        if depth >= max_depth:
            return {}
        result = {}
        try:
            for entry in sorted(path.iterdir()):
                if entry.is_symlink(): continue
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
    if (root / "requirements.txt").exists() or (root / "pyproject.toml").exists(): return "Python"
    return "Unknown"


def count_files(root, paths):
    """Count code files inside the given relative paths."""
    total = 0
    for p in paths:
        d = root / p
        if not d.is_dir():
            continue
        for f in d.rglob("*"):
            if f.is_file() and f.suffix in CODE_EXTENSIONS:
                total += 1
    return total


def estimate_tokens(root, selected_paths):
    """Return (selected_files, total_files, selected_tokens, total_tokens)."""
    all_dirs = flatten_tree(build_tree(root))
    sel   = count_files(root, selected_paths)
    total = count_files(root, all_dirs)
    return sel, total, sel * AVG_TOKENS_PER_FILE, total * AVG_TOKENS_PER_FILE


def get_git_changed_dirs(root):
    """Dirs touched by uncommitted changes + untracked files."""
    try:
        r1 = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=root, capture_output=True, text=True, timeout=5
        )
        r2 = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=root, capture_output=True, text=True, timeout=5
        )
        return _dirs_from_files(r1.stdout.splitlines() + r2.stdout.splitlines())
    except Exception:
        return []


def get_recent_changed_dirs(root, n=3):
    """Dirs touched in the last N commits."""
    try:
        r = subprocess.run(
            ["git", "log", f"-{n}", "--name-only", "--pretty=format:"],
            cwd=root, capture_output=True, text=True, timeout=5
        )
        return _dirs_from_files(r.stdout.splitlines())
    except Exception:
        return []


def _dirs_from_files(files):
    dirs = set()
    for f in files:
        f = f.strip()
        if not f:
            continue
        parts = f.split("/")
        if len(parts) > 1:
            if parts[0] in DEFAULT_IGNORE or parts[0].startswith("."):
                continue
            dirs.add("/".join(parts[:-1]))
    return sorted(dirs)
