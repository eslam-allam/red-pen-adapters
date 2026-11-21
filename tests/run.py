#!/usr/bin/env python3
"""Run the registry and adapter outcome test suites."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


def main() -> int:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(
        loader.discover(
            str(ROOT / "scripts" / "tests"),
            pattern="test_*.py",
            top_level_dir=str(ROOT / "scripts" / "tests"),
        )
    )
    suite.addTests(
        loader.discover(
            str(ROOT / "tests"),
            pattern="test_*.py",
            top_level_dir=str(ROOT / "tests"),
        )
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
