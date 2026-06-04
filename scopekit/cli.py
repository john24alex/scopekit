import sys
from pathlib import Path

try:
    import questionary
    from questionary import Style
except ImportError:
    print("Run: pip3 install questionary")
    sys.exit(1)

from .tree import (build_tree, flatten_tree, get_project_name, detect_framework,
                   load_scopeignore, get_git_changed_dirs, get_recent_changed_dirs,
                   estimate_tokens)
from .presets import list_presets, load_preset, save_preset, delete_preset, ensure_scope_dir
from .prompt import generate_prompt, copy_to_clipboard
from .selector import run_tree_selector
from .stats import record_session, print_stats
from .init_cmd import run_init
from .web import run_web

STYLE = Style([
    ("qmark",       "fg:#58a6ff bold"),
    ("question",    "fg:#c9d1d9 bold"),
    ("answer",      "fg:#7ee787 bold"),
    ("pointer",     "fg:#58a6ff bold"),
    ("highlighted", "fg:#58a6ff bold"),
    ("selected",    "fg:#7ee787"),
    ("instruction", "fg:#6e7681"),
])

GREEN  = "\033[1;32m"
BLUE   = "\033[1;34m"
DIM    = "\033[2m"
YELLOW = "\033[1;33m"
RED    = "\033[1;31m"
RESET  = "\033[0m"


def _fmt_tokens(n):
    if n >= 1_000_000: return f"~{n/1_000_000:.1f}M"
    if n >= 1_000:     return f"~{n//1000}k"
    return str(n)


def print_header(name, fw):
    print(f"\n  {BLUE}🎯 ScopeKit{RESET}  {DIM}{name} · {fw}{RESET}")
    print(f"  {DIM}Select scope before sending to Claude Code{RESET}\n")


def finish(root, selected, mode, fmt="claude", print_only=False, preset_name=None):
    sel_files, total_files, sel_tok, total_tok = estimate_tokens(root, selected)
    saved = total_tok - sel_tok
    pct   = int((1 - sel_tok / total_tok) * 100) if total_tok else 0

    prompt = generate_prompt(selected, fmt=fmt)

    print(f"\n  {GREEN}✓ Scope set:{RESET}  "
          f"{DIM}{len(selected)} folders · {sel_files} files · "
          f"{_fmt_tokens(sel_tok)} tokens  "
          f"(saved {_fmt_tokens(saved)}, {pct}% less){RESET}")
    for p in sorted(selected):
        print(f"    {GREEN}• {p}/{RESET}")

    if print_only:
        print(f"\n{prompt}\n")
    elif copy_to_clipboard(prompt):
        label = {"cursor": "Cursor rules", "copilot": "Copilot instructions"}.get(fmt, "Prompt")
        print(f"\n  {GREEN}✓ {label} copied to clipboard — paste it before describing the bug{RESET}\n")
    else:
        print(f"\n{prompt}\n")

    record_session(root, selected, sel_files, total_files, sel_tok, total_tok, preset_name)

    if mode == "select" and not print_only:
        if questionary.confirm("Save as preset?", default=False, style=STYLE).ask():
            name = questionary.text("Preset name:", style=STYLE).ask()
            if name and name.strip():
                ensure_scope_dir(root)
                save_preset(root, name.strip(), selected)
                print(f"\n  {GREEN}✓ Preset '{name.strip()}' saved.{RESET}\n")


