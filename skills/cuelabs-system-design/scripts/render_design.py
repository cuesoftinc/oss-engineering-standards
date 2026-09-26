#!/usr/bin/env python3
"""Render a system-design spec (JSON) into a self-contained HTML page.

The page carries SVG diagrams, tables, and a "Copy for Excalidraw" /
"Copy as Mermaid" button under each figure. Dependency-free (stdlib only).

Usage:
    render_design.py SPEC.json --out docs/system-design.html
    render_design.py SPEC.json --out page.html --mode artifact
    render_design.py SPEC.json --check            # lint only, no output

Modes:
    standalone  a full HTML document that opens in any browser (default)
    artifact    page content only (title, fonts, style, body) for hosts that
                wrap pages in their own document skeleton

The spec format is documented in references/page-spec.md.
"""

from __future__ import annotations

import argparse
import html
import json
import random
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# --------------------------------------------------------------------------
# Visual vocabulary
# --------------------------------------------------------------------------

NODE_KINDS = {
    # kind: (svg class, legend label)
    "client": ("edgeb", "client or outside service"),
    "service": ("svc", "Go (CRUD) or Node (gateway)"),
    "python": ("py", "Python (processing)"),
    "function": ("fn", "serverless function"),
    "stock": ("stock", "stock component, no custom code"),
    "store": ("store", "data store"),
    "bus": ("bus", "message queue"),
    "person": ("person", "people"),
    "chip": ("chip", None),
    "chipbad": ("chipbad", None),
    "group": ("group", "one service, several worker pools"),
    "labelbg": ("lblbg", None),
}
EDGE_KINDS = {
    # kind: (svg class, marker, legend label, default layer)
    "request": ("r", "r", "request (HTTPS)", "front"),
    "request-dashed": ("rd", "r", "reply or occasional use", "front"),
    "kafka": ("k", "k", "Kafka event", "front"),
    "storage-write": ("dt", "d", "object storage write", "front"),
    "storage-read": ("dd", "d", "object storage read", "front"),
    "cache": ("redis", "d", "uses the cache", "back"),
    "telemetry": ("tel", "r", "telemetry", "back"),
    "sync": ("s", "s", "synchronous internal call", "front"),
    "main": ("i", "i", "main use", "front"),
    "removed": ("xb", "b", "removed by the redesign", "front"),
    "lifeline": ("life", None, None, "back"),
}
LABEL_KINDS = {
    "muted": "lb", "kafka": "lbk", "storage": "lbd", "removed": "lbr",
    "sync": "lbs", "python": "lbp", "heading": "h", "title": "t", "sub": "st",
}

DEFAULT_THEME = {
    "light": {
        "bg": "#F2F5F4", "surface": "#FFFFFF", "ink": "#0F1B18", "muted": "#56665F",
        "line": "#AFC0BA", "rule": "#D5DFDB", "edge": "#E9EFED",
        "accent": "#00977F", "accent-ink": "#00705F", "accent-soft": "#D3F2EA",
        "store": "#DCE8F8", "store-line": "#3F6FAE", "py": "#FFF6DA", "py-line": "#B26A00",
        "fn": "#EEE7FD", "fn-line": "#6D4FC2", "person": "#FFF1C9",
        "warn": "#8A5200", "ok": "#1E8E4E", "bad": "#C8372D", "bad-soft": "#FBE9E7",
        "on-accent": "#FFFFFF",
    },
    "dark": {
        "bg": "#0B1412", "surface": "#12201C", "ink": "#E4EEEB", "muted": "#93A7A0",
        "line": "#35504A", "rule": "#22342F", "edge": "#10231F",
        "accent": "#00C98E", "accent-ink": "#00E09E", "accent-soft": "#0D3A2F",
        "store": "#15263C", "store-line": "#7AA5DE", "py": "#2B2410", "py-line": "#F2B84B",
        "fn": "#221A38", "fn-line": "#A78BFA", "person": "#3A2F12",
        "warn": "#F2B84B", "ok": "#45CE7E", "bad": "#F06A5F", "bad-soft": "#3A1714",
        "on-accent": "#FFFFFF",
    },
}

# Approximate glyph widths (em) used by the layout checker and Excalidraw.
SANS_EM = 0.52
MONO_EM = 0.6
CLASS_FONT = {  # svg text class -> (size px, em factor)
    "t": (14, 0.56), "st": (12, SANS_EM), "h": (16, SANS_EM),
    "lb": (11, MONO_EM), "lbk": (11, MONO_EM), "lbd": (11, MONO_EM),
    "lbr": (11, MONO_EM), "lbs": (11, MONO_EM), "lbp": (11, MONO_EM),
}


def esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def text_width(text: str, cls: str, size: float | None = None) -> float:
    base, em = CLASS_FONT.get(cls, (12, SANS_EM))
    return len(text) * (size or base) * em


# --------------------------------------------------------------------------
# Diagrams (boxes and arrows at explicit coordinates)
# --------------------------------------------------------------------------

def markers(prefix: str) -> str:
    kinds = {"r": "mk-r", "k": "mk-k", "d": "mk-d", "s": "mk-s", "i": "mk-i", "b": "mk-b"}
    rows = [
        f'<marker id="{prefix}-{m}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        f'markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" class="{c}"/></marker>'
        for m, c in kinds.items()
    ]
    return "<defs>" + "".join(rows) + "</defs>"


UNNESTED = ("chip", "chipbad", "labelbg")


def contains(outer: dict, inner: dict) -> bool:
    return (inner is not outer and inner["x"] >= outer["x"] and inner["y"] >= outer["y"]
            and inner["x"] + inner["w"] <= outer["x"] + outer["w"]
            and inner["y"] + inner["h"] <= outer["y"] + outer["h"])


def containers(nodes: list[dict]) -> list[dict]:
    """Nodes that hold other boxes (not just chips): drawn and checked as containers."""
    return [o for o in nodes if o.get("kind") not in UNNESTED + ("bus",)
            and any(contains(o, i) for i in nodes if i.get("kind") not in UNNESTED)]


