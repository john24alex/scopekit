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
    safe_name = name.replace("/", "_").replace("\\", "_").replace("..", "_")
    ensure_scope_dir(root)
    f = root / PRESETS_DIR / f"{safe_name}.json"
    f.write_text(json.dumps({"name": safe_name, "paths": sorted(paths)}, indent=2))

def delete_preset(root, name):
    f = root / PRESETS_DIR / f"{name}.json"
    if f.exists():
        f.unlink()
        return True
    return False
