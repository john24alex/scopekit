import json
from datetime import datetime
from pathlib import Path

STATS_FILE = ".scope/stats.json"


def _load(root):
    f = root / STATS_FILE
    if not f.exists():
        return {"sessions": 0, "total_folders_scoped": 0,
                "total_folders_available": 0, "tokens_saved": 0,
                "preset_usage": {}, "history": []}
    try:
        return json.loads(f.read_text())
    except Exception:
        return {}


def _save(root, data):
    f = root / STATS_FILE
    f.parent.mkdir(exist_ok=True)
    f.write_text(json.dumps(data, indent=2))


def record_session(root, selected_paths, sel_files, total_files, sel_tokens, total_tokens, preset_name=None):
    data = _load(root)
    data["sessions"] = data.get("sessions", 0) + 1
    data["total_folders_scoped"] = data.get("total_folders_scoped", 0) + len(selected_paths)
    data["total_folders_available"] = data.get("total_folders_available", 0) + total_files
    saved = total_tokens - sel_tokens
    data["tokens_saved"] = data.get("tokens_saved", 0) + max(saved, 0)

    if preset_name:
        pu = data.setdefault("preset_usage", {})
        pu[preset_name] = pu.get(preset_name, 0) + 1

    history = data.setdefault("history", [])
    history.append({
        "date": datetime.now().strftime("%Y-%m-%d"),
        "folders": len(selected_paths),
        "files_scoped": sel_files,
        "files_total": total_files,
        "tokens_saved": max(saved, 0),
    })
    # keep last 100 sessions only
    data["history"] = history[-100:]
    _save(root, data)


def print_stats(root):
    data = _load(root)
    if not data.get("sessions"):
        print("\n  No stats yet — run scopekit in a project first.\n")
        return

    sessions  = data["sessions"]
    saved     = data.get("tokens_saved", 0)
    history   = data.get("history", [])
    preset_usage = data.get("preset_usage", {})

    # avg folders scoped vs available
    avg_scoped = data.get("total_folders_scoped", 0) / sessions
    avg_total  = data.get("total_folders_available", 0) / sessions
    pct_excluded = (1 - avg_scoped / avg_total) * 100 if avg_total else 0

    # sessions this week
    today = datetime.now().strftime("%Y-%m-%d")
    week_sessions = sum(1 for h in history if h.get("date", "") >= today[:8] + "0" * 2)

    GREEN = "\033[1;32m"
    BLUE  = "\033[1;34m"
    DIM   = "\033[2m"
    RESET = "\033[0m"

    print(f"\n  {BLUE}📊 ScopeKit Stats{RESET}\n")
    print(f"  Total sessions       {GREEN}{sessions}{RESET}")
    print(f"  Sessions this week   {GREEN}{week_sessions}{RESET}")
    print(f"  Avg scope            {GREEN}{avg_scoped:.0f} / {avg_total:.0f} folders{RESET}  {DIM}({pct_excluded:.0f}% excluded){RESET}")
    print(f"  Est. tokens saved    {GREEN}{_fmt_tokens(saved)}{RESET}")

    if preset_usage:
        top = sorted(preset_usage.items(), key=lambda x: -x[1])[:5]
        print(f"\n  {DIM}Top presets:{RESET}")
        for name, count in top:
            print(f"    {GREEN}• {name}{RESET}  {DIM}({count}x){RESET}")

    print()


def _fmt_tokens(n):
    if n >= 1_000_000:
        return f"~{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"~{n//1000}k"
    return str(n)
