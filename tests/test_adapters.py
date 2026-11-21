from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "tests" / "lua" / "outcome_harness.lua"
LUA = shutil.which("lua") or shutil.which("lua5.4") or shutil.which("lua5.3")

SCENARIOS = (
    "graded",
    "previewed",
    "missing-key",
    "missing-input",
    "timeout",
    "failed-exit",
    "launch-failure",
)


def registry_adapters() -> list[dict]:
    registry = json.loads((ROOT / "registry.json").read_text(encoding="utf-8"))
    return registry["adapters"]


@unittest.skipUnless(LUA, "lua is not installed")
class AdapterOutcomeTests(unittest.TestCase):
    """Every published adapter must use the typed outcome protocol."""

    def run_adapter(self, adapter_id: str, kind: str, scenario: str) -> None:
        result = subprocess.run(
            [
                LUA,
                str(HARNESS),
                str(ROOT / adapter_id / "adapter.lua"),
                kind,
                scenario,
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_every_registry_adapter_returns_explicit_outcomes(self) -> None:
        adapters = registry_adapters()
        self.assertEqual(len(adapters), 26)
        for entry in adapters:
            adapter_id = entry["id"]
            kind = "logisim" if adapter_id == "logisim" else "language"
            for scenario in SCENARIOS:
                with self.subTest(adapter=adapter_id, scenario=scenario):
                    self.run_adapter(adapter_id, kind, scenario)

    def test_all_24_generated_adapters_are_present(self) -> None:
        config = json.loads(
            (ROOT / "scripts" / "languages.json").read_text(encoding="utf-8")
        )
        generated = [entry["id"] for entry in config["generated"]]
        self.assertEqual(len(generated), 24)
        for adapter_id in generated:
            with self.subTest(adapter=adapter_id):
                self.assertTrue((ROOT / adapter_id / "adapter.lua").is_file())
