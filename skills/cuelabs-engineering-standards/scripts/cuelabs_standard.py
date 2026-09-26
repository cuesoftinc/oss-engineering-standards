#!/usr/bin/env python3
"""Audit and safely apply the portable CueLABS repository baseline."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "templates"
PROJECT_SCHEMA = SKILL_ROOT / "assets" / "schema" / "project.schema.json"

PORTABLE_TEMPLATE_TARGETS = {
    "gitignore": ".gitignore",
    "editorconfig": ".editorconfig",
}

CUELABS_TEMPLATE_TARGETS = {
    **PORTABLE_TEMPLATE_TARGETS,
    "CODEOWNERS": "CODEOWNERS",
    "CODE_OF_CONDUCT.md": "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md": "CONTRIBUTING.md",
    "LICENSE": "LICENSE",
    "SECURITY.md": "SECURITY.md",
    "PULL_REQUEST_TEMPLATE.md": ".github/PULL_REQUEST_TEMPLATE.md",
    "ISSUE_TEMPLATE/bug_report.md": ".github/ISSUE_TEMPLATE/bug_report.md",
    "ISSUE_TEMPLATE/config.yml": ".github/ISSUE_TEMPLATE/config.yml",
    "ISSUE_TEMPLATE/feature_request.md": ".github/ISSUE_TEMPLATE/feature_request.md",
}

CUELABS_APPLICATION_TEMPLATE_TARGETS = {
    "Makefile": "Makefile",
    "dockerignore.root": ".dockerignore",
    "env.example": ".env.example",
}

# Seeded targets are copied when missing but never byte-compared afterwards:
# the canon fixes their variable NAMES and section format, while values and
# product-specific sections legitimately diverge per repository.
SEEDED_TEMPLATE_SOURCES = {"env.example"}

PORTABLE_REPOSITORY_FILES = [
    "CODEOWNERS",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "SECURITY.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/ISSUE_TEMPLATE/bug_report.md",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/feature_request.md",
]
PORTABLE_APPLICATION_FILES = ["Makefile", ".dockerignore", ".env.example"]

STATUSES = {"active", "planned", "paused", "absent"}

# Surfaces `init` can declare; dotted names nest under their prefix.
INIT_SURFACES = ("web", "backend", "mobile.flutter", "mobile.android", "mobile.ios")
DECISIONS_TEMPLATE = TEMPLATE_ROOT / "decisions.md"


class ManifestError(ValueError):
    """The project manifest cannot be parsed or violates its schema."""


class BlockingCollision(RuntimeError):
    """A required file target is occupied by a directory or blocked by a file."""

    def __init__(self, collisions: list[str]):
        super().__init__("blocking path collisions: " + ", ".join(collisions))
        self.collisions = collisions


@dataclass(frozen=True)
class Manifest:
    state: str
    profile: str
    data: dict[str, Any] | None
    errors: list[str]


@dataclass(frozen=True)
class Audit:
    repository: str
    profile: str
    manifest: str
    manifest_errors: list[str]
    active_deviations: list[dict[str, Any]]
    surfaces: dict[str, str]
    missing_shared_files: list[str]
    drifted_shared_files: list[str]
    blocking_collisions: list[str]
    missing_repository_files: list[str]

    @property
    def conforming(self) -> bool:
        return (
            self.manifest not in {"missing", "invalid"}
            and not self.manifest_errors
            and not self.missing_shared_files
            and not self.drifted_shared_files
            and not self.blocking_collisions
            and not self.missing_repository_files
        )


@dataclass(frozen=True)
class PlanStep:
    order: int
    action: str
    mode: str
    paths: list[str]
    reason: str


def split_flow_items(
    value: str, delimiter: str, *, maxsplit: int | None = None
) -> list[str]:
    items: list[str] = []
    start = 0
    stack: list[str] = []
    quote: str | None = None
    escaped = False
    index = 0
    while index < len(value):
        character = value[index]
        if quote == '"':
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quote = None
            index += 1
            continue
        if quote == "'":
            if character == "'" and index + 1 < len(value) and value[index + 1] == "'":
                index += 2
                continue
            if character == "'":
                quote = None
            index += 1
            continue
        if character in {"'", '"'}:
            quote = character
        elif character in "[{":
            stack.append(character)
        elif character in "]}":
            expected = "[" if character == "]" else "{"
            if not stack or stack.pop() != expected:
                raise ManifestError("unbalanced flow collection")
        elif (
            character == delimiter
            and not stack
            and (maxsplit is None or len(items) < maxsplit)
        ):
            items.append(value[start:index].strip())
            start = index + 1
        index += 1

    if quote is not None or stack:
        raise ManifestError("unterminated flow collection")
    items.append(value[start:].strip())
    return items


def split_flow_mapping_entry(value: str) -> tuple[str, str]:
    parts = split_flow_items(value, ":", maxsplit=1)
    if len(parts) != 2:
        raise ManifestError(f"expected a key-value pair in flow mapping: {value!r}")
    return parts[0], parts[1]


def parse_flow_collection(value: str) -> Any:
    opening, closing = value[0], value[-1]
    if (opening, closing) not in {("{", "}"), ("[", "]")}:
        raise ManifestError("unbalanced flow collection")
    content = value[1:-1].strip()
    if not content:
        return {} if opening == "{" else []

    items = split_flow_items(content, ",")
    if items[-1] == "":
        items.pop()
    if any(not item for item in items):
        raise ManifestError("empty item in flow collection")
    if opening == "[":
        return [parse_scalar(item) for item in items]

    mapping: dict[str, Any] = {}
    for item in items:
        raw_key, raw_value = split_flow_mapping_entry(item)
        if not raw_key or not raw_value:
            raise ManifestError(f"incomplete flow mapping entry: {item!r}")
        if raw_key[0:1] in {"'", '"'}:
            key = parse_scalar(raw_key)
        else:
            key = raw_key
        if not isinstance(key, str) or not re.fullmatch(
            r"[A-Za-z][A-Za-z0-9_-]*", key
        ):
            raise ManifestError(f"invalid flow mapping key {raw_key!r}")
        if key in mapping:
            raise ManifestError(f"duplicate key {key!r}")
        mapping[key] = parse_scalar(raw_value)
    return mapping


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"", "null", "Null", "NULL", "~"}:
        return None
    if value.startswith(("{", "[")) or value.endswith(("}", "]")):
        return parse_flow_collection(value)
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if re.fullmatch(r"-?[0-9]+", value):
        return int(value)
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            return json.loads(value)
        except json.JSONDecodeError as error:
            raise ManifestError(f"invalid quoted scalar: {error}") from error
    if len(value) >= 2 and value[0] == value[-1] == "'":
        inner = value[1:-1]
        decoded = ""
        index = 0
        while index < len(inner):
            if inner[index] != "'":
                decoded += inner[index]
                index += 1
                continue
            if index + 1 >= len(inner) or inner[index + 1] != "'":
                raise ManifestError(
                    "invalid single-quoted scalar: internal quotes must be doubled"
                )
            decoded += "'"
            index += 2
        return decoded
    if (
        value[0] in ",[]{}#&*!|>'\"%@`"
        or (
            value[0] in "-?:"
            and (len(value) == 1 or value[1].isspace())
        )
    ):
        raise ManifestError(
            f"plain scalar {value!r} begins with a reserved YAML indicator; "
            "quote the value"
        )
    if re.search(r":(?:\s|$)", value):
        raise ManifestError(
            f"plain scalar {value!r} contains a reserved YAML colon; "
            "quote the value"
        )
    return value


BLOCK_SCALAR = re.compile(
    r"^(?P<indent> *)(?P<prefix>(?:-\s+)?[A-Za-z][A-Za-z0-9_-]*:\s*)"
    r"(?P<style>[|>])(?P<modifiers>(?:[1-9][+-]?|[+-][1-9]?|))"
    r"(?:\s+#.*)?$"
)


def fold_block_lines(lines: list[str]) -> str:
    folded = ""
    for index, line in enumerate(lines):
        folded += line
        if index == len(lines) - 1:
            continue
        following = lines[index + 1]
        if not line:
            if not following:
                folded += "\n"
        elif not following or line[:1].isspace() or following[:1].isspace():
            folded += "\n"
        else:
            folded += " "
    return folded


def expand_block_scalars(text: str) -> str:
    lines = text.splitlines()
    expanded = list(lines)
    index = 0
    while index < len(lines):
        match = BLOCK_SCALAR.fullmatch(lines[index])
        if match is None:
            index += 1
            continue

        header_indent = len(match["indent"])
        modifiers = match["modifiers"]
        explicit_indent = next(
            (int(character) for character in modifiers if character.isdigit()),
            None,
        )
        content_indent = (
            header_indent + explicit_indent
            if explicit_indent is not None
            else None
        )
        content_start = index + 1
        content_end = content_start
        while content_end < len(lines):
            candidate = lines[content_end]
            if not candidate.strip():
                content_end += 1
                continue
            candidate_indent = len(candidate) - len(candidate.lstrip(" "))
            if candidate_indent <= header_indent:
                break
            if content_indent is None:
                content_indent = candidate_indent
            elif candidate_indent < content_indent:
                break
            content_end += 1

        raw_content = lines[content_start:content_end]
        content_indent = content_indent or header_indent + 1
        if any(
            line.strip()
            and len(line) - len(line.lstrip(" ")) < content_indent
            for line in raw_content
        ):
            raise ManifestError(
                f"line {index + 1}: block scalar content is under-indented"
            )

        content = [
            line[content_indent:] if line.strip() else ""
            for line in raw_content
        ]
        value = (
            "\n".join(content)
            if match["style"] == "|"
            else fold_block_lines(content)
        )
        if content:
            if "-" in modifiers:
                value = value.rstrip("\n")
            elif "+" not in modifiers:
                value = value.rstrip("\n") + "\n"
            else:
                value += "\n"

        expanded[index] = (
            f"{match['indent']}{match['prefix']}"
            f"{json.dumps(value, ensure_ascii=False)}"
        )
        for content_index in range(content_start, content_end):
            expanded[content_index] = ""
        index = content_end
    return "\n".join(expanded)


def strip_yaml_comment(content: str) -> str:
    quote: str | None = None
    escaped = False
    index = 0
    while index < len(content):
        character = content[index]
        if quote == '"':
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quote = None
        elif quote == "'":
            if (
                character == "'"
                and index + 1 < len(content)
                and content[index + 1] == "'"
            ):
                index += 1
            elif character == "'":
                quote = None
        elif character in {"'", '"'}:
            quote = character
        elif character == "#" and (
            index == 0 or content[index - 1].isspace()
        ):
            return content[:index].rstrip()
        index += 1
    return content


def unsupported_yaml_indicator(content: str) -> str | None:
    quote: str | None = None
    escaped = False
    index = 0
    while index < len(content):
        character = content[index]
        if quote == '"':
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quote = None
        elif quote == "'":
            if (
                character == "'"
                and index + 1 < len(content)
                and content[index + 1] == "'"
            ):
                index += 1
            elif character == "'":
                quote = None
        elif character in {"'", '"'}:
            quote = character
        elif (
            content.startswith("<<", index)
            and (
                index == 0
                or content[index - 1].isspace()
                or content[index - 1] in "[{,"
            )
            and re.match(r"<<\s*:", content[index:])
        ):
            return "merge keys"
        elif character in {"&", "*", "!"} and (
            index == 0
            or content[index - 1].isspace()
            or content[index - 1] in "[{,:-"
        ):
            return {
                "&": "anchors",
                "*": "aliases",
                "!": "tags",
            }[character]
        index += 1
    return None


def validate_yaml_subset_syntax(text: str) -> None:
    for line_number, raw in enumerate(text.splitlines(), 1):
        content = strip_yaml_comment(raw.strip())
        if not content:
            continue
        if content.startswith("%"):
            raise ManifestError(
                f"line {line_number}: YAML directives are not supported"
            )
        if content in {"---", "..."}:
            raise ManifestError(
                f"line {line_number}: YAML document markers are not supported"
            )
        if content.startswith("?"):
            raise ManifestError(
                f"line {line_number}: complex YAML keys are not supported"
            )
        indicator = unsupported_yaml_indicator(content)
        if indicator is not None:
            raise ManifestError(
                f"line {line_number}: YAML {indicator} are not supported"
            )


def yaml_tokens(text: str) -> list[tuple[int, str, int]]:
    tokens: list[tuple[int, str, int]] = []
    for line_number, raw in enumerate(text.splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise ManifestError(f"line {line_number}: tabs are not allowed")
        indent = len(raw) - len(raw.lstrip(" "))
        if indent % 2:
            raise ManifestError(
                f"line {line_number}: indentation must use multiples of two spaces"
            )
        content = strip_yaml_comment(raw.strip())
        if content:
            tokens.append((indent, content, line_number))
    return tokens


def split_mapping(content: str, line_number: int) -> tuple[str, str]:
    if ":" not in content:
        raise ManifestError(f"line {line_number}: expected a mapping entry")
    key, raw_value = content.split(":", 1)
    key = key.strip()
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", key):
        raise ManifestError(f"line {line_number}: invalid key {key!r}")
    return key, raw_value.strip()


def parse_yaml_block(
    tokens: list[tuple[int, str, int]], index: int, indent: int
) -> tuple[Any, int]:
    if index >= len(tokens) or tokens[index][0] != indent:
        raise ManifestError("invalid indentation")
    is_list = tokens[index][1].startswith("-")
    container: Any = [] if is_list else {}

    while index < len(tokens):
        current_indent, content, line_number = tokens[index]
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ManifestError(f"line {line_number}: unexpected indentation")

        if is_list:
            if not content.startswith("-"):
                break
            item = content[1:].strip()
            index += 1
            if not item:
                if index >= len(tokens) or tokens[index][0] <= indent:
                    raise ManifestError(f"line {line_number}: empty list item")
                value, index = parse_yaml_block(tokens, index, tokens[index][0])
                container.append(value)
                continue
            if ":" not in item:
                container.append(parse_scalar(item))
                continue

            key, raw_value = split_mapping(item, line_number)
            entry: dict[str, Any] = {}
            if raw_value:
                entry[key] = parse_scalar(raw_value)
            elif index < len(tokens) and tokens[index][0] > indent:
                entry[key], index = parse_yaml_block(tokens, index, tokens[index][0])
            else:
                entry[key] = None
            if index < len(tokens) and tokens[index][0] > indent:
                continuation, index = parse_yaml_block(tokens, index, tokens[index][0])
                if not isinstance(continuation, dict):
                    raise ManifestError(
                        f"line {line_number}: list mapping continuation must be a mapping"
                    )
                duplicates = set(entry) & set(continuation)
                if duplicates:
                    raise ManifestError(
                        f"line {line_number}: duplicate keys {sorted(duplicates)}"
                    )
                entry.update(continuation)
            container.append(entry)
            continue

        if content.startswith("-"):
            break
        key, raw_value = split_mapping(content, line_number)
        if key in container:
            raise ManifestError(f"line {line_number}: duplicate key {key!r}")
        index += 1
        if raw_value:
            container[key] = parse_scalar(raw_value)
        elif index < len(tokens) and tokens[index][0] > indent:
            container[key], index = parse_yaml_block(tokens, index, tokens[index][0])
        elif (
            index < len(tokens)
            and tokens[index][0] == indent
            and tokens[index][1].startswith("-")
        ):
            container[key], index = parse_yaml_block(tokens, index, indent)
        else:
            container[key] = None
    return container, index


def parse_yaml_subset(text: str) -> dict[str, Any]:
    expanded = expand_block_scalars(text)
    validate_yaml_subset_syntax(expanded)
    tokens = yaml_tokens(expanded)
    if not tokens:
        raise ManifestError("manifest is empty")
    if tokens[0][0] != 0:
        raise ManifestError("top-level keys must not be indented")
    value, index = parse_yaml_block(tokens, 0, 0)
    if index != len(tokens):
        _, _, line_number = tokens[index]
        raise ManifestError(f"line {line_number}: could not parse entry")
    if not isinstance(value, dict):
        raise ManifestError("manifest root must be a mapping")
    return value


def validate_status(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, str) or value not in STATUSES:
        errors.append(f"{path} must be one of {sorted(STATUSES)}")


def validate_manifest_data(data: dict[str, Any]) -> list[str]:
    # Load the bundled schema so a missing or malformed published contract fails
    # before the manual, dependency-free validation below.
    try:
        schema = json.loads(PROJECT_SCHEMA.read_text())
    except (OSError, json.JSONDecodeError) as error:
        return [f"bundled project schema is unavailable: {error}"]

    errors: list[str] = []
    allowed = set(schema["properties"])
    unknown = sorted(set(data) - allowed)
    if unknown:
        errors.append(f"unknown top-level fields: {unknown}")
    missing = sorted(set(schema["required"]) - set(data))
    if missing:
        errors.append(f"missing required fields: {missing}")

    if data.get("schemaVersion") != 1:
        errors.append("schemaVersion must be 1")
    name = data.get("name")
    if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
        errors.append("name must use lowercase letters, digits, and hyphens")
    if data.get("profile") not in {"base", "cuelabs"}:
        errors.append("profile must be 'base' or 'cuelabs'")

    surfaces = data.get("surfaces")
    if not isinstance(surfaces, dict):
        errors.append("surfaces must be a mapping")
    else:
        for key, value in surfaces.items():
            if not isinstance(key, str):
                errors.append("surface names must be strings")
            elif isinstance(value, dict):
                for child, status in value.items():
                    validate_status(status, f"surfaces.{key}.{child}", errors)
            else:
                validate_status(value, f"surfaces.{key}", errors)

    capabilities = data.get("capabilities", {})
    if not isinstance(capabilities, dict):
        errors.append("capabilities must be a mapping")
    else:
        for key, value in capabilities.items():
            validate_status(value, f"capabilities.{key}", errors)

    deployment = data.get("deployment", {})
    if not isinstance(deployment, dict) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in deployment.items()
    ):
        errors.append("deployment must map string keys to string values")

    deviations = data.get("deviations", [])
    if not isinstance(deviations, list):
        errors.append("deviations must be a list")
    else:
        for index, item in enumerate(deviations):
            prefix = f"deviations[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{prefix} must be a mapping")
                continue
            unknown_deviation = sorted(set(item) - {"id", "reason", "expires"})
            if unknown_deviation:
                errors.append(f"{prefix} has unknown fields: {unknown_deviation}")
            for required in ("id", "reason"):
                if not isinstance(item.get(required), str) or not item[required]:
                    errors.append(f"{prefix}.{required} must be a non-empty string")
            expires = item.get("expires")
            if expires is not None:
                if not isinstance(expires, str):
                    errors.append(f"{prefix}.expires must be a date or null")
                else:
                    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", expires):
                        errors.append(f"{prefix}.expires must use YYYY-MM-DD")
                    else:
                        try:
                            expiration = date.fromisoformat(expires)
                        except ValueError:
                            errors.append(f"{prefix}.expires must use YYYY-MM-DD")
                        else:
                            if expiration < date.today():
                                errors.append(
                                    f"{prefix}.expires has passed "
                                    f"({expiration.isoformat()})"
                                )
    return errors


def load_manifest(path: Path, *, required: bool) -> Manifest:
    if not path.is_file():
        return Manifest(
            state="missing" if required else "not-required",
            profile="unknown",
            data=None,
            errors=[],
        )
    try:
        data = parse_yaml_subset(path.read_text())
    except (OSError, UnicodeError, ManifestError) as error:
        return Manifest("invalid", "unknown", None, [str(error)])
    errors = validate_manifest_data(data)
    if errors:
        return Manifest("invalid", str(data.get("profile", "unknown")), data, errors)
    return Manifest("valid", str(data["profile"]), data, [])


def infer_surfaces(repo: Path) -> dict[str, str]:
    checks = {
        "web": (repo / "web" / "package.json").is_file(),
        "go-api": any((repo / "api").glob("*/go.mod")),
        "flutter": (repo / "mobile" / "flutter" / "pubspec.yaml").is_file(),
        "helm": (repo / "deploy" / "helm" / "Chart.yaml").is_file(),
        "terraform": any((repo / "deploy" / "terraform").glob("*.tf")),
    }
    return {name: ("active" if active else "not-detected") for name, active in checks.items()}


def aggregate_status(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        statuses = set(value.values())
        for status in ("active", "planned", "paused", "absent"):
            if status in statuses:
                return status
    return "absent"


def declared_surfaces(data: dict[str, Any]) -> dict[str, str]:
    declared = data["surfaces"]
    mobile = declared.get("mobile", declared.get("flutter", "absent"))
    flutter = (
        mobile.get("flutter", mobile)
        if isinstance(mobile, dict)
        else mobile
    )
    backend = declared.get(
        "backend",
        declared.get("api", declared.get("go-api", "absent")),
    )
    return {
        "web": aggregate_status(declared.get("web", "absent")),
        "go-api": aggregate_status(backend),
        "flutter": aggregate_status(flutter),
        "helm": (
            "active"
            if data.get("deployment", {}).get("selfHost") == "helm"
            else "not-declared"
        ),
        "terraform": (
            "active"
            if data.get("deployment", {}).get("infrastructure") == "terraform"
            else "not-declared"
        ),
    }


def find_collision(repo: Path, destination_name: str) -> str | None:
    destination = repo / destination_name
    current = destination.parent
    while current != repo:
        if current.is_symlink() or (current.exists() and not current.is_dir()):
            return destination_name
        current = current.parent
    if destination.is_symlink() or (
        destination.exists() and not destination.is_file()
    ):
        return destination_name
    return None


def has_active_application(surfaces: dict[str, str]) -> bool:
    return any(
        surfaces.get(name) == "active" for name in ("web", "go-api", "flutter")
    )


def required_targets(profile: str, surfaces: dict[str, str]) -> dict[str, str]:
    targets = dict(
        CUELABS_TEMPLATE_TARGETS
        if profile == "cuelabs"
        else PORTABLE_TEMPLATE_TARGETS
    )
    if profile == "cuelabs" and has_active_application(surfaces):
        targets.update(CUELABS_APPLICATION_TEMPLATE_TARGETS)
    return targets


def inspect(repo: Path) -> Audit:
    inferred = infer_surfaces(repo)
    product_evidence = any(
        inferred.get(name) == "active" for name in ("web", "go-api", "flutter")
    )
    manifest = load_manifest(repo / ".cuelabs" / "project.yaml", required=product_evidence)
    if manifest.state == "valid" and manifest.data is not None:
        surfaces = declared_surfaces(manifest.data)
    elif manifest.state == "invalid":
        surfaces = {name: "unknown-invalid-manifest" for name in inferred}
    else:
        surfaces = inferred

    active_deviations = (
        [dict(item) for item in manifest.data.get("deviations", [])]
        if manifest.state == "valid" and manifest.data is not None
        else []
    )
    targets = required_targets(manifest.profile, surfaces)
    missing_shared: list[str] = []
    drifted_shared: list[str] = []
    collisions: list[str] = []
    for source_name, destination_name in targets.items():
        collision = find_collision(repo, destination_name)
        if collision:
            collisions.append(collision)
            continue
        destination = repo / destination_name
        if not destination.is_file():
            missing_shared.append(destination_name)
            continue
        source = TEMPLATE_ROOT / source_name
        if not source.is_file():
            collisions.append(f"{destination_name} (bundled template missing)")
        elif (
            source_name not in SEEDED_TEMPLATE_SOURCES
            and destination.read_bytes() != source.read_bytes()
        ):
            drifted_shared.append(destination_name)

    repository_specific = ["README.md", "CHANGELOG.md"]
    if manifest.profile != "cuelabs":
        repository_specific.extend(PORTABLE_REPOSITORY_FILES)
        if has_active_application(surfaces):
            repository_specific.extend(PORTABLE_APPLICATION_FILES)
    if has_active_application(surfaces):
        repository_specific.append(".github/dependabot.yml")
    missing_specific = sorted(
        path for path in repository_specific if not (repo / path).is_file()
    )
    return Audit(
        repository=str(repo),
        profile=manifest.profile,
        manifest=manifest.state,
        manifest_errors=manifest.errors,
        active_deviations=active_deviations,
        surfaces=surfaces,
        missing_shared_files=sorted(missing_shared),
        drifted_shared_files=sorted(drifted_shared),
        blocking_collisions=sorted(collisions),
        missing_repository_files=missing_specific,
    )


def build_plan(audit: Audit) -> list[PlanStep]:
    steps: list[PlanStep] = []

    def add(action: str, mode: str, paths: list[str], reason: str) -> None:
        steps.append(PlanStep(len(steps) + 1, action, mode, paths, reason))

    if audit.manifest == "missing":
        add(
            "Author and validate the project manifest",
            "manual",
            [".cuelabs/project.yaml"],
            "Surface readiness must be declared before application files are applied.",
        )
    elif audit.manifest == "invalid":
        add(
            "Repair and validate the project manifest",
            "manual",
            [".cuelabs/project.yaml"],
            "; ".join(audit.manifest_errors),
        )
    if audit.active_deviations:
        deviation_ids = ", ".join(
            str(deviation["id"]) for deviation in audit.active_deviations
        )
        add(
            "Review active manifest deviations",
            "manual",
            [".cuelabs/project.yaml"],
            f"Documented exceptions still require follow-up: {deviation_ids}.",
        )
    if audit.blocking_collisions:
        add(
            "Resolve blocking path collisions",
            "manual",
            audit.blocking_collisions,
            "A required file target or one of its parents is not the expected type.",
        )
    if audit.drifted_shared_files:
        add(
            "Review shared-file drift and replace intentionally",
            "manual",
            audit.drifted_shared_files,
            "Existing files differ from the canonical templates and are never overwritten automatically.",
        )
    if audit.missing_shared_files:
        add(
            "Copy missing canonical templates",
            "automatic",
            audit.missing_shared_files,
            "The apply operation can create these files without overwriting existing paths.",
        )
    if audit.missing_repository_files:
        add(
            "Author repository-specific files",
            "manual",
            audit.missing_repository_files,
            "These files require repository-specific content and are not copied blindly.",
        )
    add(
        "Run verification and repository-native checks",
        "automatic",
        [],
        "Confirm the baseline, then run tests appropriate to active surfaces.",
    )
    return steps


def print_audit(audit: Audit, *, heading: str) -> None:
    print(f"# {heading}")
    print()
    print(f"- Repository: `{audit.repository}`")
    print(f"- Profile: `{audit.profile}`")
    print(f"- Project manifest: {audit.manifest}")
    print(f"- Baseline conforming: {'yes' if audit.conforming else 'no'}")
    if audit.manifest_errors:
        print("- Manifest errors:")
        for error in audit.manifest_errors:
            print(f"  - {error}")
    print()
    print("## Active deviations")
    print()
    if audit.active_deviations:
        for deviation in audit.active_deviations:
            expiry = deviation.get("expires")
            expiry_text = (
                f"expires `{expiry}`" if expiry is not None else "no expiry"
            )
            print(
                f"- `{deviation['id']}`: {deviation['reason']} ({expiry_text})"
            )
    else:
        print("- None")
    print()
    print("## Detected surfaces")
    print()
    for name, state in audit.surfaces.items():
        print(f"- `{name}`: {state}")
    sections = (
        ("Missing shared files", audit.missing_shared_files),
        ("Drifted shared files", audit.drifted_shared_files),
        ("Blocking collisions", audit.blocking_collisions),
        ("Missing repository-specific files", audit.missing_repository_files),
    )
    for title, paths in sections:
        print()
        print(f"## {title}")
        print()
        if paths:
            for path in paths:
                suffix = (
                    " (author for this repository; do not copy blindly)"
                    if title == "Missing repository-specific files"
                    else ""
                )
                print(f"- `{path}`{suffix}")
        else:
            print("- None")


def print_plan(audit: Audit, plan: list[PlanStep]) -> None:
    print_audit(audit, heading="CueLABS standards plan")
    print()
    print("## Ordered actions")
    print()
    for step in plan:
        print(f"{step.order}. **{step.action}** (`{step.mode}`)")
        print(f"   - Why: {step.reason}")
        if step.paths:
            print(f"   - Paths: {', '.join(f'`{path}`' for path in step.paths)}")
    print()
    print("## Assumptions")
    print()
    print("- Existing files are preserved unless a human approves replacement.")
    print("- A valid manifest overrides placeholder filesystem evidence.")
    print("- Only declared active product surfaces receive application-only files.")


def emit_audit(audit: Audit, output_format: str, *, heading: str) -> None:
    if output_format == "json":
        payload = asdict(audit)
        payload["conforming"] = audit.conforming
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print_audit(audit, heading=heading)


def emit_plan(audit: Audit, output_format: str) -> None:
    plan = build_plan(audit)
    if output_format == "json":
        payload = asdict(audit)
        payload["conforming"] = audit.conforming
        payload["plan"] = [asdict(step) for step in plan]
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print_plan(audit, plan)


def apply_missing(repo: Path) -> list[str]:
    audit = inspect(repo)
    if audit.manifest == "missing":
        raise ManifestError(
            "required project manifest is missing: .cuelabs/project.yaml"
        )
    if audit.manifest == "invalid":
        raise ManifestError("; ".join(audit.manifest_errors))
    if audit.blocking_collisions:
        raise BlockingCollision(audit.blocking_collisions)
    copied: list[str] = []
    targets = required_targets(audit.profile, audit.surfaces)
    for source_name, destination_name in targets.items():
        source = TEMPLATE_ROOT / source_name
        destination = repo / destination_name
        if destination.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        copied.append(destination_name)
    return copied


def parse_surface_flags(values: list[str]) -> dict[str, str]:
    surfaces: dict[str, str] = {}
    for value in values:
        name, separator, status = value.partition("=")
        if not separator or name not in INIT_SURFACES or status not in STATUSES:
            raise ManifestError(
                f"invalid --surface {value!r}: expected NAME=STATUS with NAME in "
                f"{', '.join(INIT_SURFACES)} and STATUS in "
                f"{', '.join(sorted(STATUSES))}"
            )
        if name in surfaces:
            raise ManifestError(f"surface {name!r} is declared twice")
        surfaces[name] = status
    if not surfaces:
        raise ManifestError(
            "declare at least one surface, e.g. --surface web=planned"
        )
    return surfaces


def render_manifest(name: str, profile: str, surfaces: dict[str, str]) -> str:
    lines = [
        "# Syntax: references/project-manifest.md in the installed engineering skill.",
        "schemaVersion: 1",
        f"name: {name}",
        f"profile: {profile}",
        "",
        "surfaces:",
    ]
    nested: dict[str, dict[str, str]] = {}
    for surface in INIT_SURFACES:
        if surface not in surfaces:
            continue
        parent, _, child = surface.partition(".")
        if child:
            nested.setdefault(parent, {})[child] = surfaces[surface]
        else:
            lines.append(f"  {surface}: {surfaces[surface]}")
    for parent, children in nested.items():
        lines.append(f"  {parent}:")
        lines.extend(f"    {child}: {status}" for child, status in children.items())
    lines += ["", "capabilities: {}", "deployment: {}", "deviations: []", ""]
    return "\n".join(lines)


def render_decisions(name: str, display_name: str) -> str:
    template = DECISIONS_TEMPLATE.read_text(encoding="utf-8")
    return template.replace("{{Product}}", display_name).replace("{{product}}", name)


def initialize(
    repo: Path,
    *,
    name: str,
    profile: str,
    surfaces: dict[str, str],
    display_name: str | None = None,
) -> list[str]:
    """Create the manifest (and, for cuelabs, docs/decisions.md) for a new product.

    Never overwrites: an existing manifest is an error, an existing
    decisions register is kept as-is.
    """
    text = render_manifest(name, profile, surfaces)
    errors = validate_manifest_data(parse_yaml_subset(text))
    if errors:
        raise ManifestError("; ".join(errors))
    manifest_path = repo / ".cuelabs" / "project.yaml"
    for destination_name in (".cuelabs/project.yaml", "docs/decisions.md"):
        collision = find_collision(repo, destination_name)
        if collision:
            raise BlockingCollision([collision])
    if manifest_path.exists():
        raise ManifestError(
            "project manifest already exists: .cuelabs/project.yaml; "
            "edit it instead of re-running init"
        )

    created: list[str] = []
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(text, encoding="utf-8", newline="\n")
    created.append(".cuelabs/project.yaml")

    decisions = repo / "docs" / "decisions.md"
    if profile == "cuelabs" and not decisions.exists():
        display = display_name or name.replace("-", " ").title()
        decisions.parent.mkdir(parents=True, exist_ok=True)
        decisions.write_text(
            render_decisions(name, display), encoding="utf-8", newline="\n"
        )
        created.append("docs/decisions.md")
    return created


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Initialize, audit, or apply the CueLABS repository baseline."
    )
    parser.add_argument(
        "operation", choices=("init", "audit", "plan", "apply", "verify")
    )
    parser.add_argument("--repo", default=".", help="Target repository path")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--name", help="init: product slug (lowercase, hyphens)")
    parser.add_argument(
        "--display-name", help="init: display name (default: title-cased slug)"
    )
    parser.add_argument(
        "--profile", choices=("cuelabs", "base"), default="cuelabs",
        help="init: standards profile",
    )
    parser.add_argument(
        "--surface", action="append", default=[], metavar="NAME=STATUS",
        help="init: declare a surface, e.g. web=planned (repeatable)",
    )
    return parser.parse_args()


def run_init(repo: Path, args: argparse.Namespace) -> int:
    if not args.name:
        print("error: init requires --name <product-slug>", file=sys.stderr)
        return 2
    try:
        created = initialize(
            repo,
            name=args.name,
            profile=args.profile,
            surfaces=parse_surface_flags(args.surface),
            display_name=args.display_name,
        )
    except (BlockingCollision, ManifestError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps({"created": created}, indent=2))
        return 0
    print("# CueLABS standards init")
    print()
    print("## Created files")
    print()
    for path in created:
        print(f"- `{path}`")
    print()
    print("## Next steps")
    print()
    print("1. Run `apply` to copy the missing shared files.")
    if "docs/decisions.md" in created:
        print(
            "2. Fill in the Standard parameters table in `docs/decisions.md` "
            "before building each surface."
        )
    return 0


def is_git_worktree(repo: Path) -> bool:
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "rev-parse",
                "--is-inside-work-tree",
                "--show-toplevel",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    lines = result.stdout.splitlines()
    if result.returncode != 0 or len(lines) != 2 or lines[0] != "true":
        return False
    return Path(lines[1]).resolve() == repo.resolve()


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).expanduser().resolve()
    if not is_git_worktree(repo):
        print(f"error: not a git repository: {repo}", file=sys.stderr)
        return 2
    if args.operation == "init":
        return run_init(repo, args)

    before = inspect(repo)
    if args.operation == "audit":
        emit_audit(before, args.format, heading="CueLABS standards audit")
        return 0
    if args.operation == "plan":
        emit_plan(before, args.format)
        return 0
    if args.operation == "apply":
        try:
            copied = apply_missing(repo)
        except (BlockingCollision, ManifestError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        after = inspect(repo)
        emit_audit(after, args.format, heading="CueLABS standards apply result")
        if args.format == "markdown":
            print()
            print("## Copied files")
            print()
            if copied:
                for path in copied:
                    print(f"- `{path}`")
            else:
                print("- None; existing files were preserved.")
        return 0 if after.conforming else 1

    emit_audit(before, args.format, heading="CueLABS standards verification")
    return 0 if before.conforming else 1


if __name__ == "__main__":
    raise SystemExit(main())