def node_svg(n: dict, is_container: bool = False) -> list[str]:
    kind = n.get("kind", "service")
    cls = NODE_KINDS[kind][0]
    x, y, w, h = n["x"], n["y"], n["w"], n["h"]
    rx = 8 if kind in ("person", "group") else 6
    out = [f'<rect class="{cls}" x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="{rx}"/>']
    title = n.get("title", "")
    lines = n.get("lines", [])
    size = n.get("font_size")
    style = f' style="font-size:{size}px"' if size else ""
    if is_container and kind != "group":
        if title:
            out.append(f'<text class="lb" x="{x + 16:g}" y="{y + 18:g}">{esc(title)}</text>')
        return out
    if kind in ("chip", "chipbad"):
        out.append(f'<text class="st" x="{x + w / 2:g}" y="{y + h / 2 + 4:g}" text-anchor="middle">{esc(title)}</text>')
        return out
    if kind == "group":
        pos = n.get("label_pos", "bottom-right")
        lx = x + w - 10 if pos.endswith("right") else x + 12
        ly = y + h - 8 if pos.startswith("bottom") else y + 18
        anchor = ' text-anchor="end"' if pos.endswith("right") else ""
        if title:
            out.append(f'<text class="lbp" x="{lx:g}" y="{ly:g}"{anchor}>{esc(title)}</text>')
        return out
    if kind == "bus":
        if title and w >= 120:
            out.append(f'<text class="t" x="{x + 16:g}" y="{y + h / 2 + 5:g}">{esc(title)}</text>')
        return out
    if kind == "labelbg":
        return out
    cx = x + w / 2
    if n.get("align") == "top":
        out.append(f'<text class="t" x="{cx:g}" y="{y + 22:g}" text-anchor="middle"{style}>{esc(title)}</text>')
        return out
    rows = ([("t", title)] if title else []) + [("st", line) for line in lines]
    step = 18
    first = y + h / 2 - (len(rows) - 1) * step / 2 + 5
    for i, (c, text) in enumerate(rows):
        s = style if c == "t" else ""
        out.append(f'<text class="{c}" x="{cx:g}" y="{first + i * step:g}" text-anchor="middle"{s}>{esc(text)}</text>')
    return out


def edge_svg(e: dict, prefix: str) -> str:
    cls, mk, _, _ = EDGE_KINDS[e.get("kind", "request")]
    pts = e["points"]
    d = "M" + " L".join(f"{p[0]:g} {p[1]:g}" for p in pts)
    arrow = e.get("arrow", "none" if e.get("kind") in ("cache", "lifeline") else "end")
    attrs = ""
    if mk and arrow in ("end", "both"):
        attrs += f' marker-end="url(#{prefix}-{mk})"'
    if mk and arrow in ("start", "both"):
        attrs += f' marker-start="url(#{prefix}-{mk})"'
    return f'<path class="{cls}" d="{d}"{attrs}/>'


def label_svg(lbl: dict) -> str:
    cls = LABEL_KINDS.get(lbl.get("kind", "muted"), "lb")
    anchor = lbl.get("anchor", "start")
    a = "" if anchor == "start" else f' text-anchor="{anchor}"'
    return f'<text class="{cls}" x="{lbl["x"]:g}" y="{lbl["y"]:g}"{a}>{esc(lbl["text"])}</text>'


def diagram_svg(key: str, d: dict) -> str:
    prefix = re.sub(r"[^a-z0-9]", "", key.lower())[:6] or "d"
    parts = [f'<svg data-xc="{esc(key)}" viewBox="0 0 {d["width"]} {d["height"]}" role="img" aria-label="{esc(d.get("aria", ""))}">',
             markers(prefix)]
    edges = d.get("edges", [])
    back = [e for e in edges if e.get("layer", EDGE_KINDS[e.get("kind", "request")][3]) == "back"]
    front = [e for e in edges if e not in back]
    parts += [edge_svg(e, prefix) for e in back]
    nodes = d.get("nodes", [])
    boxes = containers(nodes)
    for n in sorted(nodes, key=lambda n: 0 if (n.get("kind") in ("group", "labelbg") or n in boxes) else 1):
        parts += node_svg(n, n in boxes)
    parts += [edge_svg(e, prefix) for e in front]
    parts += [label_svg(lbl) for lbl in d.get("labels", [])]
    parts.append("</svg>")
    return "\n".join(parts)


# --------------------------------------------------------------------------
# Sequence diagrams (lanes and steps, laid out automatically)
# --------------------------------------------------------------------------

SEQ_EDGE = {"request": ("r", "r", "lb"), "reply": ("rd", "r", "lb"), "kafka": ("k", "k", "lbk"),
            "storage-write": ("dt", "d", "lbd"), "storage-read": ("dd", "d", "lbd"),
            "sync": ("s", "s", "lbs"), "removed": ("xb", "b", "lbr")}


def sequence_layout(s: dict) -> dict:
    """Turn lanes + steps into explicit coordinates (also used by the checker)."""
    width = s.get("width", 1200)
    lanes = s["lanes"]
    if all("x" in lane for lane in lanes):
        xs = [lane["x"] for lane in lanes]
    else:
        gap = (width - 200) / max(1, len(lanes) - 1)
        xs = [100 + i * gap for i in range(len(lanes))]
    X = {lane["id"]: x for lane, x in zip(lanes, xs)}
    y = 100
    items = []
    for st in s["steps"]:
        if st.get("gap"):
            y += st["gap"]
            continue
        if "note" in st:
            end = st.get("side") == "left"
            x = X[st["at"]] + (-8 if end else 8)
            items.append({"type": "note", "x": x, "y": y, "text": st["note"],
                          "anchor": "end" if end else "start", "kind": st.get("kind", "muted")})
            y += 26
        else:
            x1, x2 = X[st["from"]], X[st["to"]]
            items.append({"type": "msg", "x1": x1, "x2": x2, "y": y, "text": st.get("text", ""),
                          "kind": st.get("kind", "request")})
            y += 40
    bottom = y + 10
    height = s.get("height") or bottom + (50 if s.get("footer") else 20)
    return {"width": width, "height": height, "X": X, "xs": xs, "items": items, "bottom": bottom}


def sequence_svg(key: str, s: dict) -> str:
    L = sequence_layout(s)
    prefix = re.sub(r"[^a-z0-9]", "", key.lower())[:6] or "s"
    out = [f'<svg data-xc="{esc(key)}" viewBox="0 0 {L["width"]:g} {L["height"]:g}" role="img" aria-label="{esc(s.get("aria", ""))}">',
           markers(prefix)]
    lane_w = s.get("lane_width", 160)
    for x in L["xs"]:
        out.append(f'<path class="life" d="M{x:g} 64 L{x:g} {L["bottom"]:g}"/>')
    for lane, x in zip(s["lanes"], L["xs"]):
        cls = NODE_KINDS[lane.get("kind", "service")][0]
        out.append(f'<rect class="{cls}" x="{x - lane_w / 2:g}" y="20" width="{lane_w}" height="44" rx="6"/>')
        out.append(f'<text class="t" x="{x:g}" y="40" text-anchor="middle">{esc(lane["title"])}</text>')
        if lane.get("sub"):
            out.append(f'<text class="st" x="{x:g}" y="56" text-anchor="middle">{esc(lane["sub"])}</text>')
    for it in L["items"]:
        if it["type"] == "note":
            a = ' text-anchor="end"' if it["anchor"] == "end" else ""
            cls = LABEL_KINDS.get(it["kind"], "lb")
            out.append(f'<text class="{cls}" x="{it["x"]:g}" y="{it["y"] + 4:g}"{a}>{esc(it["text"])}</text>')
            continue
        cls, mk, lcls = SEQ_EDGE[it["kind"]]
        x1, x2, y = it["x1"], it["x2"], it["y"]
        x2e = x2 - 2 if x2 > x1 else x2 + 2
        out.append(f'<path class="{cls}" d="M{x1:g} {y:g} L{x2e:g} {y:g}" marker-end="url(#{prefix}-{mk})"/>')
        out.append(f'<text class="{lcls}" x="{(x1 + x2) / 2:g}" y="{y - 6:g}" text-anchor="middle">{esc(it["text"])}</text>')
    if s.get("footer"):
        out.append(f'<text class="st" x="20" y="{L["height"] - 16:g}">{esc(s["footer"])}</text>')
    out.append("</svg>")
    return "\n".join(out)


