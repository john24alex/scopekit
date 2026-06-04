from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Window, HSplit, FloatContainer, Float
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style


class Node:
    def __init__(self, path, children=None):
        self.path = path
        self.name = path.split("/")[-1]
        self.depth = path.count("/")
        self.children = children or []
        self.expanded = False
        self.selected = False

    @property
    def has_children(self):
        return bool(self.children)


def _build_nodes(tree, prefix=""):
    nodes = []
    for key, subtree in tree.items():
        full = f"{prefix}/{key}" if prefix else key
        children = _build_nodes(subtree, full) if subtree else []
        nodes.append(Node(full, children))
    return nodes


def _visible(nodes):
    result = []
    for n in nodes:
        result.append(n)
        if n.expanded and n.children:
            result.extend(_visible(n.children))
    return result


def _select_subtree(node, value):
    node.selected = value
    for child in node.children:
        _select_subtree(child, value)


def _collect_selected(nodes):
    result = []
    for n in nodes:
        if n.selected:
            result.append(n.path)
        result.extend(_collect_selected(n.children))
    return result


def run_tree_selector(tree):
    """
    Collapsible tree selector. Returns list of selected paths, or None if cancelled.

      ↑ / ↓     navigate
      → / l     expand folder
      ← / h     collapse folder  (or jump to parent)
      Space     select / deselect  (propagates to all children)
      a         toggle select-all visible
      Enter     confirm
      q / Esc   cancel
    """
    roots = _build_nodes(tree)
    if not roots:
        return []

    cursor = [0]   # mutable so closures can write to it

    # ── render ────────────────────────────────────────────────────────────────

    def render_body():
        visible = _visible(roots)
        lines = []
        for i, node in enumerate(visible):
            is_cur = i == cursor[0]
            indent = "  " * node.depth
            arrow  = ("▼ " if node.expanded else "▶ ") if node.has_children else "  "
            check  = "[✓] " if node.selected else "[ ] "
            text   = f"{indent}{arrow}{check}{node.name}\n"

            if is_cur and node.selected:
                lines.append(("class:cursor-sel", text))
            elif is_cur:
                lines.append(("class:cursor", text))
            elif node.selected:
                lines.append(("class:selected", text))
            elif node.has_children:
                lines.append(("class:folder", text))
            else:
                lines.append(("class:leaf", text))
        return lines

    def render_footer():
        visible = _visible(roots)
        n_sel = len(_collect_selected(roots))
        sel_str = f"  {n_sel} selected" if n_sel else "  nothing selected"
        return [
            ("class:footer-count", sel_str),
            ("class:footer", "   ·   ↑↓ move  Space select  → expand  ← collapse  a all  Enter confirm  q quit\n"),
        ]

    body_ctrl   = FormattedTextControl(render_body,   focusable=True)
    footer_ctrl = FormattedTextControl(render_footer)

    header = Window(
        FormattedTextControl(lambda: [("class:header", "  📁  Select folders  "), ("class:hint", "(→ expand  Space select  multiple allowed)\n")]),
        height=1,
    )
    body   = Window(content=body_ctrl)
    footer = Window(content=footer_ctrl, height=1)

    layout = Layout(HSplit([header, body, footer]))

    # ── key bindings ──────────────────────────────────────────────────────────

    kb = KeyBindings()
    result = [None]

    @kb.add("up")
    def _(event):
        if cursor[0] > 0:
            cursor[0] -= 1
        event.app.invalidate()

    @kb.add("down")
    def _(event):
        if cursor[0] < len(_visible(roots)) - 1:
            cursor[0] += 1
        event.app.invalidate()

    @kb.add("right")
    @kb.add("l")
    def _(event):
        node = _visible(roots)[cursor[0]]
        if node.has_children:
            node.expanded = True
        event.app.invalidate()

    @kb.add("left")
    @kb.add("h")
    def _(event):
        visible = _visible(roots)
        node = visible[cursor[0]]
        if node.expanded:
            node.expanded = False
        elif node.depth > 0:
            parent_path = "/".join(node.path.split("/")[:-1])
            for j, n in enumerate(visible):
                if n.path == parent_path:
                    cursor[0] = j
                    break
        event.app.invalidate()

    @kb.add(" ")
    def _(event):
        visible = _visible(roots)
        node = visible[cursor[0]]
        _select_subtree(node, not node.selected)
        if cursor[0] < len(_visible(roots)) - 1:
            cursor[0] += 1
        event.app.invalidate()

    @kb.add("a")
    def _(event):
        visible = _visible(roots)
        all_sel = all(n.selected for n in visible)
        for n in visible:
            _select_subtree(n, not all_sel)
        event.app.invalidate()

    @kb.add("enter")
    def _(event):
        result[0] = _collect_selected(roots)
        event.app.exit()

    @kb.add("q")
    @kb.add("escape")
    def _(event):
        result[0] = None
        event.app.exit()

    # ── style ─────────────────────────────────────────────────────────────────

    style = Style.from_dict({
        "cursor":       "bg:#1c3a5e fg:#58a6ff bold",
        "cursor-sel":   "bg:#1c3a5e fg:#7ee787 bold",
        "selected":     "fg:#7ee787",
        "folder":       "fg:#c9d1d9",
        "leaf":         "fg:#8b949e",
        "header":       "fg:#58a6ff bold",
        "hint":         "fg:#6e7681",
        "footer":       "fg:#6e7681",
        "footer-count": "fg:#7ee787 bold",
    })

    Application(
        layout=layout,
        key_bindings=kb,
        style=style,
        full_screen=False,
        mouse_support=False,
        refresh_interval=None,
    ).run()

    return result[0]
