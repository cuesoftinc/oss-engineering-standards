#!/usr/bin/env python3
"""Validate the local Agent Skills catalog without third-party dependencies."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
EVALS = ROOT / "evals" / "trigger-cases.json"
LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")

# The skills are product-agnostic: a product appears only as the provider of a
# shared ecosystem service, in that table's rows. Rules carry no dated history.
PRODUCT_NAMES = re.compile(r"\b(apparule|expendit|upstat|irealty|getpp)\b", re.I)
SHARED_SERVICES = (
    SKILLS / "cuelabs-engineering-standards" / "references" / "organization-policy.md"
)
ISO_DATE = re.compile(r"\b20\d\d-\d\d-\d\d\b")


def frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        raise ValueError("missing YAML frontmatter")
    closing = text.find("\n---\n", 4)
    if closing < 0:
        raise ValueError("unterminated YAML frontmatter")
    values: dict[str, str] = {}
    current: str | None = None
    for raw in text[4:closing].splitlines():
        if raw.startswith((" ", "\t")) and current:
            values[current] = f"{values[current]} {raw.strip()}".strip()
            continue
        if ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        current = key.strip()
        values[current] = value.strip().strip("\"'")
    return values


def validate_skill(path: Path, cases: dict[str, list[dict[str, str]]]) -> list[str]:
    errors: list[str] = []
    skill_file = path / "SKILL.md"
    if not skill_file.is_file():
        return [f"{path}: missing SKILL.md"]
    text = skill_file.read_text()
    try:
        metadata = frontmatter(text)
    except ValueError as error:
        return [f"{skill_file}: {error}"]

    if metadata.get("name") != path.name:
        errors.append(
            f"{skill_file}: name {metadata.get('name')!r} does not match {path.name!r}"
        )
    if not metadata.get("description"):
        errors.append(f"{skill_file}: description is required")
    unexpected = sorted(set(metadata) - {"name", "description"})
    if unexpected:
        errors.append(f"{skill_file}: unexpected frontmatter fields: {unexpected}")
    body_lines = text.split("\n---\n", 1)[-1].count("\n") + 1
    if body_lines > 500:
        errors.append(f"{skill_file}: body has {body_lines} lines; maximum is 500")
    if "TODO" in text:
        errors.append(f"{skill_file}: unresolved TODO")

    metadata_file = path / "agents" / "openai.yaml"
    if not metadata_file.is_file():
        errors.append(f"{path}: missing agents/openai.yaml")
    elif f"${path.name}" not in metadata_file.read_text():
        errors.append(f"{metadata_file}: default prompt must mention ${path.name}")

    for target in LINK.findall(text):
        if "://" in target or target.startswith("#"):
            continue
        clean = target.split("#", 1)[0]
        if clean and not (path / clean).exists():
            errors.append(f"{skill_file}: broken local link {target!r}")

    skill_cases = cases.get(path.name, [])
    expectations = {case.get("expect") for case in skill_cases}
    if len(skill_cases) < 5:
        errors.append(f"{path}: expected at least 5 trigger evaluation cases")
    for required in ("trigger", "do-not-trigger", "ambiguous"):
        if required not in expectations:
            errors.append(f"{path}: missing {required!r} evaluation case")
    return errors


def validate_markdown_links(path: Path) -> list[str]:
    errors: list[str] = []
    for target in LINK.findall(path.read_text()):
        if (
            "://" in target
            or target.startswith(("#", "mailto:"))
            or target.startswith("$")
        ):
            continue
        clean = target.split("#", 1)[0]
        if clean and not (path.parent / clean).exists():
            errors.append(f"{path}: broken local link {target!r}")
    return errors


def validate_generic_content(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for number, line in enumerate(text.splitlines(), start=1):
        match = PRODUCT_NAMES.search(line)
        if match and not (path == SHARED_SERVICES and line.startswith("|")):
            errors.append(
                f"{path}:{number}: product name {match.group(0)!r}; state the "
                "rule generically or record the value in the product's "
                "docs/decisions.md"
            )
        if path.suffix == ".md" and ISO_DATE.search(line):
            errors.append(
                f"{path}:{number}: dated history belongs in CHANGELOG.md, "
                "not in a standard"
            )
    return errors


def main() -> int:
    errors: list[str] = []
    if not EVALS.is_file():
        errors.append(f"{EVALS}: missing evaluation catalog")
        cases: dict[str, list[dict[str, str]]] = {}
    else:
        cases = json.loads(EVALS.read_text()).get("skills", {})

    paths = sorted(path for path in SKILLS.iterdir() if path.is_dir())
    if not paths:
        errors.append(f"{SKILLS}: no skills found")
    for path in paths:
        errors.extend(validate_skill(path, cases))
    markdown = [
        ROOT / "README.md",
        ROOT / "CONTRIBUTING.md",
        *sorted((ROOT / "docs").rglob("*.md")),
        *sorted(SKILLS.glob("*/SKILL.md")),
        *sorted(SKILLS.glob("*/references/*.md")),
    ]
    for path in markdown:
        errors.extend(validate_markdown_links(path))
    for path in sorted(SKILLS.rglob("*")):
        if path.is_file():
            errors.extend(validate_generic_content(path))

    if errors:
        print("Catalog validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"Validated {len(paths)} skills.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
