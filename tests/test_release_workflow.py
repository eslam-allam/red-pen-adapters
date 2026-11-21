from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
SIGN_WORKFLOW = ROOT / ".github" / "workflows" / "sign.yml"


class ReleaseWorkflowTests(unittest.TestCase):
    """Guard the release workflow's verification surface.

    The release job runs on protected tags and publishes trust artifacts, so
    these assertions are deliberately static: they fail if a later edit
    reintroduces a repo-local validator or drops a required check.
    """

    def setUp(self) -> None:
        self.text = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    def test_top_level_permissions_are_read_only(self) -> None:
        header = self.text.split("\njobs:", 1)[0]
        self.assertIn("permissions:\n  contents: read\n", header)
        self.assertNotIn("contents: write", header)

    def test_only_the_release_job_can_write(self) -> None:
        self.assertEqual(self.text.count("contents: write"), 1)
        self.assertIn("    permissions:\n      contents: write", self.text)

    def test_checks_out_the_pinned_signer(self) -> None:
        self.assertIn(
            "repository: ${{ steps.config.outputs.signer_repository }}", self.text
        )
        self.assertIn("ref: ${{ steps.config.outputs.signer_commit }}", self.text)
        self.assertIn("path: signer", self.text)
        self.assertIn("redpen_signing.cli check-pin", self.text)
        self.assertIn('--commit "$SIGNER_COMMIT"', self.text)
        self.assertIn('--expected-repository "$SIGNER_REPOSITORY"', self.text)
        self.assertIn(
            "uses: ./signer/.github/actions/install-minisign", self.text
        )
        self.assertIn("jsonschema==4.26.0", self.text)

    def test_requires_tag_identity_and_main_ancestry(self) -> None:
        self.assertIn('"$GITHUB_REF_NAME" = "$expected_tag"', self.text)
        self.assertIn('"$release_tag" = "$expected_tag"', self.text)
        self.assertIn("registry-v${release_sequence}", self.text)
        self.assertIn("git fetch --no-tags origin main", self.text)
        self.assertIn(
            'git merge-base --is-ancestor "$GITHUB_SHA" origin/main', self.text
        )

    def test_validates_with_the_pinned_signer_and_checksums(self) -> None:
        self.assertIn("redpen_signing.cli validate", self.text)
        self.assertIn("--require-signature", self.text)
        self.assertNotIn("--skip-release", self.text)
        self.assertIn("sha256sum --check --strict registry.sha256", self.text)
        self.assertIn("--verify-tag", self.text)

    def test_runs_no_repo_local_code(self) -> None:
        for forbidden in (
            "python scripts/",
            "from scripts",
            "uses: ./.github/",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.text)
        after_validation = self.text.split("redpen_signing.cli validate", 1)[1]
        self.assertNotIn("python scripts/", after_validation)
        self.assertNotIn("uses: ./.github/", after_validation)

    def test_signing_workflow_ignores_release_workflow_edits(self) -> None:
        sign_text = SIGN_WORKFLOW.read_text(encoding="utf-8")
        triggers = sign_text.split("\njobs:", 1)[0]
        self.assertNotIn(".github/workflows/release.yml", triggers)


if __name__ == "__main__":
    unittest.main()
