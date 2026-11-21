#!/usr/bin/env python3
"""Negative and positive tests for the registry validator helpers.

Run from the repository root:
  python scripts/tests/test_validate.py
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.validate import (  # noqa: E402
    bootstrap_errors,
    generated_tool_errors,
    python_runtime_errors,
)

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover - the validator reports the same error
    Draft202012Validator = None  # type: ignore[assignment]


class GeneratedToolTests(unittest.TestCase):
    def test_legacy_language_hint_is_rejected(self) -> None:
        manifest = {
            "id": "go",
            "language": "gcc",
            "runtimes": [{"tool": "go", "version": "latest"}],
        }
        errors = generated_tool_errors(manifest, {"go"}, "registry entry go")
        self.assertEqual(len(errors), 1)
        self.assertIn("language", errors[0])
        self.assertIn("runtimes[0].tool", errors[0])

    def test_legacy_misetool_hint_is_rejected(self) -> None:
        manifest = {
            "id": "c",
            "miseTool": "conda:gcc",
            "runtimes": [{"tool": "conda:gcc", "version": "16.2.0"}],
        }
        errors = generated_tool_errors(manifest, {"c"}, "registry entry c")
        self.assertEqual(len(errors), 1)
        self.assertIn("miseTool", errors[0])

    def test_generated_adapter_without_primary_tool_is_rejected(self) -> None:
        manifest = {"id": "r", "runtimes": [{"version": "4.6.2"}]}
        errors = generated_tool_errors(manifest, {"r"}, "registry entry r")
        self.assertEqual(len(errors), 1)
        self.assertIn("runtimes[0].tool", errors[0])

    def test_primary_runtime_tool_passes(self) -> None:
        manifest = {
            "id": "c",
            "runtimes": [{"tool": "conda:gcc", "version": "16.2.0"}],
        }
        self.assertEqual(
            generated_tool_errors(manifest, {"c"}, "registry entry c"), []
        )

    def test_no_runtime_is_skipped(self) -> None:
        manifest = {"id": "bash"}
        self.assertEqual(
            generated_tool_errors(manifest, {"bash"}, "registry entry bash"), []
        )


class ContractV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        if Draft202012Validator is None:
            self.skipTest("jsonschema is not installed")
        self.manifest_schema = json.loads(
            (ROOT / "schemas" / "manifest.schema.json").read_text(encoding="utf-8")
        )
        self.registry_schema = json.loads(
            (ROOT / "schemas" / "registry.schema.json").read_text(encoding="utf-8")
        )

    def manifest(self) -> dict:
        return {
            "schema": 5,
            "apiVersion": 2,
            "id": "example",
            "name": "Example",
            "version": "1.0.0",
            "description": "Example adapter.",
            "author": "Red Pen",
            "extensions": ["txt"],
            "appliesTo": ["file"],
            "output": {"kinds": ["diff"], "label": "Output"},
            "permissions": ["subprocess"],
            "settings": [
                {
                    "key": "version",
                    "label": "Version",
                    "type": "select",
                    "options": ["1.0.0"],
                    "default": "1.0.0",
                }
            ],
            "keyInput": [
                {"key": "expected", "label": "Expected", "type": "textarea"}
            ],
            "questionInput": [
                {"key": "inputFile", "label": "Input file", "type": "path"}
            ],
            "runtimes": [
                {"tool": "example", "setting": "version", "version": "1.0.0"}
            ],
            "bootstrap": {"mise": "latest"},
        }

    def entry(self) -> dict:
        return {
            "apiVersion": 2,
            "id": "example",
            "name": "Example",
            "version": "1.0.0",
            "description": "Example adapter.",
            "author": "Red Pen",
            "extensions": ["txt"],
            "appliesTo": ["file"],
            "output": {"kinds": ["diff"], "label": "Output"},
            "permissions": ["subprocess"],
            "settings": self.manifest()["settings"],
            "keyInput": self.manifest()["keyInput"],
            "questionInput": self.manifest()["questionInput"],
            "runtimes": self.manifest()["runtimes"],
            "bootstrap": {"mise": "latest"},
            "folder": "example",
            "files": [
                {"path": "manifest.json", "sha256": "a" * 64},
                {"path": "adapter.lua", "sha256": "b" * 64},
            ],
            "readmeUrl": "https://example.com/example/README.md",
        }

    def registry(self) -> dict:
        return {
            "schema": 7,
            "kind": "red-pen-adapters",
            "registryId": "example-registry",
            "publisher": "Example publisher",
            "sequence": 1,
            "issuedAt": "2026-11-20T21:00:00Z",
            "expiresAt": "2027-05-19T21:00:00Z",
            "adapters": [self.entry()],
        }

    def assert_valid(self, schema: dict, value: dict) -> None:
        errors = sorted(Draft202012Validator(schema).iter_errors(value), key=str)
        self.assertEqual([error.message for error in errors], [])

    def assert_invalid(self, schema: dict, value: dict) -> None:
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(value)))

    def test_v2_manifest_example_is_valid(self) -> None:
        self.assert_valid(self.manifest_schema, self.manifest())

    def test_manifest_schema_4_is_rejected(self) -> None:
        manifest = self.manifest()
        manifest["schema"] = 4
        self.assert_invalid(self.manifest_schema, manifest)

    def test_missing_manifest_api_version_is_rejected(self) -> None:
        manifest = self.manifest()
        manifest.pop("apiVersion")
        self.assert_invalid(self.manifest_schema, manifest)

    def test_legacy_permissions_are_rejected(self) -> None:
        for permission in (
            "environment",
            "files:read",
            "files:write",
            "directories",
        ):
            with self.subTest(permission=permission):
                manifest = self.manifest()
                manifest["permissions"] = [permission]
                self.assert_invalid(self.manifest_schema, manifest)

    def test_legacy_language_and_misetool_are_rejected(self) -> None:
        for field in ("language", "miseTool"):
            with self.subTest(field=field):
                manifest = self.manifest()
                manifest[field] = "example"
                self.assert_invalid(self.manifest_schema, manifest)

    def test_v2_registry_example_is_valid(self) -> None:
        self.assert_valid(self.registry_schema, self.registry())

    def test_registry_schema_6_is_rejected(self) -> None:
        registry = self.registry()
        registry["schema"] = 6
        self.assert_invalid(self.registry_schema, registry)

    def test_root_name_is_rejected(self) -> None:
        registry = self.registry()
        registry["name"] = "Legacy registry"
        self.assert_invalid(self.registry_schema, registry)

    def test_bare_string_files_are_rejected(self) -> None:
        registry = self.registry()
        registry["adapters"][0]["files"] = ["manifest.json", "adapter.lua"]
        self.assert_invalid(self.registry_schema, registry)

    def test_entry_api_version_is_required(self) -> None:
        registry = self.registry()
        registry["adapters"][0].pop("apiVersion")
        self.assert_invalid(self.registry_schema, registry)


class BootstrapTests(unittest.TestCase):
    def test_managed_runtime_requires_mise(self) -> None:
        manifest = {"runtimes": [{"tool": "conda:gcc"}]}
        errors = bootstrap_errors(manifest, "registry entry c")
        self.assertEqual(len(errors), 1)
        self.assertIn("non-empty bootstrap.mise", errors[0])
        manifest["bootstrap"] = {"uv": "0.5.11"}
        errors = bootstrap_errors(manifest, "registry entry c")
        self.assertEqual(len(errors), 1)
        manifest["bootstrap"] = {"mise": "latest"}
        self.assertEqual(bootstrap_errors(manifest, "registry entry c"), [])

    def test_bootstrap_without_runtime_is_rejected(self) -> None:
        manifest = {"bootstrap": {"mise": "latest"}}
        errors = bootstrap_errors(manifest, "registry entry example")
        self.assertEqual(len(errors), 1)
        self.assertIn("without a managed runtime", errors[0])

    def test_both_bootstrap_tools_allowed_with_runtime(self) -> None:
        manifest = {
            "runtimes": [{"tool": "conda:gcc"}],
            "bootstrap": {"mise": "latest", "uv": "0.13.9"},
        }
        self.assertEqual(bootstrap_errors(manifest, "registry entry c"), [])


class BootstrapSchemaTests(unittest.TestCase):
    def test_v2_bootstrap_pins(self) -> None:
        from jsonschema import Draft202012Validator

        root_schema = json.loads(
            (ROOT / "schemas" / "registry.schema.json").read_text(encoding="utf-8")
        )
        schema = {"$ref": "#/$defs/bootstrap", "$defs": root_schema["$defs"]}
        validator = Draft202012Validator(schema)
        for value in (
            {"mise": "latest"},
            {"mise": "2026.11.11"},
            {"uv": "latest"},
            {"uv": "0.13.9"},
            {"mise": "latest", "uv": "0.13.9"},
        ):
            with self.subTest(value=value):
                self.assertTrue(validator.is_valid(value), value)
        for value in (
            {"mise": "1.2.3"},
            {"mise": "v1.2.3"},
            {"mise": "any-version"},
            {"mise": None},
            {"uv": "0.5.11"},
            {"uv": True},
            {},
            {"mise": "latest", "extra": "1.2.3"},
        ):
            with self.subTest(value=value):
                self.assertFalse(validator.is_valid(value), value)


class PythonCeilingTests(unittest.TestCase):
    def test_python_316_is_rejected(self) -> None:
        manifest = {"id": "python"}
        settings = {
            "pythonVersion": {
                "type": "select",
                "options": ["3.13", "3.16"],
                "default": "3.13",
            }
        }
        errors = python_runtime_errors(manifest, settings, "registry entry python")
        self.assertEqual(len(errors), 1)
        self.assertIn("3.16", errors[0])

    def test_free_threaded_build_is_rejected(self) -> None:
        manifest = {"id": "python"}
        settings = {
            "pythonVersion": {
                "type": "select",
                "options": ["3.13", "3.13t"],
                "default": "3.13",
            }
        }
        errors = python_runtime_errors(manifest, settings, "registry entry python")
        self.assertEqual(len(errors), 1)
        self.assertIn("3.13t", errors[0])

    def test_supported_python_options_pass(self) -> None:
        manifest = {"id": "python"}
        settings = {
            "pythonVersion": {
                "type": "select",
                "options": ["3.8", "3.13", "3.15"],
                "default": "3.13",
            }
        }
        self.assertEqual(
            python_runtime_errors(manifest, settings, "registry entry python"), []
        )


class AdapterOutcomeProtocolTests(unittest.TestCase):
    def test_every_adapter_returns_an_explicit_status(self) -> None:
        adapters = sorted(
            path for path in ROOT.glob("*/adapter.lua") if path.parent.name != "scripts"
        )
        self.assertEqual(len(adapters), 26)
        for path in adapters:
            with self.subTest(adapter=path.parent.name):
                source = path.read_text(encoding="utf-8")
                self.assertIn('status = "graded"', source)
                self.assertNotRegex(source, r"app\.result\(\s*\{\s*error\s*=")


if __name__ == "__main__":
    unittest.main()
