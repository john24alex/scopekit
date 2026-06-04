"""
scopekit --web  →  starts a local server and opens the browser UI.
Zero extra dependencies: uses Python's built-in http.server.
"""

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from .tree import build_tree, flatten_tree, load_scopeignore, get_project_name, detect_framework, estimate_tokens
from .presets import list_presets, load_preset, save_preset, ensure_scope_dir
from .prompt import generate_prompt, copy_to_clipboard
from .stats import record_session

PORT = 7777

# ── HTML ──────────────────────────────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ScopeKit</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg:       #0d1117;
    --surface:  #161b22;
    --border:   #30363d;
    --blue:     #58a6ff;
    --green:    #3fb950;
    --green-d:  #238636;
    --text:     #c9d1d9;
    --dim:      #8b949e;
    --sel-bg:   #1f3a2a;
    --hover-bg: #1c2128;
    --red:      #f85149;
  }
  body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", monospace; font-size: 14px; height: 100vh; display: flex; flex-direction: column; }

  /* ── header ── */
  header { background: var(--surface); border-bottom: 1px solid var(--border); padding: 14px 20px; display: flex; align-items: center; gap: 12px; flex-shrink: 0; }
  .logo { color: var(--blue); font-weight: 700; font-size: 16px; }
  .project-badge { background: var(--border); color: var(--dim); border-radius: 20px; padding: 3px 10px; font-size: 12px; }
  .fw-badge { background: #1f2937; color: #60a5fa; border-radius: 20px; padding: 3px 10px; font-size: 12px; border: 1px solid #374151; }
  header .spacer { flex: 1; }
  .stats-pill { background: var(--surface); border: 1px solid var(--border); border-radius: 20px; padding: 4px 12px; font-size: 12px; color: var(--dim); display: flex; gap: 8px; align-items: center; }
  .stats-pill .count { color: var(--green); font-weight: 600; }

  /* ── layout ── */
  .body { display: flex; flex: 1; overflow: hidden; }

  /* ── sidebar ── */
  .sidebar { width: 260px; border-right: 1px solid var(--border); background: var(--surface); display: flex; flex-direction: column; flex-shrink: 0; }
  .sidebar-header { padding: 12px 16px; border-bottom: 1px solid var(--border); font-size: 11px; text-transform: uppercase; letter-spacing: .08em; color: var(--dim); display: flex; justify-content: space-between; align-items: center; }
  .preset-list { flex: 1; overflow-y: auto; padding: 8px 0; }
  .preset-item { display: flex; align-items: center; padding: 7px 16px; cursor: pointer; gap: 8px; transition: background .1s; }
  .preset-item:hover { background: var(--hover-bg); }
  .preset-item.active { background: #1f3a2a; color: var(--green); }
  .preset-item .name { flex: 1; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .preset-item .del { color: var(--dim); font-size: 11px; padding: 2px 5px; border-radius: 4px; opacity: 0; transition: opacity .1s; }
  .preset-item:hover .del { opacity: 1; }
  .preset-item .del:hover { color: var(--red); background: #2d1b1b; }
  .no-presets { padding: 16px; color: var(--dim); font-size: 12px; text-align: center; }
  .sidebar-footer { padding: 10px 12px; border-top: 1px solid var(--border); }
  .save-btn { width: 100%; background: var(--green-d); color: #fff; border: none; border-radius: 6px; padding: 7px; font-size: 13px; cursor: pointer; transition: background .15s; }
  .save-btn:hover { background: #2ea043; }
  .save-btn:disabled { opacity: .4; cursor: default; }

  /* ── tree panel ── */
  .tree-panel { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
  .tree-toolbar { padding: 10px 16px; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
  .search-box { flex: 1; background: var(--bg); border: 1px solid var(--border); border-radius: 6px; padding: 6px 10px; color: var(--text); font-size: 13px; outline: none; }
  .search-box:focus { border-color: var(--blue); }
  .btn-sm { background: var(--surface); border: 1px solid var(--border); color: var(--dim); border-radius: 6px; padding: 5px 10px; font-size: 12px; cursor: pointer; transition: all .1s; white-space: nowrap; }
  .btn-sm:hover { border-color: var(--blue); color: var(--blue); }
  .btn-sm.active { border-color: var(--green); color: var(--green); }
  .tree-scroll { flex: 1; overflow-y: auto; padding: 8px 0; }
  .tree-scroll::-webkit-scrollbar { width: 6px; }
  .tree-scroll::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

  /* ── tree nodes ── */
  .node { user-select: none; }
  .node-row { display: flex; align-items: center; padding: 3px 16px; cursor: pointer; gap: 6px; transition: background .08s; border-radius: 4px; margin: 0 4px; }
  .node-row:hover { background: var(--hover-bg); }
  .node-row.selected { background: var(--sel-bg); }
  .node-row.cursor { outline: 1px solid var(--blue); outline-offset: -1px; }
  .toggle { width: 16px; height: 16px; display: flex; align-items: center; justify-content: center; color: var(--dim); font-size: 10px; flex-shrink: 0; transition: transform .15s; }
  .toggle.open { transform: rotate(90deg); }
  .toggle.empty { opacity: 0; }
  .cb { width: 15px; height: 15px; border: 1.5px solid var(--border); border-radius: 3px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; transition: all .1s; }
  .cb.checked { background: var(--green); border-color: var(--green); }
  .cb.partial { background: #1a3825; border-color: var(--green); }
  .cb svg { display: none; }
  .cb.checked svg { display: block; }
  .node-icon { font-size: 13px; }
  .node-name { flex: 1; font-size: 13px; }
  .node-name.dim { color: var(--dim); }
  .node-count { font-size: 11px; color: var(--dim); }
  .children { display: none; }
  .children.open { display: block; }
  .hidden-node { display: none !important; }

  /* ── right panel ── */
  .right-panel { width: 320px; border-left: 1px solid var(--border); background: var(--surface); display: flex; flex-direction: column; flex-shrink: 0; }
  .right-header { padding: 12px 16px; border-bottom: 1px solid var(--border); font-size: 11px; text-transform: uppercase; letter-spacing: .08em; color: var(--dim); }
  .scope-list { flex: 1; overflow-y: auto; padding: 10px 0; }
  .scope-item { display: flex; align-items: center; padding: 5px 16px; gap: 8px; font-size: 13px; }
  .scope-item .dot { color: var(--green); }
  .scope-item .spath { color: var(--text); }
  .scope-item .rm { color: var(--dim); cursor: pointer; margin-left: auto; font-size: 11px; }
  .scope-item .rm:hover { color: var(--red); }
  .empty-scope { padding: 20px 16px; color: var(--dim); font-size: 12px; text-align: center; line-height: 1.6; }

  .token-bar { padding: 12px 16px; border-top: 1px solid var(--border); }
  .token-label { font-size: 11px; color: var(--dim); text-transform: uppercase; letter-spacing: .06em; margin-bottom: 6px; display: flex; justify-content: space-between; }
  .token-label .saved { color: var(--green); }
  .progress-track { background: var(--bg); border-radius: 4px; height: 6px; overflow: hidden; }
  .progress-fill { height: 100%; background: var(--green); border-radius: 4px; transition: width .3s; }
  .token-nums { margin-top: 6px; font-size: 11px; color: var(--dim); display: flex; justify-content: space-between; }
  .token-nums .sel { color: var(--text); }

  .action-area { padding: 12px 16px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 8px; }
  .fmt-row { display: flex; gap: 6px; }
  .fmt-btn { flex: 1; background: var(--bg); border: 1px solid var(--border); color: var(--dim); border-radius: 6px; padding: 5px; font-size: 11px; cursor: pointer; text-align: center; transition: all .1s; }
  .fmt-btn.active { border-color: var(--blue); color: var(--blue); background: #112035; }
  .copy-btn { background: var(--blue); color: #0d1117; border: none; border-radius: 6px; padding: 10px; font-size: 14px; font-weight: 600; cursor: pointer; transition: all .15s; }
  .copy-btn:hover { background: #79b8ff; }
  .copy-btn:disabled { opacity: .4; cursor: default; }
  .copy-btn.success { background: var(--green); }

  /* ── modal ── */
  .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.6); display: flex; align-items: center; justify-content: center; z-index: 100; display: none; }
  .modal-overlay.open { display: flex; }
  .modal { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 20px; width: 320px; }
  .modal h3 { margin-bottom: 12px; font-size: 15px; }
  .modal input { width: 100%; background: var(--bg); border: 1px solid var(--border); border-radius: 6px; padding: 8px 10px; color: var(--text); font-size: 13px; outline: none; margin-bottom: 12px; }
  .modal input:focus { border-color: var(--blue); }
  .modal-btns { display: flex; gap: 8px; justify-content: flex-end; }
  .modal-btns button { border-radius: 6px; padding: 6px 14px; font-size: 13px; cursor: pointer; border: 1px solid var(--border); background: var(--bg); color: var(--text); }
  .modal-btns .primary { background: var(--green-d); border-color: var(--green-d); color: #fff; }
  .modal-btns .primary:hover { background: #2ea043; }

  /* ── scrollbars ── */
  .preset-list::-webkit-scrollbar, .scope-list::-webkit-scrollbar { width: 4px; }
  .preset-list::-webkit-scrollbar-thumb, .scope-list::-webkit-scrollbar-thumb { background: var(--border); }
</style>
</head>
<body>

<header>
  <span class="logo">🎯 ScopeKit</span>
  <span class="project-badge" id="projectName">loading…</span>
  <span class="fw-badge" id="fwBadge"></span>
  <div class="spacer"></div>
  <div class="stats-pill">
    <span><span class="count" id="selCount">0</span> selected</span>
    <span>·</span>
    <span><span class="count" id="totalCount">0</span> total</span>
  </div>
</header>

<div class="body">

  <!-- presets sidebar -->
  <div class="sidebar">
    <div class="sidebar-header">
      <span>Presets</span>
    </div>
    <div class="preset-list" id="presetList"></div>
    <div class="sidebar-footer">
      <button class="save-btn" id="saveBtn" disabled onclick="openSaveModal()">💾 Save as preset</button>
    </div>
  </div>

  <!-- tree -->
  <div class="tree-panel">
    <div class="tree-toolbar">
      <input class="search-box" id="searchBox" placeholder="🔍  Filter folders…" oninput="filterTree(this.value)">
      <button class="btn-sm" onclick="expandAll()">Expand all</button>
      <button class="btn-sm" onclick="collapseAll()">Collapse</button>
      <button class="btn-sm" onclick="clearAll()">Clear</button>
    </div>
    <div class="tree-scroll" id="treeRoot"></div>
  </div>

  <!-- scope + actions -->
  <div class="right-panel">
    <div class="right-header">Active scope</div>
    <div class="scope-list" id="scopeList">
      <div class="empty-scope">Select folders from the tree<br>to build your debug scope.</div>
    </div>

    <div class="token-bar">
      <div class="token-label">
        <span>Sending to AI</span>
        <span class="saved" id="savedLabel"></span>
      </div>
      <div class="progress-track">
        <div class="progress-fill" id="progressFill" style="width:0%"></div>
      </div>
      <div class="token-nums">
        <span class="sel" id="selTokens">0 tokens · 0 files</span>
        <span id="totalTokens"></span>
      </div>
    </div>

    <div class="action-area">
      <div class="fmt-row">
        <button class="fmt-btn active" data-fmt="claude"  onclick="setFmt('claude')">Claude</button>
        <button class="fmt-btn"        data-fmt="cursor"  onclick="setFmt('cursor')">Cursor</button>
        <button class="fmt-btn"        data-fmt="copilot" onclick="setFmt('copilot')">Copilot</button>
      </div>
      <button class="copy-btn" id="copyBtn" disabled onclick="copyScope()">Copy prompt to clipboard</button>
    </div>
  </div>

</div>

<!-- save modal -->
<div class="modal-overlay" id="modal">
  <div class="modal">
    <h3>Save preset</h3>
    <input id="presetNameInput" placeholder="e.g. auth-flow, coach-bug…" onkeydown="if(event.key==='Enter')savePreset()">
    <div class="modal-btns">
      <button onclick="closeModal()">Cancel</button>
      <button class="primary" onclick="savePreset()">Save</button>
    </div>
  </div>
</div>

<script>
let tree = {};
let selected = new Set();
let fmt = 'claude';
let totalFiles = 0, totalTokens = 0;
let fileCounts = {}; // path → file count (own files only)

const AVG = 150;

// ── boot ────────────────────────────────────────────────────────────────────
async function boot() {
  const [treeRes, presetsRes, infoRes, fileCountsRes] = await Promise.all([
    fetch('/api/tree').then(r => r.json()),
    fetch('/api/presets').then(r => r.json()),
    fetch('/api/info').then(r => r.json()),
    fetch('/api/filecounts').then(r => r.json()),
  ]);
  tree = treeRes;
  fileCounts = fileCountsRes;  // {path: file_count}
  document.getElementById('projectName').textContent = infoRes.name;
  document.getElementById('fwBadge').textContent = infoRes.fw;
  document.getElementById('totalCount').textContent = infoRes.total_folders;
  totalFiles = infoRes.total_files;
  totalTokens = infoRes.total_tokens;
  document.getElementById('totalTokens').textContent = fmtTok(totalTokens) + ' total';
  renderTree(tree, document.getElementById('treeRoot'), '');
  renderPresets(presetsRes);
}

// ── tree rendering ───────────────────────────────────────────────────────────
function renderTree(subtree, container, prefix) {
  for (const [name, children] of Object.entries(subtree)) {
    const path = prefix ? prefix + '/' + name : name;
    const hasChildren = children && Object.keys(children).length > 0;
    const node = document.createElement('div');
    node.className = 'node';
    node.dataset.path = path;

    const row = document.createElement('div');
    row.className = 'node-row';
    row.style.paddingLeft = (16 + prefix.split('/').filter(Boolean).length * 18) + 'px';
    const fc = fileCounts[path] || 0;
    const countBadge = fc > 0 ? `<span class="node-count">${fc} file${fc !== 1 ? 's' : ''}</span>` : '';
    row.innerHTML = `
      <span class="toggle ${hasChildren ? '' : 'empty'}">▶</span>
      <span class="cb" onclick="toggleSel(event,'${path}')">
        <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
          <path d="M1 4L3.5 6.5L9 1" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </span>
      <span class="node-icon">📁</span>
      <span class="node-name">${name}</span>
      ${countBadge}
    `;

    // toggle expand on row click (not checkbox)
    row.addEventListener('click', (e) => {
      if (e.target.closest('.cb')) return;
      if (!hasChildren) { toggleSel(e, path); return; }
      const ch = node.querySelector('.children');
      const tog = row.querySelector('.toggle');
      const open = ch.classList.toggle('open');
      tog.classList.toggle('open', open);
    });

    node.appendChild(row);

    if (hasChildren) {
      const ch = document.createElement('div');
      ch.className = 'children';
      renderTree(children, ch, path);
      node.appendChild(ch);
    }

    container.appendChild(node);
  }
}

function toggleSel(e, path) {
  e.stopPropagation();
  const adding = !selected.has(path);
  // select/deselect subtree
  const paths = allPathsUnder(path);
  paths.forEach(p => adding ? selected.add(p) : selected.delete(p));
  selected.has(path) || adding ? selected.add(path) : selected.delete(path);
  if (adding) selected.add(path);
  else selected.delete(path);
  // also toggle all descendants
  document.querySelectorAll(`[data-path]`).forEach(n => {
    if (n.dataset.path === path || n.dataset.path.startsWith(path + '/')) {
      const cb = n.querySelector(':scope > .node-row .cb');
      if (cb) {
        if (adding) { cb.classList.add('checked'); selected.add(n.dataset.path); }
        else { cb.classList.remove('checked'); selected.delete(n.dataset.path); }
      }
    }
  });
  updateUI();
}

function countFilesUnder(path) {
  // sum fileCounts for path and all its descendants
  return Object.entries(fileCounts)
    .filter(([p]) => p === path || p.startsWith(path + '/'))
    .reduce((s, [, n]) => s + n, 0);
}

function allPathsUnder(path) {
  const results = [];
  document.querySelectorAll('[data-path]').forEach(n => {
    if (n.dataset.path.startsWith(path + '/')) results.push(n.dataset.path);
  });
  return results;
}

// ── selection UI ─────────────────────────────────────────────────────────────
function updateUI() {
  const sel = [...selected];
  // top-level selected only (no duplicates with children)
  const top = sel.filter(p => !sel.some(o => o !== p && p.startsWith(o + '/')));
  document.getElementById('selCount').textContent = top.length;
  document.getElementById('saveBtn').disabled = top.length === 0;
  document.getElementById('copyBtn').disabled = top.length === 0;

  // token math — use real file counts, sum only top-level (children already included)
  const selFiles = top.reduce((sum, p) => sum + countFilesUnder(p), 0);
  const selTok   = selFiles * AVG;
  const pct      = totalTokens ? Math.min(100, (selTok / totalTokens) * 100) : 0;
  const saved    = Math.max(0, totalTokens - selTok);
  document.getElementById('progressFill').style.width = pct + '%';
  const pctUsed = totalTokens ? Math.round((selTok / totalTokens) * 100) : 0;
  const pctExcl = 100 - pctUsed;
  document.getElementById('selTokens').textContent = fmtTok(selTok) + ' · ' + selFiles + ' files  (' + pctUsed + '% of project)';
  document.getElementById('savedLabel').textContent = saved > 0 ? '🛡 ' + pctExcl + '% excluded' : '';

  // scope list
  const scopeList = document.getElementById('scopeList');
  if (top.length === 0) {
    scopeList.innerHTML = '<div class="empty-scope">Select folders from the tree<br>to build your debug scope.</div>';
    return;
  }
  scopeList.innerHTML = top.sort().map(p =>
    `<div class="scope-item">
      <span class="dot">•</span>
      <span class="spath">${p}/</span>
      <span class="rm" onclick="removePath('${p}')">✕</span>
    </div>`
  ).join('');
}

function removePath(path) {
  selected.delete(path);
  allPathsUnder(path).forEach(p => selected.delete(p));
  document.querySelectorAll(`[data-path]`).forEach(n => {
    if (n.dataset.path === path || n.dataset.path.startsWith(path + '/')) {
      const cb = n.querySelector(':scope > .node-row .cb');
      if (cb) cb.classList.remove('checked');
    }
  });
  updateUI();
}

// ── actions ──────────────────────────────────────────────────────────────────
function setFmt(f) {
  fmt = f;
  document.querySelectorAll('.fmt-btn').forEach(b => b.classList.toggle('active', b.dataset.fmt === f));
}

async function copyScope() {
  const sel = [...selected].filter(p => ![...selected].some(o => o !== p && p.startsWith(o + '/')));
  if (!sel.length) return;
  const btn = document.getElementById('copyBtn');
  const res = await fetch('/api/copy', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({paths: sel, fmt})
  }).then(r => r.json());
  btn.textContent = '✓ Copied!';
  btn.classList.add('success');
  setTimeout(() => { btn.textContent = 'Copy prompt to clipboard'; btn.classList.remove('success'); }, 2000);
}

function expandAll() {
  document.querySelectorAll('.children').forEach(c => c.classList.add('open'));
  document.querySelectorAll('.toggle:not(.empty)').forEach(t => t.classList.add('open'));
}
function collapseAll() {
  document.querySelectorAll('.children').forEach(c => c.classList.remove('open'));
  document.querySelectorAll('.toggle').forEach(t => t.classList.remove('open'));
}
function clearAll() {
  selected.clear();
  document.querySelectorAll('.cb').forEach(cb => cb.classList.remove('checked'));
  updateUI();
}

function filterTree(q) {
  const lq = q.toLowerCase();
  document.querySelectorAll('.node').forEach(n => {
    const path = n.dataset.path || '';
    const match = !lq || path.toLowerCase().includes(lq);
    n.classList.toggle('hidden-node', !match);
    if (match && lq) {
      // expand parents
      let parent = n.parentElement?.closest('.node');
      while (parent) {
        parent.querySelector(':scope > .node-row + .children')?.classList.add('open');
        parent.querySelector(':scope > .node-row .toggle')?.classList.add('open');
        parent = parent.parentElement?.closest('.node');
      }
    }
  });
}

// ── presets ──────────────────────────────────────────────────────────────────
function renderPresets(presets) {
  const el = document.getElementById('presetList');
  if (!presets.length) {
    el.innerHTML = '<div class="no-presets">No presets yet.<br>Select folders and save.</div>';
    return;
  }
  el.innerHTML = presets.map(p =>
    `<div class="preset-item" onclick="loadPreset('${p}')">
      <span class="node-icon">⚡</span>
      <span class="name">${p}</span>
      <span class="del" onclick="deletePreset(event,'${p}')">✕</span>
    </div>`
  ).join('');
}

async function loadPreset(name) {
  const paths = await fetch('/api/preset/' + name).then(r => r.json());
  clearAll();
  paths.forEach(path => {
    selected.add(path);
    const node = document.querySelector(`[data-path="${path}"]`);
    if (node) {
      node.querySelector(':scope > .node-row .cb')?.classList.add('checked');
      // expand parents
      let parent = node.parentElement?.closest('.node');
      while (parent) {
        parent.querySelector(':scope > .node-row + .children')?.classList.add('open');
        parent.querySelector(':scope > .node-row .toggle')?.classList.add('open');
        parent = parent.parentElement?.closest('.node');
      }
    }
  });
  document.querySelectorAll('.preset-item').forEach(i => i.classList.toggle('active', i.textContent.trim().startsWith(name)));
  updateUI();
}

async function deletePreset(e, name) {
  e.stopPropagation();
  await fetch('/api/preset/' + name, {method: 'DELETE'});
  const presets = await fetch('/api/presets').then(r => r.json());
  renderPresets(presets);
}

function openSaveModal() {
  document.getElementById('modal').classList.add('open');
  document.getElementById('presetNameInput').value = '';
  setTimeout(() => document.getElementById('presetNameInput').focus(), 50);
}
function closeModal() { document.getElementById('modal').classList.remove('open'); }

async function savePreset() {
  const name = document.getElementById('presetNameInput').value.trim();
  if (!name) return;
  const sel = [...selected].filter(p => ![...selected].some(o => o !== p && p.startsWith(o + '/')));
  await fetch('/api/preset/' + name, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({paths: sel})
  });
  closeModal();
  const presets = await fetch('/api/presets').then(r => r.json());
  renderPresets(presets);
}

function fmtTok(n) {
  if (n >= 1000000) return '~' + (n/1000000).toFixed(1) + 'M';
  if (n >= 1000)    return '~' + Math.round(n/1000) + 'k';
  return String(n);
}

boot();
</script>
</body>
</html>
"""

# ── server ────────────────────────────────────────────────────────────────────

class _Handler(BaseHTTPRequestHandler):
    root = None
    fmt  = "claude"

    def log_message(self, *_):
        pass  # silence request logs

    def _json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _html(self):
        body = HTML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path

        if path == "/" or path == "":
            self._html(); return

        if path == "/api/tree":
            extra  = load_scopeignore(self.root)
            tree   = build_tree(self.root, extra_ignore=extra)
            self._json(tree); return

        if path == "/api/info":
            from .tree import flatten_tree, count_files, AVG_TOKENS_PER_FILE
            extra = load_scopeignore(self.root)
            tree  = build_tree(self.root, extra_ignore=extra)
            all_dirs = flatten_tree(tree)
            total_files = count_files(self.root, all_dirs)
            self._json({
                "name":          get_project_name(self.root),
                "fw":            detect_framework(self.root),
                "total_folders": len(all_dirs),
                "total_files":   total_files,
                "total_tokens":  total_files * AVG_TOKENS_PER_FILE,
            }); return

        if path == "/api/filecounts":
            from .tree import flatten_tree, CODE_EXTENSIONS
            extra    = load_scopeignore(self.root)
            all_dirs = flatten_tree(build_tree(self.root, extra_ignore=extra))
            counts   = {}
            for d in all_dirs:
                dp = self.root / d
                if dp.is_dir():
                    # only direct files in this folder (not recursive) so counts don't overlap
                    counts[d] = sum(
                        1 for f in dp.iterdir()
                        if f.is_file() and f.suffix in CODE_EXTENSIONS
                    )
            self._json(counts); return

        if path == "/api/presets":
            self._json(list_presets(self.root)); return

        if path.startswith("/api/preset/"):
            name = path[len("/api/preset/"):]
            self._json(load_preset(self.root, name)); return

        self.send_response(404); self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = json.loads(self.rfile.read(length)) if length else {}
        path   = urlparse(self.path).path

        if path == "/api/copy":
            paths  = body.get("paths", [])
            fmt    = body.get("fmt", "claude")
            prompt = generate_prompt(paths, fmt=fmt)
            copied = copy_to_clipboard(prompt)
            sel_f, tot_f, sel_t, tot_t = estimate_tokens(self.root, paths)
            record_session(self.root, paths, sel_f, tot_f, sel_t, tot_t)
            self._json({"ok": True, "copied": copied, "prompt": prompt}); return

        if path.startswith("/api/preset/"):
            name  = path[len("/api/preset/"):]
            paths = body.get("paths", [])
            ensure_scope_dir(self.root)
            save_preset(self.root, name, paths)
            self._json({"ok": True}); return

        self.send_response(404); self.end_headers()

    def do_DELETE(self):
        path = urlparse(self.path).path
        if path.startswith("/api/preset/"):
            from .presets import delete_preset
            name = path[len("/api/preset/"):]
            delete_preset(self.root, name)
            self._json({"ok": True}); return
        self.send_response(404); self.end_headers()


def _free_port(port):
    """Kill any process holding the port so we can bind cleanly."""
    import signal, subprocess as sp
    try:
        r = sp.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True)
        for pid in r.stdout.split():
            try:
                import os; os.kill(int(pid), signal.SIGTERM)
            except Exception:
                pass
    except Exception:
        pass


def run_web(root: Path):
    _free_port(PORT)
    _Handler.root = root
    HTTPServer.allow_reuse_address = True
    server = HTTPServer(("127.0.0.1", PORT), _Handler)
    url = f"http://127.0.0.1:{PORT}"
    print(f"\n  🌐  ScopeKit Web UI → {url}")
    print(f"  {chr(27)}[2mCtrl+C to stop{chr(27)}[0m\n")
    threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.\n")
