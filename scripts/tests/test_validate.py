#!/usr/bin/env python3
"""Negative and positive tests for the registry validator helpers.

Run from the repository root:
  python scripts/tests/test_validate.py
"""

from __future__ import annotations

import json
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


class GeneratedToolTests(unittest.TestCase):
    def test_generated_adapter_tool_mismatch_is_rejected(self) -> None:
        manifest = {
            "id": "c",
            "miseTool": "conda:gcc",
            "runtimes": [{"tool": "conda:gxx", "version": "16.2.0"}],
        }
        errors = generated_tool_errors(manifest, {"c"}, "registry entry c")
        self.assertEqual(len(errors), 1)
        self.assertIn("conda:gcc", errors[0])
        self.assertIn("conda:gxx", errors[0])

    def test_generated_adapter_language_mismatch_is_rejected(self) -> None:
        manifest = {
            "id": "go",
            "language": "gcc",
            "runtimes": [{"tool": "go", "version": "latest"}],
        }
        errors = generated_tool_errors(manifest, {"go"}, "registry entry go")
        self.assertEqual(len(errors), 1)
        self.assertIn("uses 'gcc'", errors[0])
        self.assertIn("tool 'go'", errors[0])

    def test_generated_adapter_without_tool_hint_is_rejected(self) -> None:
        manifest = {
            "id": "r",
            "runtimes": [{"tool": "conda:r-base", "version": "4.6.2"}],
        }
        errors = generated_tool_errors(manifest, {"r"}, "registry entry r")
        self.assertEqual(len(errors), 1)
        self.assertIn("needs miseTool or language", errors[0])

    def test_matching_tool_passes(self) -> None:
        manifest = {
            "id": "c",
            "miseTool": "conda:gcc",
            "language": "c",
            "runtimes": [{"tool": "conda:gcc", "version": "16.2.0"}],
        }
        self.assertEqual(
            generated_tool_errors(manifest, {"c"}, "registry entry c"), []
        )

    def test_no_runtime_is_skipped(self) -> None:
        manifest = {"id": "bash", "language": "bash"}
        self.assertEqual(
            generated_tool_errors(manifest, {"bash"}, "registry entry bash"), []
        )


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
            "bootstrap": {"mise": "latest", "uv": "0.5.11"},
        }
        self.assertEqual(bootstrap_errors(manifest, "registry entry c"), [])


class BootstrapSchemaTests(unittest.TestCase):
    def test_bootstrap_semver_shapes(self) -> None:
        from jsonschema import Draft202012Validator

        root_schema = json.loads(
            (ROOT / "schemas" / "registry.schema.json").read_text(encoding="utf-8")
        )
        schema = {"$ref": "#/$defs/bootstrap", "$defs": root_schema["$defs"]}
        validator = Draft202012Validator(schema)
        for value in (
            {"mise": "latest"},
            {"mise": "1.2.3"},
            {"mise": "v1.2.3"},
            {"mise": "1.2.3-rc.1+build.1"},
            {"mise": "v1.2.3-rc.1+build.1"},
            {"mise": "latest", "uv": "0.5.11"},
            {"mise": None},
        ):
            with self.subTest(value=value):
                self.assertTrue(validator.is_valid(value), value)
        for value in (
            {"mise": "any-version"},
            {"mise": "01.2.3"},
            {"mise": "1.2"},
            {"mise": "1.2.3-01"},
            {"mise": "1.2.3-rc_1"},
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


if __name__ == "__main__":
    unittest.main()