def run(root, fmt="claude", print_only=False):
    print_header(get_project_name(root), detect_framework(root))
    extra_ignore = load_scopeignore(root)

    git_dirs    = get_git_changed_dirs(root)
    recent_dirs = get_recent_changed_dirs(root, n=3)
    git_hint    = f"  {DIM}({len(git_dirs)} folders){RESET}"    if git_dirs    else f"  {DIM}(no changes){RESET}"
    recent_hint = f"  {DIM}({len(recent_dirs)} folders){RESET}" if recent_dirs else f"  {DIM}(no commits){RESET}"

    mode = questionary.select(
        "Where is the bug?",
        choices=[
            questionary.Choice("🔍  Select specific folders",              value="select"),
            questionary.Choice("⚡  Load a saved preset",                  value="preset"),
            questionary.Choice(f"🔀  Uncommitted changes (git){git_hint}", value="git"),
            questionary.Choice(f"🕐  Recent commits (last 3){recent_hint}", value="recent"),
            questionary.Choice("📁  Entire project",                       value="all"),
        ],
        style=STYLE,
    ).ask()

    if mode is None:
        print("\n  Cancelled.\n"); return

    selected = []
    preset_name = None

    if mode == "select":
        tree = build_tree(root, extra_ignore=extra_ignore)
        if not tree:
            print("  No folders found.\n"); return
        selected = run_tree_selector(tree)
        if selected is None:
            print("\n  Cancelled.\n"); return
        if not selected:
            print("\n  Nothing selected. Cancelled.\n"); return

    elif mode == "preset":
        presets = list_presets(root)
        if not presets:
            print(f"  {DIM}No presets yet. Select folders first and save a preset.{RESET}\n"); return
        chosen = questionary.select("Choose a preset:", choices=presets, style=STYLE).ask()
        if not chosen: return
        selected = load_preset(root, chosen)
        preset_name = chosen
        if not selected:
            print(f"  {RED}Preset is empty or missing.{RESET}\n"); return

    elif mode == "git":
        if not git_dirs:
            print(f"  {DIM}No uncommitted changes found.{RESET}\n"); return
        print(f"\n  {DIM}Uncommitted changes in:{RESET}")
        for d in git_dirs: print(f"    {DIM}• {d}{RESET}")
        if not questionary.confirm("\n  Use these as scope?", default=True, style=STYLE).ask(): return
        selected = git_dirs

    elif mode == "recent":
        if not recent_dirs:
            print(f"  {DIM}No recent commits found.{RESET}\n"); return
        print(f"\n  {DIM}Folders touched in last 3 commits:{RESET}")
        for d in recent_dirs: print(f"    {DIM}• {d}{RESET}")
        if not questionary.confirm("\n  Use these as scope?", default=True, style=STYLE).ask(): return
        selected = recent_dirs

    elif mode == "all":
        tree = build_tree(root, max_depth=1, extra_ignore=extra_ignore)
        selected = flatten_tree(tree)
        if not selected:
            print("  No folders found.\n"); return

    finish(root, selected, mode, fmt=fmt, print_only=print_only, preset_name=preset_name)


