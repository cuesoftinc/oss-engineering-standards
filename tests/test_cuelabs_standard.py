from __future__ import annotations

import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, timedelta
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "skills"
    / "cuelabs-engineering-standards"
    / "scripts"
    / "cuelabs_standard.py"
)
SPEC = importlib.util.spec_from_file_location("cuelabs_standard", SCRIPT)
assert SPEC and SPEC.loader
standard = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = standard
SPEC.loader.exec_module(standard)


class StandardsCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / ".git").mkdir()
        (self.repo / "README.md").write_text("# Fixture\n")
        (self.repo / "CHANGELOG.md").write_text("# Changelog\n")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_manifest(
        self, surfaces: str = "  web: active\n", *, profile: str = "cuelabs"
    ) -> None:
        manifest = self.repo / ".cuelabs" / "project.yaml"
        manifest.parent.mkdir()
        manifest.write_text(
            "schemaVersion: 1\n"
            "name: fixture\n"
            f"profile: {profile}\n"
            "surfaces:\n"
            f"{surfaces}"
            "capabilities: {}\n"
            "deployment: {}\n"
            "deviations: []\n"
        )

    def copy_required_templates(
        self, *, application: bool, profile: str = "cuelabs"
    ) -> None:
        surfaces = {"web": "active" if application else "absent"}
        targets = standard.required_targets(profile, surfaces)
        for source_name, destination_name in targets.items():
            source = standard.TEMPLATE_ROOT / source_name
            destination = self.repo / destination_name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())

    def test_declared_planned_surface_overrides_placeholder_files(self) -> None:
        self.write_manifest("  web: planned\n")
        (self.repo / "web").mkdir()
        (self.repo / "web" / "package.json").write_text('{"name":"placeholder"}\n')
        self.copy_required_templates(application=False)

        audit = standard.inspect(self.repo)

        self.assertEqual(audit.surfaces["web"], "planned")
        self.assertNotIn("Makefile", audit.missing_shared_files)
        self.assertNotIn(".env.example", audit.missing_shared_files)
        self.assertNotIn(".github/dependabot.yml", audit.missing_repository_files)
        self.assertTrue(audit.conforming)

    def test_shared_file_drift_fails_conformance(self) -> None:
        self.write_manifest("  web: absent\n")
        self.copy_required_templates(application=False)
        (self.repo / "LICENSE").write_text("not the canonical license\n")

        audit = standard.inspect(self.repo)

        self.assertIn("LICENSE", audit.drifted_shared_files)
        self.assertFalse(audit.conforming)

    def test_customized_env_example_is_seeded_not_drift(self) -> None:
        self.write_manifest("  web: active\n")
        self.copy_required_templates(application=True)
        (self.repo / ".env.example").write_text(
            "# product local development environment.\nJWT_SECRET=dev-only\n"
        )
        (self.repo / ".github").mkdir(exist_ok=True)
        (self.repo / ".github" / "dependabot.yml").write_text("version: 2\n")

        audit = standard.inspect(self.repo)

        self.assertNotIn(".env.example", audit.drifted_shared_files)
        self.assertTrue(audit.conforming)

    def test_missing_env_example_is_still_seeded_on_apply(self) -> None:
        self.write_manifest("  web: active\n")
        self.copy_required_templates(application=True)
        (self.repo / ".env.example").unlink()

        audit = standard.inspect(self.repo)

        self.assertIn(".env.example", audit.missing_shared_files)

    def test_invalid_manifest_is_rejected(self) -> None:
        manifest = self.repo / ".cuelabs" / "project.yaml"
        manifest.parent.mkdir()
        manifest.write_text("schemaVersion: nope\nsurfaces: []\n")
        self.copy_required_templates(application=False)

        audit = standard.inspect(self.repo)

        self.assertEqual(audit.manifest, "invalid")
        self.assertTrue(audit.manifest_errors)
        self.assertFalse(audit.conforming)
        with self.assertRaises(standard.ManifestError):
            standard.apply_missing(self.repo)

    def test_invalid_utf8_manifest_is_reported_without_traceback(self) -> None:
        manifest = self.repo / ".cuelabs" / "project.yaml"
        manifest.parent.mkdir()
        manifest.write_bytes(b"schemaVersion: 1\nname: \xff\n")

        audit = standard.inspect(self.repo)

        self.assertEqual(audit.manifest, "invalid")
        self.assertTrue(any("decode" in error for error in audit.manifest_errors))
        self.assertFalse(audit.conforming)
        with self.assertRaises(standard.ManifestError):
            standard.apply_missing(self.repo)

    def test_plan_is_ordered_and_distinguishes_manual_and_automatic(self) -> None:
        (self.repo / "web").mkdir()
        (self.repo / "web" / "package.json").write_text('{"name":"fixture"}\n')

        plan = standard.build_plan(standard.inspect(self.repo))

        self.assertEqual([step.order for step in plan], list(range(1, len(plan) + 1)))
        self.assertEqual(plan[0].action, "Author and validate the project manifest")
        self.assertTrue(any(step.mode == "automatic" for step in plan))
        self.assertTrue(any(step.mode == "manual" for step in plan))

    def test_apply_rejects_directory_collision(self) -> None:
        self.write_manifest("  web: absent\n")
        self.copy_required_templates(application=False)
        (self.repo / "CODEOWNERS").unlink()
        (self.repo / "CODEOWNERS").mkdir()

        with self.assertRaises(standard.BlockingCollision) as context:
            standard.apply_missing(self.repo)

        self.assertIn("CODEOWNERS", context.exception.collisions)

    def test_apply_is_idempotent_and_preserves_existing_files(self) -> None:
        self.write_manifest("  web: absent\n")
        first = standard.apply_missing(self.repo)
        second = standard.apply_missing(self.repo)

        self.assertTrue(first)
        self.assertEqual(second, [])
        self.assertTrue(standard.inspect(self.repo).conforming)

    def test_manifest_deviation_list_is_parsed_and_validated(self) -> None:
        manifest = self.repo / ".cuelabs" / "project.yaml"
        manifest.parent.mkdir()
        manifest.write_text(
            "schemaVersion: 1\n"
            "name: fixture\n"
            "profile: base\n"
            "surfaces:\n"
            "  web: absent # intentionally not implemented\n"
            "deviations:\n"
            "  - id: EX-1\n"
            "    reason: Intentional exception\n"
            f"    expires: {(date.today() + timedelta(days=30)).isoformat()}\n"
        )
        self.copy_required_templates(application=False, profile="base")
        for path in standard.PORTABLE_REPOSITORY_FILES:
            destination = self.repo / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(f"fixture-owned {path}\n")

        audit = standard.inspect(self.repo)

        self.assertEqual(audit.manifest, "valid")
        self.assertEqual(audit.manifest_errors, [])
        self.assertEqual(audit.active_deviations[0]["id"], "EX-1")
        self.assertTrue(audit.conforming)

        markdown = io.StringIO()
        with redirect_stdout(markdown):
            standard.emit_audit(
                audit, "markdown", heading="CueLABS standards audit"
            )
        self.assertIn("## Active deviations", markdown.getvalue())
        self.assertIn("`EX-1`: Intentional exception", markdown.getvalue())

        json_output = io.StringIO()
        with redirect_stdout(json_output):
            standard.emit_plan(audit, "json")
        payload = json.loads(json_output.getvalue())
        self.assertEqual(payload["active_deviations"][0]["id"], "EX-1")
        self.assertTrue(
            any(
                step["action"] == "Review active manifest deviations"
                for step in payload["plan"]
            )
        )

    def test_indentationless_deviation_sequence_is_parsed(self) -> None:
        data = standard.parse_yaml_subset(
            "schemaVersion: 1\n"
            "name: fixture\n"
            "profile: cuelabs\n"
            "surfaces: { web: absent }\n"
            "deviations:\n"
            "- id: EX-1\n"
            "  reason: Valid indentationless sequence\n"
            "  expires: null\n"
        )

        self.assertEqual(data["deviations"][0]["id"], "EX-1")
        self.assertEqual(
            data["deviations"][0]["reason"],
            "Valid indentationless sequence",
        )
        self.assertIsNone(data["deviations"][0]["expires"])

    def test_unsupported_yaml_features_fail_explicitly(self) -> None:
        cases = {
            "anchors": "value: &shared active\n",
            "aliases": "value: *shared\n",
            "tags": "value: !custom active\n",
            "merge keys": "value: { <<: { web: active } }\n",
            "directives": "%YAML 1.2\nvalue: active\n",
            "document markers": "---\nvalue: active\n",
            "complex YAML keys": "? [web, active]\n: value\n",
        }

        for feature, manifest in cases.items():
            with self.subTest(feature=feature):
                with self.assertRaisesRegex(standard.ManifestError, feature):
                    standard.parse_yaml_subset(manifest)

    def test_reserved_yaml_indicators_inside_strings_are_preserved(self) -> None:
        data = standard.parse_yaml_subset(
            'reason: "Use &shared, *alias, !tag, and <<: as literal text"\n'
        )

        self.assertEqual(
            data["reason"],
            "Use &shared, *alias, !tag, and <<: as literal text",
        )

    def test_unquoted_reserved_indicator_scalars_are_rejected(self) -> None:
        for value in ("- invalid", "? invalid", "@invalid", "`invalid"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    standard.ManifestError,
                    "reserved YAML indicator",
                ):
                    standard.parse_yaml_subset(f"reason: {value}\n")

    def test_reserved_plain_colon_and_lone_single_quote_are_rejected(self) -> None:
        with self.assertRaisesRegex(standard.ManifestError, "reserved YAML colon"):
            standard.parse_yaml_subset("reason: key: value\n")
        with self.assertRaisesRegex(standard.ManifestError, "reserved YAML colon"):
            standard.parse_yaml_subset("value: { reason: key: value }\n")
        with self.assertRaisesRegex(
            standard.ManifestError,
            "internal quotes must be doubled",
        ):
            standard.parse_yaml_subset("reason: 'owner's note'\n")

        data = standard.parse_yaml_subset("reason: 'owner''s note'\n")
        self.assertEqual(data["reason"], "owner's note")

    def test_apply_requires_manifest_before_modifying_active_product(self) -> None:
        (self.repo / "web").mkdir()
        (self.repo / "web" / "package.json").write_text('{"name":"fixture"}\n')

        with self.assertRaises(standard.ManifestError):
            standard.apply_missing(self.repo)

        self.assertFalse((self.repo / "Makefile").exists())
        self.assertFalse((self.repo / ".github").exists())

    def test_base_profile_preserves_repository_identity_files(self) -> None:
        self.write_manifest("  web: absent\n", profile="base")
        self.copy_required_templates(application=False, profile="base")
        repository_content = {
            path: f"external project content for {path}\n"
            for path in standard.PORTABLE_REPOSITORY_FILES
        }
        for path, content in repository_content.items():
            destination = self.repo / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content)

        audit = standard.inspect(self.repo)
        copied = standard.apply_missing(self.repo)

        self.assertTrue(audit.conforming)
        self.assertEqual(copied, [])
        for path, content in repository_content.items():
            self.assertEqual((self.repo / path).read_text(), content)

    def test_expired_deviation_invalidates_manifest(self) -> None:
        manifest = self.repo / ".cuelabs" / "project.yaml"
        manifest.parent.mkdir()
        manifest.write_text(
            "schemaVersion: 1\n"
            "name: fixture\n"
            "profile: base\n"
            "surfaces:\n"
            "  web: absent\n"
            "deviations:\n"
            "  - id: EX-1\n"
            "    reason: Expired exception\n"
            f"    expires: {(date.today() - timedelta(days=1)).isoformat()}\n"
        )

        audit = standard.inspect(self.repo)

        self.assertEqual(audit.manifest, "invalid")
        self.assertTrue(any("has passed" in error for error in audit.manifest_errors))
        with self.assertRaises(standard.ManifestError):
            standard.apply_missing(self.repo)

    def test_basic_iso_deviation_date_is_rejected(self) -> None:
        manifest = self.repo / ".cuelabs" / "project.yaml"
        manifest.parent.mkdir()
        manifest.write_text(
            "schemaVersion: 1\n"
            "name: fixture\n"
            "profile: base\n"
            "surfaces:\n"
            "  web: absent\n"
            "deviations:\n"
            "  - id: EX-1\n"
            "    reason: Malformed date\n"
            '    expires: "20991231"\n'
        )

        audit = standard.inspect(self.repo)

        self.assertEqual(audit.manifest, "invalid")
        self.assertTrue(
            any("must use YYYY-MM-DD" in error for error in audit.manifest_errors)
        )

    def test_empty_deviation_expiry_is_yaml_null(self) -> None:
        manifest = self.repo / ".cuelabs" / "project.yaml"
        manifest.parent.mkdir()
        manifest.write_text(
            "schemaVersion: 1\n"
            "name: fixture\n"
            "profile: cuelabs\n"
            "surfaces:\n"
            "  web: absent\n"
            "deviations:\n"
            "  - id: EX-1\n"
            "    reason: Non-expiring exception\n"
            "    expires:\n"
        )

        audit = standard.inspect(self.repo)

        self.assertEqual(audit.manifest, "valid")
        self.assertIsNone(audit.active_deviations[0]["expires"])

    def test_flow_style_surfaces_are_parsed(self) -> None:
        manifest = self.repo / ".cuelabs" / "project.yaml"
        manifest.parent.mkdir()
        manifest.write_text(
            "schemaVersion: 1\n"
            "name: fixture\n"
            "profile: cuelabs\n"
            "surfaces: { web: active, mobile: { flutter: planned } }\n"
            "capabilities: {}\n"
            "deployment: {}\n"
            "deviations: []\n"
        )
        self.copy_required_templates(application=True)
        (self.repo / ".github" / "dependabot.yml").write_text("version: 2\n")

        audit = standard.inspect(self.repo)

        self.assertEqual(audit.manifest, "valid")
        self.assertEqual(audit.surfaces["web"], "active")
        self.assertEqual(audit.surfaces["flutter"], "planned")
        self.assertTrue(audit.conforming)

    def test_flow_style_deviations_are_parsed(self) -> None:
        manifest = self.repo / ".cuelabs" / "project.yaml"
        manifest.parent.mkdir()
        manifest.write_text(
            "schemaVersion: 1\n"
            "name: fixture\n"
            "profile: cuelabs\n"
            "surfaces: { web: absent }\n"
            "capabilities: {}\n"
            "deployment: {}\n"
            "deviations: [{ id: EX-1, reason: Flow exception, expires: null }]\n"
        )
        self.copy_required_templates(application=False)

        audit = standard.inspect(self.repo)

        self.assertEqual(audit.manifest, "valid")
        self.assertEqual(audit.active_deviations[0]["id"], "EX-1")
        self.assertIsNone(audit.active_deviations[0]["expires"])
        self.assertTrue(audit.conforming)

    def test_literal_and_folded_block_scalar_reasons_are_parsed(self) -> None:
        manifest = self.repo / ".cuelabs" / "project.yaml"
        manifest.parent.mkdir()
        manifest.write_text(
            "schemaVersion: 1\n"
            "name: fixture\n"
            "profile: cuelabs\n"
            "surfaces: { web: absent }\n"
            "capabilities: {}\n"
            "deployment: {}\n"
            "deviations:\n"
            "  - id: EX-1\n"
            "    reason: |\n"
            "      Preserve this line\n"
            "      and this line.\n"
            "    expires: null\n"
            "  - id: EX-2\n"
            "    reason: >-\n"
            "      Fold this line\n"
            "      into this line.\n"
            "    expires: null\n"
        )
        self.copy_required_templates(application=False)

        audit = standard.inspect(self.repo)

        self.assertEqual(audit.manifest, "valid")
        self.assertEqual(
            audit.active_deviations[0]["reason"],
            "Preserve this line\nand this line.\n",
        )
        self.assertEqual(
            audit.active_deviations[1]["reason"],
            "Fold this line into this line.",
        )
        self.assertTrue(audit.conforming)

    def test_block_scalar_can_be_first_key_in_list_item(self) -> None:
        data = standard.parse_yaml_subset(
            "schemaVersion: 1\n"
            "name: fixture\n"
            "profile: cuelabs\n"
            "surfaces: { web: absent }\n"
            "deviations:\n"
            "  - reason: |\n"
            "      Multi-line reason.\n"
            "    id: EX-1\n"
            "    expires: null\n"
        )

        self.assertEqual(data["deviations"][0]["reason"], "Multi-line reason.\n")
        self.assertEqual(data["deviations"][0]["id"], "EX-1")
        self.assertIsNone(data["deviations"][0]["expires"])

    def test_escaped_quote_does_not_expose_hash_as_comment(self) -> None:
        data = standard.parse_yaml_subset(
            "schemaVersion: 1\n"
            "name: fixture\n"
            "profile: cuelabs\n"
            "surfaces: { web: absent }\n"
            "deviations:\n"
            '  - reason: "Owner wrote \\" # still part of the reason"\n'
            "    id: EX-1\n"
            "    expires: null\n"
        )

        self.assertEqual(
            data["deviations"][0]["reason"],
            'Owner wrote " # still part of the reason',
        )

    def test_go_api_surface_alias_activates_application_requirements(self) -> None:
        self.write_manifest("  go-api: active\n")
        self.copy_required_templates(application=True)
        (self.repo / ".github" / "dependabot.yml").write_text("version: 2\n")

        audit = standard.inspect(self.repo)

        self.assertEqual(audit.surfaces["go-api"], "active")
        self.assertTrue(audit.conforming)

    def test_additional_go_service_requires_manifest(self) -> None:
        service = self.repo / "api" / "measure"
        service.mkdir(parents=True)
        (service / "go.mod").write_text("module example.com/measure\n")

        audit = standard.inspect(self.repo)

        self.assertEqual(audit.surfaces["go-api"], "active")
        self.assertEqual(audit.manifest, "missing")
        self.assertFalse(audit.conforming)
        with self.assertRaises(standard.ManifestError):
            standard.apply_missing(self.repo)

    def test_web_skill_bundles_canonical_prettierignore(self) -> None:
        core = (
            ROOT
            / "skills"
            / "cuelabs-engineering-standards"
            / "assets"
            / "templates"
            / "prettierignore.web"
        )
        web = (
            ROOT
            / "skills"
            / "cuelabs-web-standard"
            / "assets"
            / "templates"
            / "prettierignore.web"
        )

        self.assertEqual(web.read_bytes(), core.read_bytes())

    def test_nested_backend_status_activates_application_requirements(self) -> None:
        self.write_manifest("  backend:\n    go: active\n")
        self.copy_required_templates(application=True)
        (self.repo / ".github" / "dependabot.yml").write_text("version: 2\n")

        audit = standard.inspect(self.repo)

        self.assertEqual(audit.surfaces["go-api"], "active")
        self.assertTrue(audit.conforming)

    def test_nested_web_status_activates_application_requirements(self) -> None:
        self.write_manifest("  web:\n    storefront: active\n")
        self.copy_required_templates(application=True)
        (self.repo / ".github" / "dependabot.yml").write_text("version: 2\n")

        audit = standard.inspect(self.repo)

        self.assertEqual(audit.surfaces["web"], "active")
        self.assertTrue(audit.conforming)

    def test_cli_rejects_fake_git_metadata_before_apply(self) -> None:
        shutil.rmtree(self.repo / ".git")
        (self.repo / ".git").write_text("not git metadata\n")
        stderr = io.StringIO()

        with mock.patch.object(
            sys, "argv", ["cuelabs_standard.py", "apply", "--repo", str(self.repo)]
        ):
            with redirect_stderr(stderr):
                exit_code = standard.main()

        self.assertEqual(exit_code, 2)
        self.assertIn("not a git repository", stderr.getvalue())
        self.assertFalse((self.repo / ".gitignore").exists())

    def test_git_worktree_validation_accepts_repository_root(self) -> None:
        subprocess.run(
            ["git", "init", "--quiet", str(self.repo)],
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertTrue(standard.is_git_worktree(self.repo))

    def test_init_writes_valid_manifest_and_decisions_register(self) -> None:
        created = standard.initialize(
            self.repo,
            name="acme-labs",
            profile="cuelabs",
            surfaces={"web": "planned", "mobile.flutter": "absent"},
        )

        self.assertEqual(created, [".cuelabs/project.yaml", "docs/decisions.md"])
        audit = standard.inspect(self.repo)
        self.assertEqual(audit.manifest, "valid")
        self.assertEqual(audit.surfaces["web"], "planned")
        self.assertEqual(audit.surfaces["flutter"], "absent")
        decisions = (self.repo / "docs" / "decisions.md").read_text(encoding="utf-8")
        self.assertIn("# Acme Labs — Decisions", decisions)
        self.assertIn("| P-01 | Product slug | acme-labs |", decisions)
        self.assertIn("| P-14 | Discord channel | — | Proposed: `#acme-labs-lab`", decisions)
        self.assertNotIn("{{", decisions)

    def test_init_then_apply_reaches_conformance_on_empty_repo(self) -> None:
        standard.initialize(
            self.repo, name="acme", profile="cuelabs", surfaces={"web": "planned"}
        )

        standard.apply_missing(self.repo)

        self.assertTrue(standard.inspect(self.repo).conforming)

    def test_init_never_overwrites_existing_files(self) -> None:
        self.write_manifest()
        manifest = self.repo / ".cuelabs" / "project.yaml"
        original = manifest.read_bytes()

        with self.assertRaises(standard.ManifestError):
            standard.initialize(
                self.repo, name="acme", profile="cuelabs", surfaces={"web": "active"}
            )
        self.assertEqual(manifest.read_bytes(), original)

        manifest.unlink()
        decisions = self.repo / "docs" / "decisions.md"
        decisions.parent.mkdir()
        decisions.write_text("# Existing register\n")
        created = standard.initialize(
            self.repo, name="acme", profile="cuelabs", surfaces={"web": "active"}
        )
        self.assertEqual(created, [".cuelabs/project.yaml"])
        self.assertEqual(decisions.read_text(), "# Existing register\n")

    def test_init_base_profile_skips_decisions_register(self) -> None:
        created = standard.initialize(
            self.repo, name="acme", profile="base", surfaces={"backend": "active"}
        )

        self.assertEqual(created, [".cuelabs/project.yaml"])
        self.assertEqual(standard.inspect(self.repo).profile, "base")

    def test_init_rejects_invalid_arguments_before_writing(self) -> None:
        with self.assertRaises(standard.ManifestError):
            standard.initialize(
                self.repo, name="Bad_Name", profile="cuelabs", surfaces={"web": "active"}
            )
        for flags in ([], ["api=active"], ["web=done"], ["web"], ["web=active", "web=planned"]):
            with self.assertRaises(standard.ManifestError):
                standard.parse_surface_flags(flags)
        self.assertFalse((self.repo / ".cuelabs").exists())

    def test_cli_init_requires_name(self) -> None:
        stderr = io.StringIO()
        with mock.patch.object(standard, "is_git_worktree", return_value=True):
            with mock.patch.object(
                sys,
                "argv",
                ["cuelabs_standard.py", "init", "--repo", str(self.repo),
                 "--surface", "web=planned"],
            ):
                with redirect_stderr(stderr):
                    exit_code = standard.main()

        self.assertEqual(exit_code, 2)
        self.assertIn("--name", stderr.getvalue())
        self.assertFalse((self.repo / ".cuelabs").exists())

    def test_apply_rejects_symlinked_template_parent(self) -> None:
        self.write_manifest("  web: absent\n")
        with tempfile.TemporaryDirectory() as outside_dir:
            outside = Path(outside_dir)
            (self.repo / ".github").symlink_to(outside, target_is_directory=True)

            with self.assertRaises(standard.BlockingCollision):
                standard.apply_missing(self.repo)

            self.assertFalse((outside / "PULL_REQUEST_TEMPLATE.md").exists())

    def test_web_dockerfile_creates_optional_public_directory(self) -> None:
        dockerfile = (standard.TEMPLATE_ROOT / "Dockerfile.web").read_text()

        create = dockerfile.index("RUN mkdir -p public")
        build = dockerfile.index("RUN npm run build")
        copy = dockerfile.index("COPY --from=builder /app/public ./public")
        self.assertLess(create, build)
        self.assertLess(build, copy)

    def test_helm_envoy_configmap_matches_deployment_volume(self) -> None:
        templates = standard.TEMPLATE_ROOT / "helm" / "templates"
        configmap = (templates / "envoy-configmap.yaml").read_text()
        deployment = (templates / "deployment.yaml").read_text()

        self.assertIn("kind: ConfigMap", configmap)
        self.assertIn("name: {{ $name }}-envoy-config", configmap)
        self.assertIn("$.Files.Get $svc.envoyConfig", configmap)
        self.assertIn("name: {{ $name }}-envoy-config", deployment)

    def test_helm_envoy_configmap_renders(self) -> None:
        helm = shutil.which("helm")
        if helm is None:
            self.skipTest("helm is not installed")
        chart = self.repo / "chart"
        shutil.copytree(standard.TEMPLATE_ROOT / "helm", chart)
        (chart / "Chart.yaml").write_text(
            (chart / "Chart.example.yaml")
            .read_text()
            .replace("name: REPO", "name: fixture")
            .replace("for REPO", "for fixture")
        )
        (chart / "values.yaml").write_text(
            "replicaCount: 1\n"
            "services:\n"
            "  envoy:\n"
            "    image: envoyproxy/envoy:v1.31-latest\n"
            "    port: 8080\n"
            "    envoyConfig: envoy/envoy.yaml\n"
        )
        envoy = chart / "envoy" / "envoy.yaml"
        envoy.parent.mkdir()
        envoy.write_text("static_resources: {}\n")

        result = subprocess.run(
            [helm, "template", "fixture", str(chart)],
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("kind: ConfigMap", result.stdout)
        self.assertIn("name: envoy-envoy-config", result.stdout)
        self.assertIn("static_resources: {}", result.stdout)


if __name__ == "__main__":
    unittest.main()