# --------------------------------------------------------------------------
# Mermaid (generated from the spec so the two never disagree)
# --------------------------------------------------------------------------

def _mm(text: str) -> str:
    return re.sub(r'["|<>{}\[\]()#;]', " ", str(text)).replace("&", "and").strip()


def mermaid_flowchart(d: dict) -> str:
    nodes = {n["id"]: n for n in d.get("nodes", []) if "id" in n}
    groups = containers(list(nodes.values()))

    def inside(inner, outer):
        return contains(outer, inner)

    chips = {}
    for n in nodes.values():
        if n.get("kind") in ("chip", "chipbad"):
            parent = next((p for p in nodes.values() if p.get("kind") not in ("group", "chip", "chipbad") and inside(n, p)), None)
            if parent:
                chips.setdefault(parent["id"], []).append(n.get("title", ""))

    def shape(n):
        text = _mm(" - ".join([n.get("title", "")] + n.get("lines", []) + chips.get(n["id"], [])))
        k = n.get("kind")
        if k == "store":
            return f"{n['id']}[({text})]"
        if k == "bus":
            return f"{n['id']}[[{text}]]"
        if k == "person":
            return f"{n['id']}([{text}])"
        return f"{n['id']}[{text}]"

    out = [f"flowchart {d.get('direction', 'TB')}"]
    grouped = set()
    for g in groups:
        members = [n for n in nodes.values() if n.get("kind") not in UNNESTED and n not in groups and inside(n, g)]
        if not members:
            continue
        out.append(f"    subgraph {g['id']}[{_mm(g.get('title', g['id']))}]")
        for m in members:
            out.append(f"        {shape(m)}")
            grouped.add(m["id"])
        out.append("    end")
    for n in nodes.values():
        if n["id"] not in grouped and n.get("kind") not in UNNESTED and n not in groups:
            out.append(f"    {shape(n)}")
    for e in d.get("edges", []):
        if not e.get("from") or not e.get("to"):
            continue
        kind = e.get("kind", "request")
        dashed = kind in ("request-dashed", "storage-read", "cache", "telemetry", "sync")
        arrow = e.get("arrow", "none" if kind == "cache" else "end")
        body = "-.-" if dashed else "--"
        if arrow == "none":
            link = "-.-" if dashed else "---"
        elif arrow == "both":
            link = "<-.->" if dashed else "<-->"
        else:
            link = body + ">" if not dashed else "-.->"
        a, b = (e["to"], e["from"]) if arrow == "start" else (e["from"], e["to"])
        label = f"|{_mm(e['label'])}|" if e.get("label") else ""
        out.append(f"    {a} {link}{label} {b}")
    return "\n".join(out) + "\n"


def mermaid_sequence(s: dict) -> str:
    out = ["sequenceDiagram"]
    for lane in s["lanes"]:
        title = _mm(lane["title"] + (f" - {lane['sub']}" if lane.get("sub") else ""))
        out.append(f"    participant {lane['id']} as {title}")
    for st in s["steps"]:
        if st.get("gap"):
            continue
        if "note" in st:
            out.append(f"    Note over {st['at']}: {_mm(st['note'])}")
        else:
            arrow = "-->>" if st.get("kind") == "reply" else "->>"
            out.append(f"    {st['from']}{arrow}{st['to']}: {_mm(st.get('text', ''))}")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# Excalidraw clipboard (converted from the rendered SVG and tables)
# --------------------------------------------------------------------------

XC_RECT = {
    "svc": ("#1e1e1e", "#ffffff", "solid", 1), "edgeb": ("#868e96", "#ffffff", "dashed", 1),
    "store": ("#1971c2", "#d0ebff", "solid", 2), "bus": ("#0c8599", "#c3fae8", "solid", 2),
    "py": ("#e8590c", "#fff3bf", "solid", 1), "fn": ("#6741d9", "#e5dbff", "solid", 1),
    "stock": ("#868e96", "#f1f3f5", "dotted", 1), "person": ("#1e1e1e", "#ffec99", "solid", 1),
    "chip": ("#adb5bd", "#f1f3f5", "solid", 1), "chipbad": ("#e03131", "#ffe3e3", "solid", 1),
    "group": ("#e8590c", "transparent", "dashed", 1), "lblbg": ("transparent", "#ffffff", "solid", 1),
}
XC_PATH = {
    "r": ("#868e96", "solid", 1), "rd": ("#868e96", "dashed", 1), "k": ("#0c8599", "solid", 2),
    "dt": ("#1971c2", "solid", 2), "dd": ("#1971c2", "dashed", 2), "i": ("#1e1e1e", "solid", 2),
    "xb": ("#e03131", "solid", 2), "redis": ("#1971c2", "dotted", 2), "tel": ("#868e96", "dotted", 1),
    "s": ("#e8590c", "dashed", 2), "life": ("#ced4da", "dashed", 1),
}
XC_TEXT = {
    "t": ("#1e1e1e", 14), "st": ("#495057", 12), "lb": ("#495057", 11), "lbk": ("#0c8599", 11),
    "lbd": ("#1971c2", 11), "lbr": ("#e03131", 11), "lbs": ("#e8590c", 11), "lbp": ("#e8590c", 11),
    "h": ("#1e1e1e", 16),
}


