from __future__ import annotations

import copy
import importlib.util
import io
import json
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "cuelabs-system-design"
SCRIPT = SKILL / "scripts" / "render_design.py"
EXAMPLE = SKILL / "assets" / "example-spec.json"
SPEC = importlib.util.spec_from_file_location("render_design", SCRIPT)
assert SPEC and SPEC.loader
render_design = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = render_design
SPEC.loader.exec_module(render_design)


def load_example() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def copy_data(page: str) -> dict:
    match = re.search(r'<script type="application/json" id="copy-data">(.*?)</script>', page, re.S)
    assert match, "copy data missing"
    return json.loads(match.group(1))


def overview(spec: dict) -> dict:
    return next(s for s in spec["sections"] if s["id"] == "overview")["diagram"]


class RenderDesignTest(unittest.TestCase):
    def test_example_spec_is_checker_clean(self) -> None:
        self.assertEqual(render_design.check_spec(load_example()), [])

    def test_standalone_page_has_every_copy_payload(self) -> None:
        spec = load_example()
        page = render_design.render(spec, "standalone")
        self.assertTrue(page.startswith("<!doctype html>"))
        self.assertIn("<title>Ledgerline System Design</title>", page)
        data = copy_data(page)
        wanted = {s["id"] for s in spec["sections"] if s["type"] in ("diagram", "sequence", "table")}
        self.assertEqual(set(data["xc"]), wanted)
        for key, payload in data["xc"].items():
            clip = json.loads(payload)
            self.assertEqual(clip["type"], "excalidraw/clipboard", key)
            self.assertTrue(clip["elements"], key)
        self.assertEqual(set(data["mm"]), {"overview", "capture"})
        self.assertTrue(data["mm"]["overview"].startswith("flowchart TB"))
        self.assertTrue(data["mm"]["capture"].startswith("sequenceDiagram"))

    def test_every_button_has_a_payload(self) -> None:
        page = render_design.render(load_example(), "standalone")
        data = copy_data(page)
        for kind, key in re.findall(r'data-copy="(xc|mm)" data-key="([^"]+)"', page):
            self.assertIn(key, data[kind])

    def test_artifact_mode_has_no_document_skeleton(self) -> None:
        page = render_design.render(load_example(), "artifact")
        self.assertTrue(page.startswith("<title>"))
        self.assertNotIn("<html", page)
        self.assertNotIn("<body", page)

    def test_theme_overrides_reach_the_tokens(self) -> None:
        spec = load_example()
        spec["theme"] = {"light": {"accent": "#123456"}}
        self.assertIn("--accent: #123456;", render_design.render(spec, "artifact"))

    def test_checker_flags_text_wider_than_its_box(self) -> None:
        spec = load_example()
        node = next(n for n in overview(spec)["nodes"] if n["id"] == "pg")
        node["title"] = "A title far too long for a box this narrow"
        warnings = render_design.check_spec(spec)
        self.assertTrue(any("wider than its box" in w for w in warnings), warnings)

    def test_checker_flags_an_unconnected_box(self) -> None:
        spec = load_example()
        overview(spec)["nodes"].append(
            {"id": "lonely", "kind": "client", "x": 850, "y": 30, "w": 130, "h": 54, "title": "Lonely"})
        warnings = render_design.check_spec(spec)
        self.assertTrue(any("'lonely' has no arrow" in w for w in warnings), warnings)

    def test_checker_flags_an_edge_that_misses_its_node(self) -> None:
        spec = load_example()
        edge = next(e for e in overview(spec)["edges"] if e.get("label") == "owns")
        edge["points"] = [[240, 287], [120, 287]]
        warnings = render_design.check_spec(spec)
        self.assertTrue(any("does not start/end on 'pg'" in w for w in warnings), warnings)

    def test_group_becomes_a_mermaid_subgraph(self) -> None:
        diagram = {
            "width": 600, "height": 300,
            "nodes": [
                {"id": "an", "kind": "group", "x": 20, "y": 20, "w": 560, "h": 200, "title": "api/analytics"},
                {"id": "ex", "kind": "python", "x": 40, "y": 60, "w": 200, "h": 74, "title": "extract pool"},
                {"id": "co", "kind": "python", "x": 300, "y": 60, "w": 200, "h": 74, "title": "compute pool"},
            ],
            "edges": [{"from": "ex", "to": "co", "kind": "kafka", "points": [[240, 97], [298, 97]]}],
        }
        text = render_design.mermaid_flowchart(diagram)
        self.assertIn("subgraph an[api/analytics]", text)
        self.assertIn("ex --> co", text)

    def test_boxes_inside_a_connected_container_count_as_connected(self) -> None:
        diagram = {
            "width": 700, "height": 300,
            "nodes": [
                {"id": "apps", "kind": "client", "x": 20, "y": 20, "w": 400, "h": 200, "title": "Apps"},
                {"id": "web", "kind": "service", "x": 40, "y": 60, "w": 160, "h": 60, "title": "web"},
                {"id": "api", "kind": "service", "x": 500, "y": 80, "w": 160, "h": 60, "title": "api"},
            ],
            "edges": [{"from": "apps", "to": "api", "kind": "request", "points": [[420, 110], [498, 110]]}],
        }
        self.assertEqual(render_design.check_diagram("d", diagram), [])
        svg = render_design.diagram_svg("d", diagram)
        self.assertIn('<text class="lb" x="36" y="38">Apps</text>', svg)
        self.assertIn("subgraph apps[Apps]", render_design.mermaid_flowchart(diagram))

    def test_chip_text_uses_the_small_style(self) -> None:
        svg = "".join(render_design.node_svg(
            {"kind": "chip", "x": 0, "y": 0, "w": 150, "h": 28, "title": "in-memory cache"}))
        self.assertIn('class="st"', svg)
        self.assertNotIn('class="t"', svg)

    def test_cli_strict_check_passes_on_the_example(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = render_design.main([str(EXAMPLE), "--check", "--strict"])
        self.assertEqual(code, 0)
        self.assertIn("0 warning(s)", out.getvalue())

    def test_cli_writes_the_page(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "docs" / "system-design.html"
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                code = render_design.main([str(EXAMPLE), "--out", str(target)])
            self.assertEqual(code, 0)
            self.assertIn("Copy for Excalidraw", target.read_text(encoding="utf-8"))

    def test_strict_mode_fails_on_warnings(self) -> None:
        spec = load_example()
        overview(spec)["nodes"][0]["x"] = 1190
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "spec.json"
            path.write_text(json.dumps(spec), encoding="utf-8")
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                code = render_design.main([str(path), "--check", "--strict"])
        self.assertEqual(code, 1)

    def test_sequence_layout_grows_with_steps(self) -> None:
        seq = copy.deepcopy(next(s for s in load_example()["sections"] if s["id"] == "capture")["sequence"])
        short = render_design.sequence_layout(seq)["height"]
        seq["steps"] += [{"from": "app", "to": "c", "text": "again"}] * 3
        self.assertGreater(render_design.sequence_layout(seq)["height"], short)


if __name__ == "__main__":
    unittest.main()