def main():
    import argparse
    parser = argparse.ArgumentParser(
        prog="scopekit",
        description="Select project scope before debugging with AI assistants.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
commands:
  scopekit                       interactive TUI
  scopekit init                  create .scopeignore with smart defaults
  scopekit stats                 show token savings and session history
  scopekit --list-presets        list saved presets
  scopekit --show <preset>       show preset folder list
  scopekit --apply <preset>      copy prompt for a preset (non-interactive)
  scopekit --delete <preset>     delete a preset
  scopekit --git                 scope to uncommitted git changes
  scopekit --recent [N]          scope to folders from last N commits (default 3)
  scopekit --format cursor       output as Cursor rules instead of Claude prompt
  scopekit --format copilot      output as GitHub Copilot instructions
  scopekit --print               print to stdout instead of clipboard
  scopekit --version             show version
        """
    )
    parser.add_argument("command",        nargs="?",  default=None,
                        choices=[None, "init", "stats"],
                        metavar="command")
    parser.add_argument("path",           nargs="?",  default=".")
    parser.add_argument("--version",      action="store_true")
    parser.add_argument("--list-presets", action="store_true")
    parser.add_argument("--apply",        metavar="PRESET")
    parser.add_argument("--delete",       metavar="PRESET")
    parser.add_argument("--show",         metavar="PRESET")
    parser.add_argument("--git",          action="store_true")
    parser.add_argument("--recent",       nargs="?", const=3, type=int, metavar="N")
    parser.add_argument("--format",       default="claude",
                        choices=["claude", "cursor", "copilot"])
    parser.add_argument("--print",        action="store_true", dest="print_only")
    parser.add_argument("--web",          action="store_true", help="open browser UI")
    args = parser.parse_args()

    if args.version:
        from . import __version__
        print(f"scopekit {__version__}"); return

    # resolve path — handle `scopekit init` vs `scopekit init /path`
    if args.command in ("init", "stats") and args.path != ".":
        root = Path(args.path).resolve()
    elif args.command in ("init", "stats"):
        root = Path.cwd()
    else:
        root = Path(args.path or ".").resolve()

    if not root.exists():
        print(f"  {RED}Error: '{root}' not found.{RESET}"); return

    # ── subcommands ───────────────────────────────────────────────────────────

    if args.command == "init":
        run_init(root); return

    if args.command == "stats":
        print_stats(root); return

    # ── flag-based non-interactive ────────────────────────────────────────────

    if args.list_presets:
        presets = list_presets(root)
        if presets:
            print("\n  Saved presets:")
            for p in presets: print(f"    • {p}")
            print()
        else:
            print("\n  No presets yet.\n")
        return

    if args.show:
        paths = load_preset(root, args.show)
        if not paths:
            print(f"\n  {RED}Preset '{args.show}' not found.{RESET}\n"); return
        print(f"\n  Preset '{args.show}':")
        for p in paths: print(f"    • {p}/")
        print(); return

    if args.delete:
        if delete_preset(root, args.delete):
            print(f"\n  {GREEN}✓ Preset '{args.delete}' deleted.{RESET}\n")
        else:
            print(f"\n  {RED}Preset '{args.delete}' not found.{RESET}\n")
        return

    if args.apply:
        paths = load_preset(root, args.apply)
        if not paths:
            print(f"\n  {RED}Preset '{args.apply}' not found.{RESET}\n"); return
        prompt = generate_prompt(paths, fmt=args.format)
        if args.print_only:
            print(prompt)
        elif copy_to_clipboard(prompt):
            print(f"\n  {GREEN}✓ Preset '{args.apply}' copied to clipboard.{RESET}\n")
            for p in sorted(paths): print(f"    {GREEN}• {p}/{RESET}")
            print()
        else:
            print(prompt)
        sel_f, tot_f, sel_t, tot_t = estimate_tokens(root, paths)
        record_session(root, paths, sel_f, tot_f, sel_t, tot_t, preset_name=args.apply)
        return

    if args.git:
        dirs = get_git_changed_dirs(root)
        if not dirs:
            print(f"\n  {RED}No uncommitted changes found.{RESET}\n"); return
        _output_dirs(root, dirs, args.format, args.print_only)
        return

    if args.recent is not None:
        n = args.recent or 3
        dirs = get_recent_changed_dirs(root, n)
        if not dirs:
            print(f"\n  {RED}No recent commits found.{RESET}\n"); return
        _output_dirs(root, dirs, args.format, args.print_only)
        return

    if args.web:
        run_web(root); return

    # ── interactive TUI ───────────────────────────────────────────────────────
    run(root, fmt=args.format, print_only=args.print_only)


def _output_dirs(root, dirs, fmt, print_only):
    prompt = generate_prompt(dirs, fmt=fmt)
    sel_f, tot_f, sel_t, tot_t = estimate_tokens(root, dirs)
    saved = tot_t - sel_t
    pct   = int((1 - sel_t / tot_t) * 100) if tot_t else 0
    if print_only:
        print(prompt)
    elif copy_to_clipboard(prompt):
        print(f"\n  {GREEN}✓ Scope ({len(dirs)} folders · saved {_fmt_tokens(saved)}, {pct}% less) copied to clipboard.{RESET}")
        for d in dirs: print(f"    {GREEN}• {d}/{RESET}")
        print()
    else:
        print(prompt)
    record_session(root, dirs, sel_f, tot_f, sel_t, tot_t)


if __name__ == "__main__":
    main()