class Excalidraw:
    def __init__(self, seed: int) -> None:
        self.rand = random.Random(seed)
        self.n = 0

    def base(self, kind, x, y, w, h, stroke="#1e1e1e", bg="transparent", style="solid", sw=1):
        self.n += 1
        return {
            "id": f"{kind[:2]}{self.n}", "type": kind, "x": x, "y": y, "width": w, "height": h,
            "angle": 0, "strokeColor": stroke, "backgroundColor": bg, "fillStyle": "solid",
            "strokeWidth": sw, "strokeStyle": style, "roughness": 1, "opacity": 100,
            "groupIds": [], "frameId": None, "roundness": None,
            "seed": self.rand.randint(1, 2**31 - 1), "version": 1,
            "versionNonce": self.rand.randint(1, 2**31 - 1), "isDeleted": False,
            "boundElements": [], "updated": 1, "link": None, "locked": False,
        }

    def text(self, x, y, s, size, color, align="left", container=None, w=None, h=None):
        lines = s.split("\n")
        tw = w if w is not None else max(len(line) for line in lines) * size * SANS_EM
        th = h if h is not None else len(lines) * size * 1.25
        el = self.base("text", x, y, tw, th, stroke=color)
        el.update({"text": s, "originalText": s, "fontSize": size, "fontFamily": 2,
                   "textAlign": align, "verticalAlign": "middle" if container else "top",
                   "containerId": container, "lineHeight": 1.25, "autoResize": True})
        return el

    def from_svg(self, svg: str) -> list[dict]:
        svg = re.sub(r"<defs>.*?</defs>", "", svg, flags=re.S)
        root = ET.fromstring(svg)
        rects, texts, paths = [], [], []
        for el in root:
            cls = el.get("class", "")
            if el.tag == "rect":
                rects.append(dict(x=float(el.get("x")), y=float(el.get("y")), w=float(el.get("width")),
                                  h=float(el.get("height")), cls=cls))
            elif el.tag == "text":
                size = XC_TEXT.get(cls, ("#1e1e1e", 12))[1]
                m = re.search(r"font-size:(\d+)px", el.get("style", ""))
                if m:
                    size = int(m.group(1))
                texts.append(dict(x=float(el.get("x")), y=float(el.get("y")), s="".join(el.itertext()),
                                  cls=cls, anchor=el.get("text-anchor", "start"), size=size))
            elif el.tag == "path":
                pts = [(float(a), float(b)) for a, b in re.findall(r"[ML]\s*([\d.]+)\s+([\d.]+)", el.get("d"))]
                paths.append(dict(pts=pts, cls=cls, end="marker-end" in el.attrib, start="marker-start" in el.attrib))

        def inside(r, o):
            return (r is not o and o["x"] >= r["x"] and o["y"] >= r["y"]
                    and o["x"] + o["w"] <= r["x"] + r["w"] and o["y"] + o["h"] <= r["y"] + r["h"])

        out, bound = [], {}
        for r in rects:
            if r["cls"] in ("group", "lblbg") or any(inside(r, o) for o in rects):
                continue
            cx = r["x"] + r["w"] / 2
            mine = [t for t in texts if t["anchor"] == "middle" and abs(t["x"] - cx) < 2
                    and r["x"] <= t["x"] <= r["x"] + r["w"] and r["y"] <= t["y"] <= r["y"] + r["h"]]
            if mine:
                bound[id(r)] = mine
                for t in mine:
                    t["used"] = True
        for r in rects:
            stroke, bg, style, sw = XC_RECT.get(r["cls"], XC_RECT["svc"])
            el = self.base("rectangle", r["x"], r["y"], r["w"], r["h"], stroke, bg, style, sw)
            if r["cls"] != "lblbg":
                el["roundness"] = {"type": 3}
            out.append(el)
            if id(r) in bound:
                lines = sorted(bound[id(r)], key=lambda t: t["y"])
                s = "\n".join(t["s"] for t in lines)
                size = 13 if (r["h"] <= 46 and len(lines) > 1) else 14
                tw = max(len(line) for line in s.split("\n")) * size * SANS_EM
                th = len(lines) * size * 1.25
                te = self.text(r["x"] + (r["w"] - tw) / 2, r["y"] + (r["h"] - th) / 2, s, size,
                               "#1e1e1e", "center", container=el["id"], w=tw, h=th)
                el["boundElements"].append({"type": "text", "id": te["id"]})
                out.append(te)
        for p in paths:
            stroke, style, sw = XC_PATH.get(p["cls"], XC_PATH["r"])
            x0, y0 = p["pts"][0]
            rel = [[x - x0, y - y0] for x, y in p["pts"]]
            xs, ys = [a for a, _ in rel], [b for _, b in rel]
            kind = "arrow" if (p["end"] or p["start"]) else "line"
            el = self.base(kind, x0, y0, max(xs) - min(xs), max(ys) - min(ys), stroke, "transparent", style, sw)
            el.update({"points": rel, "lastCommittedPoint": None, "startBinding": None, "endBinding": None,
                       "startArrowhead": "arrow" if p["start"] else None,
                       "endArrowhead": "arrow" if p["end"] else None})
            if kind == "arrow":
                el["elbowed"] = False
            out.append(el)
        for t in texts:
            if t.get("used"):
                continue
            color, _ = XC_TEXT.get(t["cls"], ("#1e1e1e", 12))
            w = len(t["s"]) * t["size"] * SANS_EM
            x = t["x"] - (w / 2 if t["anchor"] == "middle" else w if t["anchor"] == "end" else 0)
            align = {"middle": "center", "end": "right"}.get(t["anchor"], "left")
            out.append(self.text(x, t["y"] - t["size"], t["s"], t["size"], color, align, w=w))
        return out

    def from_table(self, columns: list[str], rows: list[list[str]]) -> list[dict]:
        table = [columns] + rows
        ncol = len(columns)
        maxc = [min(max(len(r[i]) for r in table), 56) for i in range(ncol)]
        widths = [max(80, c * 7.4 + 24) for c in maxc]
        out, y = [], 0
        for ri, row in enumerate(table):
            wrapped = [_wrap(row[i], maxc[i]) for i in range(ncol)]
            h = max(w.count("\n") + 1 for w in wrapped) * 17.5 + 16
            x = 0
            for i in range(ncol):
                el = self.base("rectangle", x, y, widths[i], h, "#868e96", "#e9ecef" if ri == 0 else "#ffffff")
                lines = wrapped[i].count("\n") + 1
                te = self.text(x + 10, y + (h - lines * 17.5) / 2, wrapped[i], 14, "#1e1e1e", "left",
                               container=el["id"], w=widths[i] - 20, h=lines * 17.5)
                el["boundElements"].append({"type": "text", "id": te["id"]})
                out += [el, te]
                x += widths[i]
            y += h
        return out


def _wrap(s: str, n: int) -> str:
    words, lines, cur = s.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > n:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return "\n".join(lines)


