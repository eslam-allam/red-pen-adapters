from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
SIGN_WORKFLOW = ROOT / ".github" / "workflows" / "sign.yml"


class ReleaseWorkflowTests(unittest.TestCase):
    """Guard the release workflow's verification surface.

    The release job runs on protected tags and publishes trust artifacts, so
    these assertions are deliberately static: they fail if a later edit
    reintroduces a repo-local validator, weakens a gate, or drops a required
    check.
    """

    def setUp(self) -> None:
        self.text = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    def step_blocks(self) -> list[str]:
        starts = [match.start() for match in re.finditer(r"^      - name: ", self.text, re.M)]
        blocks = []
        for index, start in enumerate(starts):
            end = starts[index + 1] if index + 1 < len(starts) else len(self.text)
            blocks.append(self.text[start:end])
        return blocks

    def step_names(self) -> list[str]:
        return [block.splitlines()[0] for block in self.step_blocks()]

    def step(self, name: str) -> str:
        for block in self.step_blocks():
            if name in block.splitlines()[0]:
                return block
        self.fail(f"step {name!r} is missing")

    def test_top_level_permissions_are_read_only(self) -> None:
        header = self.text.split("\njobs:", 1)[0]
        self.assertIn("permissions:\n  contents: read\n", header)
        self.assertNotIn("contents: write", header)

    def test_only_the_release_job_can_write(self) -> None:
        self.assertEqual(self.text.count("contents: write"), 1)
        self.assertIn("    permissions:\n      contents: write", self.text)

    def test_has_no_secrets_or_environment(self) -> None:
        self.assertNotIn("secrets.", self.text)
        self.assertNotIn("environment:", self.text)

    def test_both_checkouts_disable_credentials(self) -> None:
        checkouts = [
            block
            for block in self.step_blocks()
            if "uses: actions/checkout@" in block
        ]
        self.assertEqual(len(checkouts), 2)
        for block in checkouts:
            with self.subTest(step=block.splitlines()[0]):
                self.assertIn("persist-credentials: false", block)

    def test_gate_and_validate_steps_are_unconditional(self) -> None:
        gates = (
            "Read pinned signer from configuration",
            "Require the pinned signer commit",
            "Assert tag identity and main ancestry",
            "Validate with the pinned signer",
            "Check checksums",
            "Create GitHub release",
        )
        for name in gates:
            block = self.step(name)
            with self.subTest(step=name):
                self.assertNotRegex(block, r"(?m)^        if:")
                self.assertNotRegex(block, r"(?m)^        continue-on-error:")

    def test_signer_allowlist_runs_before_signer_code(self) -> None:
        names = self.step_names()
        allowlist = next(
            index
            for index, name in enumerate(names)
            if "Read pinned signer from configuration" in name
        )
        checkout = next(
            index
            for index, name in enumerate(names)
            if "Checkout pinned signer by SHA" in name
        )
        check_pin = next(
            index
            for index, name in enumerate(names)
            if "Require the pinned signer commit" in name
        )
        minisign = next(
            index
            for index, name in enumerate(names)
            if "Install pinned minisign from the signer" in name
        )
        self.assertLess(allowlist, checkout)
        self.assertLess(checkout, check_pin)
        self.assertLess(check_pin, minisign)
        config_step = self.step("Read pinned signer from configuration")
        self.assertIn("official|community)", config_step)
        self.assertIn(
            "expected_signer=eslam-allam/red-pen-registry-signing", config_step
        )
        self.assertIn('"$signer_repo" = "$expected_signer"', config_step)
        self.assertIn('"$signer_repo" != "$source_repo"', config_step)

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
        self.assertIn(
            "git fetch --no-tags origin refs/heads/main:refs/remotes/origin/main",
            self.text,
        )
        self.assertIn(
            'git merge-base --is-ancestor "$GITHUB_SHA" refs/remotes/origin/main',
            self.text,
        )

    def test_validates_with_the_pinned_signer_and_checksums(self) -> None:
        self.assertIn("redpen_signing.cli validate", self.text)
        self.assertIn("--require-signature", self.text)
        self.assertNotIn("--skip-release", self.text)
        self.assertIn("sha256sum --check --strict registry.sha256", self.text)
        self.assertIn("--verify-tag", self.text)

    def test_requires_release_artifacts_before_publish(self) -> None:
        for artifact in ("release.json", "registry.json.minisig", "registry.sha256"):
            with self.subTest(artifact=artifact):
                self.assertIn(f"test -f {artifact}", self.text)
        self.assertLess(
            self.text.index("test -f release.json"),
            self.text.index("gh release create"),
        )

    def test_uploads_only_regular_public_keys(self) -> None:
        self.assertNotIn("keys/*.pub", self.text)
        self.assertIn(
            "find keys -maxdepth 1 -name '*.pub' ! -type f", self.text
        )
        self.assertIn(
            "find keys -maxdepth 1 -type f -name '*.pub'", self.text
        )
        self.assertIn('if [ -L "$KEY_FILE" ]', self.text)
        self.assertIn('grep -Fxq -- "$KEY_FILE"', self.text)
        self.assertIn('"${key_files[@]}"', self.text)

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
