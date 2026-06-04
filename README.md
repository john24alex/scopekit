<p align="center">
  <img src="docs/logo.svg" alt="ScopeKit" width="380">
</p>

<p align="center">
  <strong>Stop paying for AI to read your entire codebase. Show it exactly where the bug is.</strong>
</p>

<p align="center">
  <a href="https://john24alex.github.io/scopekit">🌐 Website</a> ·
  <a href="https://pypi.org/project/scopekit">📦 PyPI</a> ·
  <a href="https://github.com/john24alex/scopekit/issues">🐛 Issues</a>
</p>

<p align="center">
  <img src="https://img.shields.io/pypi/v/scopekit?color=58a6ff&label=pypi" alt="PyPI">
  <img src="https://img.shields.io/pypi/pyversions/scopekit?color=3fb950" alt="Python">
  <img src="https://img.shields.io/github/license/john24alex/scopekit?color=8b949e" alt="License">
</p>

Most token-saving tools (Graphify, etc.) build knowledge graphs with LLM API calls and vector databases. ScopeKit takes the opposite approach — **zero tokens, zero APIs, zero complexity.** Just a folder tree built from the filesystem and a focused prompt.

The insight: you already know roughly where the bug is. ScopeKit makes that knowledge explicit so the AI doesn't waste credits exploring irrelevant parts of your project.

---

## The problem

When debugging, AI assistants read the *entire* project to understand context — even if the bug is in one small feature. On large projects (1000+ files) this burns through credits in under an hour.

## The fix

```bash
scopekit
```

An interactive TUI shows your project tree. Select 2–3 folders in under 10 seconds. A scoped prompt is copied to your clipboard — paste it before describing the bug.

```
Only look at these folders:
  •src/payments/
  • src/core/database/
  • src/orders/processor/


If you find references to code OUTSIDE this scope that are relevant
to the bug, let me know before expanding.

Do not read files outside the selected scope without asking me first.
```

Claude (or Cursor, or Copilot) reads only what matters. The bug gets fixed faster. Your credits last longer.

---

## Install

```bash
# macOS (recommended)
pipx install scopekit

# or with pip
pip install scopekit

# or with uv
uv tool install scopekit
```

## Usage

```bash
# Run in your project root
scopekit

# Specify a path
scopekit /path/to/project

# List saved presets
scopekit --list-presets

# Show version
scopekit --version
```

## How it works

```
 ┌────────────────────────────────────────┐
 │  🎯 ScopeKit  my-app · Flutter/Dart   │
 │                                        │
 │  Where is the bug?                     │
 │  > 🔍  Select specific folders         │
 │    ⚡  Load a saved preset             │
 │    📁  Entire project                  │
 └────────────────────────────────────────┘
```

1. **Select specific folders** — checkbox tree, indent shows depth
2. **Load a saved preset** — named scopes your team committed to the repo
3. **Entire project** — top-level folders only, still reduces noise

After selection the prompt is generated and copied to clipboard. Paste it into Claude Code, Cursor, or any AI assistant before describing the bug.

---

## Features

**Auto-detects project type** — Flutter, Node.js, Python, Rust, Go

**Presets** — save common debug scopes by name, stored as plain JSON in `.scope/presets/`. Commit them so the whole team benefits.

```bash
# First time: select folders → "Save as preset?" → name it "auth-flow"
# Next time:
scopekit   # choose "Load a saved preset" → "auth-flow"
```

**.scopeignore** — list folders to always exclude (one per line):

```
tmp
fixtures
legacy
generated
```

**No API keys. No LLM calls. No tokens consumed — ever.** Works with any AI assistant, any language.

---

## Philosophy

ScopeKit is intentionally minimal. The only dependency is `questionary` for the TUI. The filesystem is the data source. The developer is the intelligence. The AI is the tool — and tools work better when you give them clear constraints.

---

## Roadmap

- `/scope` slash command for Claude Code
- Auto-suggest scope from `git diff --name-only` (scope to recently changed files)
- VS Code extension
- Browser UI for teams

---

## License

MIT