def plain(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", str(fragment))).strip()


def clipboard(elements: list[dict]) -> str:
    return json.dumps({"type": "excalidraw/clipboard", "elements": elements, "files": {}})


# --------------------------------------------------------------------------
# Layout checker
# --------------------------------------------------------------------------

def _overlap(a, b, pad=0.0):
    return not (a[2] <= b[0] + pad or b[2] <= a[0] + pad or a[3] <= b[1] + pad or b[3] <= a[1] + pad)


def _label_box(lbl: dict, cls: str) -> tuple:
    w = text_width(lbl["text"], cls)
    size = CLASS_FONT.get(cls, (12, SANS_EM))[0]
    x = lbl["x"] - (w / 2 if lbl.get("anchor") == "middle" else w if lbl.get("anchor") == "end" else 0)
    return (x, lbl["y"] - size * 0.9, x + w, lbl["y"] + size * 0.3)


def _near_border(pt, n, tol=7.0) -> bool:
    x, y = pt
    x0, y0, x1, y1 = n["x"], n["y"], n["x"] + n["w"], n["y"] + n["h"]
    inside_x = x0 - tol <= x <= x1 + tol
    inside_y = y0 - tol <= y <= y1 + tol
    on_v = inside_y and (abs(x - x0) <= tol or abs(x - x1) <= tol)
    on_h = inside_x and (abs(y - y0) <= tol or abs(y - y1) <= tol)
    return on_v or on_h


def _touches(points, n) -> bool:
    """True when any segment of the polyline meets the node's border."""
    for (ax, ay), (bx, by) in zip(points, points[1:]):
        steps = max(1, int(max(abs(bx - ax), abs(by - ay)) / 4))
        for i in range(steps + 1):
            p = (ax + (bx - ax) * i / steps, ay + (by - ay) * i / steps)
            if _near_border(p, n, 3.0):
                return True
    return False


def check_diagram(key: str, d: dict) -> list[str]:
    warn: list[str] = []
    W, H = d["width"], d["height"]
    nodes = d.get("nodes", [])
    by_id = {n["id"]: n for n in nodes if "id" in n}
    holders = containers(nodes)
    solid = [n for n in nodes if n.get("kind") not in ("group", "labelbg") and n not in holders]
    for n in nodes:
        name = n.get("id") or n.get("title", "?")
        if n["x"] < 0 or n["y"] < 0 or n["x"] + n["w"] > W or n["y"] + n["h"] > H:
            warn.append(f"{key}: node {name!r} extends outside the {W}x{H} canvas")
        if n.get("kind") in ("group", "labelbg", "bus") or n in holders:
            continue
        size = n.get("font_size")
        tcls = "st" if n.get("kind") in ("chip", "chipbad") else "t"
        if n.get("title") and text_width(n["title"], tcls, size) > n["w"] - 12:
            warn.append(f"{key}: title of {name!r} is wider than its box ({n['w']}px)")
        for line in n.get("lines", []):
            if text_width(line, "st") > n["w"] - 12:
                warn.append(f"{key}: line {line!r} in {name!r} is wider than its box")
        rows = (1 if n.get("title") else 0) + len(n.get("lines", []))
        if n.get("align") != "top" and rows * 18 + 8 > n["h"]:
            warn.append(f"{key}: {name!r} has {rows} text rows but is only {n['h']}px tall")
    for e in d.get("edges", []):
        for p in e["points"]:
            if not (0 <= p[0] <= W and 0 <= p[1] <= H):
                warn.append(f"{key}: an edge point {p} is outside the canvas")
        for end, pt in (("from", e["points"][0]), ("to", e["points"][-1])):
            if end == "to" and e.get("join"):
                continue  # a branch that merges into another line, not into the node
            ref = e.get(end)
            if ref and ref in by_id and not _near_border(pt, by_id[ref]):
                warn.append(f"{key}: edge {e.get('from')}->{e.get('to')} does not start/end on {ref!r}'s border")
            if ref and ref not in by_id:
                warn.append(f"{key}: edge refers to unknown node {ref!r}")
    boxes = []
    for lbl in d.get("labels", []):
        cls = LABEL_KINDS.get(lbl.get("kind", "muted"), "lb")
        b = _label_box(lbl, cls)
        if b[0] < 0 or b[2] > W or b[1] < 0 or b[3] > H:
            warn.append(f"{key}: label {lbl['text']!r} runs outside the canvas")
        for n in solid:
            if _overlap(b, (n["x"], n["y"], n["x"] + n["w"], n["y"] + n["h"])):
                warn.append(f"{key}: label {lbl['text']!r} overlaps node {n.get('id') or n.get('title')!r}")
                break
        for other, ob in boxes:
            if _overlap(b, ob, 1):
                warn.append(f"{key}: labels {lbl['text']!r} and {other!r} overlap")
        boxes.append((lbl["text"], b))
    def connected(n) -> bool:
        if any(_touches(e["points"], n) for e in d.get("edges", [])):
            return True
        return any(contains(o, n) and connected(o) for o in holders)

    connectable = [n for n in nodes if n.get("kind") not in UNNESTED + ("group",) and not n.get("standalone")]
    for n in connectable:
        if not connected(n):
            warn.append(f"{key}: node {n.get('id') or n.get('title')!r} has no arrow or line; connect it or set \"standalone\": true")
    if not any(e.get("from") and e.get("to") for e in d.get("edges", [])) and "mermaid" not in d:
        warn.append(f"{key}: no edge names its from/to nodes, so the Mermaid copy will be empty")
    kinds = {e.get("kind", "request") for e in d.get("edges", [])} - {"lifeline"}
    missing = [k for k in kinds if EDGE_KINDS[k][2] is None]
    if missing:
        warn.append(f"{key}: edge kinds without a legend entry: {missing}")
    return warn


def check_sequence(key: str, s: dict) -> list[str]:
    warn: list[str] = []
    L = sequence_layout(s)
    lane_ids = set(L["X"])
    for st in s["steps"]:
        for ref in (st.get("from"), st.get("to"), st.get("at")):
            if ref and ref not in lane_ids:
                warn.append(f"{key}: step refers to unknown lane {ref!r}")
    for it in L["items"]:
        if it["type"] == "msg":
            span = abs(it["x2"] - it["x1"])
            if text_width(it["text"], "lb") > span + 40:
                warn.append(f"{key}: message {it['text']!r} is much wider than its arrow ({span:.0f}px)")
        else:
            w = text_width(it["text"], "lb")
            if (it["anchor"] == "start" and it["x"] + w > L["width"]) or (it["anchor"] == "end" and it["x"] - w < 0):
                warn.append(f"{key}: note {it['text']!r} runs outside the canvas")
    lane_w = s.get("lane_width", 160)
    for lane in s["lanes"]:
        if text_width(lane["title"], "t") > lane_w - 10:
            warn.append(f"{key}: lane title {lane['title']!r} is wider than its box")
    return warn


def check_spec(spec: dict) -> list[str]:
    warn: list[str] = []
    for key in ("title", "sections"):
        if key not in spec:
            warn.append(f"spec is missing {key!r}")
    title = spec.get("title", "")
    if re.search(r"[:—–]\s", title):
        warn.append("title reads like a caption; keep it a short name (put the explanation in 'lead')")
    ids = set()
    for sec in spec.get("sections", []):
        sid = sec.get("id")
        if sid in ids:
            warn.append(f"duplicate section id {sid!r}")
        ids.add(sid)
        t = sec.get("type")
        if t == "diagram":
            warn += check_diagram(sid, sec["diagram"])
        elif t == "sequence":
            warn += check_sequence(sid, sec["sequence"])
        elif t == "table":
            width = len(sec["columns"])
            for i, row in enumerate(sec["rows"]):
                if len(row) != width:
                    warn.append(f"{sid}: row {i + 1} has {len(row)} cells, expected {width}")
        if t in ("diagram", "sequence") and not sec.get("caption"):
            warn.append(f"{sid}: add a caption that opens with a bold one-line takeaway")
    return warn


# --------------------------------------------------------------------------
# Page assembly
# --------------------------------------------------------------------------

CSS = """
  :root {TOKENS_LIGHT}
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {TOKENS_DARK}
  }
  :root[data-theme="dark"] {TOKENS_DARK}
  body {
    background: var(--bg); color: var(--ink); margin: 0;
    font-family: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
    font-size: 15px; line-height: 1.55;
    padding-inline: 16px; padding-block: 32px 56px;
  }
  .wrap { max-width: 1180px; margin: 0 auto; display: grid; gap: 40px; }
  header { display: grid; gap: 10px; max-width: 74ch; }
  header::before { content: ""; display: block; width: 72px; height: 4px; border-radius: 2px; background: var(--accent); }
  .eyebrow { font-family: "IBM Plex Mono", ui-monospace, Consolas, monospace; font-size: 12px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); }
  h1, h2 { font-family: "IBM Plex Sans Condensed", "IBM Plex Sans", "Arial Narrow", sans-serif; font-weight: 600; text-wrap: balance; margin: 0; line-height: 1.15; }
  h1 { font-size: clamp(30px, 5vw, 44px); }
  h2 { font-size: 24px; }
  p { margin: 0; max-width: 70ch; }
  .lead { font-size: 17px; }
  code, .mono { font-family: "IBM Plex Mono", ui-monospace, Consolas, monospace; font-size: 0.9em; }
  code { background: var(--edge); padding: 1px 5px; border-radius: 4px; }
  .status { display: inline-flex; width: fit-content; font-family: "IBM Plex Mono", ui-monospace, Consolas, monospace; font-size: 12px; border: 1px solid var(--warn); color: var(--warn); border-radius: 999px; padding: 2px 10px; }
  section { display: grid; gap: 14px; }
  section > p { color: var(--muted); }
  figure { margin: 0; display: grid; gap: 12px; }
  .canvas { background: var(--surface); border: 1px solid var(--rule); border-radius: 10px; overflow-x: auto; padding: 12px; }
  .canvas svg { display: block; width: 100%; min-width: 940px; height: auto; color: var(--ink); }
  figcaption { color: var(--muted); max-width: 80ch; font-size: 14px; }
  figcaption strong { color: var(--ink); font-weight: 600; }
  .legend { display: flex; flex-wrap: wrap; gap: 8px 22px; font-size: 13px; color: var(--muted); }
  .legend span { display: inline-flex; align-items: center; gap: 8px; }
  .sw { width: 28px; height: 0; border-top: 2px solid var(--muted); display: inline-block; }
  .sw.k { border-color: var(--accent); }
  .sw.dt { border-color: var(--store-line); }
  .sw.dd { border-color: var(--store-line); border-top-style: dashed; }
  .sw.redis { border-color: var(--store-line); border-top-style: dotted; }
  .sw.tel { border-top-style: dotted; }
  .sw.rd { border-top-style: dashed; }
  .sw.s { border-color: var(--warn); border-top-style: dashed; }
  .sw.i { border-color: var(--ink); }
  .sw.xb { border-color: var(--bad); }
  .sw.box { width: 16px; height: 12px; border-radius: 3px; border-top-width: 1px; }
  .sw.box.edgeb { background: var(--surface); border: 1px dashed var(--muted); }
  .sw.box.svc { background: var(--surface); border: 1px solid var(--ink); }
  .sw.box.py { background: var(--py); border: 1px solid var(--py-line); }
  .sw.box.fn { background: var(--fn); border: 1px solid var(--fn-line); }
  .sw.box.stock { background: var(--edge); border: 1px dashed var(--muted); }
  .sw.box.bus { background: var(--accent-soft); border: 1px solid var(--accent); }
  .sw.box.store { background: var(--store); border: 2px solid var(--store-line); }
  .sw.box.person { background: var(--person); border: 1px solid var(--ink); }
  .sw.box.group { background: transparent; border: 1px dashed var(--py-line); }
  .rules { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; }
  .rule { background: var(--surface); border: 1px solid var(--rule); border-radius: 8px; padding: 14px 16px; display: grid; gap: 4px; align-content: start; }
  .rule b { font-weight: 600; }
  .rule span { color: var(--muted); font-size: 14px; }
  .table-wrap { overflow-x: auto; border: 1px solid var(--rule); border-radius: 10px; background: var(--surface); }
  table { border-collapse: collapse; width: 100%; min-width: 720px; font-size: 14px; }
  th, td { text-align: left; padding: 10px 14px; border-bottom: 1px solid var(--rule); vertical-align: top; }
  th { font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); font-weight: 500; }
  tr:last-child td { border-bottom: 0; }
  td:first-child { font-family: "IBM Plex Mono", ui-monospace, Consolas, monospace; font-size: 13px; white-space: nowrap; }
  td.kafka { background: var(--accent-soft); }
  td.http { background: var(--edge); }
  td.store { background: var(--store); }
  td.sync { background: var(--py); }
  td.num { font-variant-numeric: tabular-nums; }
  .star { color: var(--accent-ink); font-weight: 600; }
  ol.questions { margin: 0; padding-left: 22px; display: grid; gap: 8px; max-width: 80ch; }
  ol.questions b { font-weight: 600; }
  ol.questions span { color: var(--muted); }
  footer { color: var(--muted); font-size: 13px; border-top: 1px solid var(--rule); padding-top: 16px; }
  .howto { background: var(--surface); border: 1px solid var(--rule); border-radius: 10px; padding: 16px 18px; display: grid; gap: 10px; }
  .howto h2 { font-size: 18px; }
  .howto ol { margin: 0; padding-left: 20px; display: grid; gap: 4px; max-width: 80ch; }
  .howto p { color: var(--muted); font-size: 14px; }
  .tools { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 10px; }
  .btn { font: inherit; font-size: 14px; font-weight: 500; cursor: pointer; border-radius: 6px; padding: 7px 14px; border: 1px solid var(--accent); background: var(--accent); color: var(--on-accent); }
  .btn.alt { background: transparent; color: var(--accent-ink); }
  .btn:hover { filter: brightness(1.08); }
  .btn:focus-visible { outline: 2px solid var(--ink); outline-offset: 2px; }
  .copied { font-size: 13px; color: var(--ok); min-height: 1em; }
  .fallback { width: 100%; height: 120px; font-family: "IBM Plex Mono", ui-monospace, Consolas, monospace; font-size: 12px; background: var(--edge); color: var(--ink); border: 1px solid var(--rule); border-radius: 6px; padding: 8px; }
  svg text { font-family: "IBM Plex Sans", system-ui, sans-serif; fill: var(--ink); }
  svg .t { font-size: 14px; font-weight: 600; }
  svg .st { font-size: 12px; fill: var(--muted); }
  svg .h { font-family: "IBM Plex Sans Condensed", "IBM Plex Sans", sans-serif; font-size: 16px; font-weight: 600; }
  svg .lb, svg .lbk, svg .lbd, svg .lbr, svg .lbs, svg .lbp { font-family: "IBM Plex Mono", ui-monospace, Consolas, monospace; font-size: 11px; fill: var(--muted); }
  svg .lbk { fill: var(--accent-ink); }
  svg .lbd { fill: var(--store-line); }
  svg .lbr { fill: var(--bad); }
  svg .lbs { fill: var(--warn); }
  svg .lbp { fill: var(--py-line); font-weight: 500; }
  svg .svc { fill: var(--surface); stroke: var(--ink); stroke-width: 1.2; }
  svg .edgeb { fill: var(--surface); stroke: var(--muted); stroke-width: 1.2; stroke-dasharray: 5 4; }
  svg .store { fill: var(--store); stroke: var(--store-line); stroke-width: 1.8; }
  svg .bus { fill: var(--accent-soft); stroke: var(--accent); stroke-width: 1.5; }
  svg .py { fill: var(--py); stroke: var(--py-line); stroke-width: 1.4; }
  svg .fn { fill: var(--fn); stroke: var(--fn-line); stroke-width: 1.4; }
  svg .stock { fill: var(--edge); stroke: var(--muted); stroke-width: 1.2; stroke-dasharray: 2 3; }
  svg .person { fill: var(--person); stroke: var(--ink); stroke-width: 1.4; }
  svg .chip { fill: var(--edge); stroke: var(--line); stroke-width: 1; }
  svg .chipbad { fill: var(--bad-soft); stroke: var(--bad); stroke-width: 1; }
  svg .group { fill: none; stroke: var(--py-line); stroke-width: 1.4; stroke-dasharray: 6 4; }
  svg .lblbg { fill: var(--surface); }
  svg .r { stroke: var(--muted); stroke-width: 1.5; fill: none; }
  svg .rd { stroke: var(--muted); stroke-width: 1.5; fill: none; stroke-dasharray: 5 4; }
  svg .k { stroke: var(--accent); stroke-width: 2; fill: none; }
  svg .dt { stroke: var(--store-line); stroke-width: 2; fill: none; }
  svg .dd { stroke: var(--store-line); stroke-width: 1.6; fill: none; stroke-dasharray: 5 4; }
  svg .s { stroke: var(--warn); stroke-width: 1.8; fill: none; stroke-dasharray: 6 4; }
  svg .i { stroke: var(--ink); stroke-width: 2; fill: none; }
  svg .xb { stroke: var(--bad); stroke-width: 1.5; fill: none; }
  svg .redis { stroke: var(--store-line); stroke-width: 1.6; fill: none; stroke-dasharray: 2 4; }
  svg .tel { stroke: var(--muted); stroke-width: 1.5; fill: none; stroke-dasharray: 2 4; }
  svg .life { stroke: var(--line); stroke-width: 1; fill: none; stroke-dasharray: 3 4; }
  svg .mk-r { fill: var(--muted); }
  svg .mk-k { fill: var(--accent); }
  svg .mk-d { fill: var(--store-line); }
  svg .mk-s { fill: var(--warn); }
  svg .mk-i { fill: var(--ink); }
  svg .mk-b { fill: var(--bad); }
  @media (max-width: 600px) { body { font-size: 14px; padding-block: 24px 40px; } .lead { font-size: 16px; } }
  @media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
"""

SCRIPT = """
(function () {
  var data = JSON.parse(document.getElementById("copy-data").textContent);
  function fallback(btn, text) {
    var tools = btn.parentElement;
    var ta = tools.nextElementSibling && tools.nextElementSibling.classList.contains("fallback") ? tools.nextElementSibling : null;
    if (!ta) {
      ta = document.createElement("textarea");
      ta.className = "fallback"; ta.readOnly = true;
      ta.setAttribute("aria-label", "Text to copy");
      tools.insertAdjacentElement("afterend", ta);
    }
    ta.value = text; ta.focus(); ta.select();
    tools.querySelector(".copied").textContent = "Copy blocked here: the text is selected below, press Ctrl+C.";
  }
  document.querySelectorAll("[data-copy]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var text = data[btn.dataset.copy][btn.dataset.key];
      var note = btn.parentElement.querySelector(".copied");
      var msg = btn.dataset.copy === "xc" ? "Copied. In Excalidraw press Esc, then V, then Ctrl+V." : "Copied. Paste into Mermaid to Excalidraw.";
      try {
        navigator.clipboard.writeText(text).then(function () { note.textContent = msg; }, function () { fallback(btn, text); });
      } catch (e) { fallback(btn, text); }
    });
  });
})();
"""

HOWTO = """<div class="howto" id="excalidraw">
    <h2>Copy these into Excalidraw</h2>
    <ol>
      <li>Click <b>Copy for Excalidraw</b> under a diagram or a table.</li>
      <li>Open <span class="mono">excalidraw.com</span>. Press <b>Esc</b>, then <b>V</b> to pick the selection tool. Don't click or double-click the canvas; that can open a text box.</li>
      <li>Press <b>Ctrl+V</b> (<b>&#8984;V</b> on Mac). The diagram arrives as shapes you can move and edit.</li>
      <li>If you get one long line of text instead, a text box was open. Undo with Ctrl+Z, press Esc, then paste again.</li>
    </ol>
    <p>Prefer Excalidraw to lay it out itself? Use <b>Copy as Mermaid</b>, then in Excalidraw open <b>&#8943; More tools &#8594; Mermaid to Excalidraw</b>, paste, and insert.</p>
  </div>"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500'
         '&amp;family=IBM+Plex+Sans+Condensed:wght@600&amp;family=IBM+Plex+Sans:wght@400;500;600&amp;display=swap">')


def tokens(values: dict, dark: bool) -> str:
    body = " ".join(f"--{k}: {v};" for k, v in values.items())
    return "{ " + ("color-scheme: dark; " if dark else "") + body + " }"


def tools_html(key: str, mermaid: bool) -> str:
    alt = (f'\n        <button class="btn alt" type="button" data-copy="mm" data-key="{esc(key)}">Copy as Mermaid</button>'
           if mermaid else "")
    return (f'<div class="tools">\n        <button class="btn" type="button" data-copy="xc" data-key="{esc(key)}">Copy for Excalidraw</button>'
            f'{alt}\n        <span class="copied" role="status" aria-live="polite"></span>\n      </div>')


def legend_html(d: dict) -> str:
    items = []
    overrides = d.get("legend_labels", {})
    used_edges = {e.get("kind", "request") for e in d.get("edges", [])}
    used_nodes = {n.get("kind", "service") for n in d.get("nodes", [])}
    for k, (cls, _, label, _) in EDGE_KINDS.items():
        if label and k in used_edges:
            items.append(f'<span><i class="sw {cls}"></i>{esc(overrides.get(k, label))}</span>')
    for k, (cls, label) in NODE_KINDS.items():
        if label and k in used_nodes:
            items.append(f'<span><i class="sw box {cls}"></i>{esc(overrides.get(k, label))}</span>')
    return '<div class="legend" aria-hidden="true">\n      ' + "\n      ".join(items) + "\n    </div>"


def cell(value) -> tuple[str, str]:
    if isinstance(value, dict):
        cls = value.get("class", "")
        return value.get("html", esc(value.get("text", ""))), (f' class="{esc(cls)}"' if cls else "")
    return str(value), ""


def render(spec: dict, mode: str) -> str:
    theme = {"light": dict(DEFAULT_THEME["light"]), "dark": dict(DEFAULT_THEME["dark"])}
    for side in ("light", "dark"):
        theme[side].update(spec.get("theme", {}).get(side, {}))
    css = CSS.replace("{TOKENS_LIGHT}", tokens(theme["light"], False)).replace("{TOKENS_DARK}", tokens(theme["dark"], True))
    xc = Excalidraw(seed=7)
    copy = {"xc": {}, "mm": {}}
    body = ['<div class="wrap">', "  <header>"]
    if spec.get("eyebrow"):
        body.append(f'    <div class="eyebrow">{esc(spec["eyebrow"])}</div>')
    body.append(f'    <h1>{esc(spec["title"])}</h1>')
    if spec.get("lead"):
        body.append(f'    <p class="lead">{spec["lead"]}</p>')
    if spec.get("status"):
        body.append(f'    <span class="status">{esc(spec["status"])}</span>')
    body.append("  </header>")
    body.append("  " + HOWTO)
    for sec in spec["sections"]:
        sid, t = sec["id"], sec["type"]
        body.append(f'  <section aria-labelledby="{esc(sid)}-h">')
        body.append(f'    <h2 id="{esc(sid)}-h">{esc(sec["title"])}</h2>')
        if sec.get("intro"):
            body.append(f"    <p>{sec['intro']}</p>")
        if t in ("diagram", "sequence"):
            if t == "diagram":
                d = sec["diagram"]
                if sec.get("legend"):
                    body.append("    " + legend_html(d))
                svg = diagram_svg(sid, d)
                mm = d.get("mermaid") or mermaid_flowchart(d)
            else:
                svg = sequence_svg(sid, sec["sequence"])
                mm = sec["sequence"].get("mermaid") or mermaid_sequence(sec["sequence"])
            copy["xc"][sid] = clipboard(xc.from_svg(svg))
            has_mm = bool(mm.strip().count("\n"))
            if has_mm:
                copy["mm"][sid] = mm
            body.append('    <figure>\n      <div class="canvas">\n' + svg + "\n      </div>")
            body.append("      " + tools_html(sid, has_mm))
            if sec.get("caption"):
                body.append(f"      <figcaption>{sec['caption']}</figcaption>")
            body.append("    </figure>")
        elif t == "table":
            head = "".join(f"<th>{esc(c)}</th>" for c in sec["columns"])
            rows, plain_rows = [], []
            for r in sec["rows"]:
                cells = [cell(v) for v in r]
                rows.append("<tr>" + "".join(f"<td{a}>{h}</td>" for h, a in cells) + "</tr>")
                plain_rows.append([plain(h) for h, _ in cells])
            body.append('    <div class="table-wrap">\n      <table>\n        <thead><tr>' + head + "</tr></thead>\n        <tbody>\n          "
                        + "\n          ".join(rows) + "\n        </tbody>\n      </table>\n    </div>")
            copy["xc"][sid] = clipboard(xc.from_table(sec["columns"], plain_rows))
            body.append("    " + tools_html(sid, False))
        elif t == "rules":
            items = "".join(f'<div class="rule"><b>{r["title"]}</b><span>{r["text"]}</span></div>' for r in sec["items"])
            body.append(f'    <div class="rules">{items}</div>')
        elif t == "list":
            items = "".join(f"<li><b>{i['title']}</b> <span>{i['text']}</span></li>" for i in sec["items"])
            body.append(f'    <ol class="questions">{items}</ol>')
        elif t == "text":
            body.append(f"    <p>{sec['html']}</p>")
        body.append("  </section>")
    if spec.get("footer"):
        body.append(f'  <footer>{spec["footer"]}</footer>')
    body.append("</div>")
    payload = json.dumps(copy).replace("</", "<\\/")
    content = (f"<title>{esc(spec['title'])}</title>\n{FONTS}\n<style>{css}</style>\n\n" + "\n".join(body)
               + f'\n\n<script type="application/json" id="copy-data">{payload}</script>\n<script>{SCRIPT}</script>\n')
    if mode == "artifact":
        return content
    head, rest = content.split("\n<style>", 1)
    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            + head + "\n<style>" + rest.replace("</style>\n\n", "</style>\n</head>\n<body>\n", 1) + "</body>\n</html>\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--mode", choices=("standalone", "artifact"), default="standalone")
    ap.add_argument("--check", action="store_true", help="lint the spec only")
    ap.add_argument("--strict", action="store_true", help="exit non-zero when the checker warns")
    args = ap.parse_args(argv)
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    warnings = check_spec(spec)
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    if args.check:
        print(f"{len(warnings)} warning(s)")
        return 1 if (warnings and args.strict) else 0
    if not args.out:
        ap.error("--out is required unless --check is given")
    page = render(spec, args.mode)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(page, encoding="utf-8")
    print(f"wrote {args.out} ({len(page) // 1024} KB, {len(warnings)} warning(s))")
    return 1 if (warnings and args.strict) else 0


if __name__ == "__main__":
    raise SystemExit(main())
