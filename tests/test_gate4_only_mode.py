"""Tests for ingest_agent --gate4-only CLI mode."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "ingest_agent.py"


class TestGate4OnlyCLI(unittest.TestCase):
    def test_help_mentions_flag(self):
        out = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=10,
        )
        self.assertEqual(out.returncode, 0)
        self.assertIn("--gate4-only", out.stdout)
        self.assertIn("--week", out.stdout)

    def test_contradictory_flags_error(self):
        # --gate4-only + --skip-gate4 → error
        out = subprocess.run(
            [sys.executable, str(SCRIPT), "--gate4-only", "--skip-gate4",
             "--week", "9999-W99"],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=10,
            env={"PATH": "/usr/bin:/bin", "APPLE_GENAI_MOCK": "1"},
        )
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("contradictory", (out.stderr + out.stdout).lower())

    def test_nonexistent_week_zero_eligible(self):
        out = subprocess.run(
            [sys.executable, str(SCRIPT), "--gate4-only", "--dry-run",
             "--week", "9999-W99"],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=15,
            env={"PATH": "/usr/bin:/bin", "APPLE_GENAI_MOCK": "1"},
        )
        self.assertEqual(out.returncode, 0)
        combined = out.stderr + out.stdout
        self.assertIn("0 eligible", combined)


if __name__ == "__main__":
    unittest.main()
