# Signing and verification

Red Pen signs the **exact bytes** of `registry.json` with minisign. The detached
signature lives in `registry.json.minisig`; the app verifies the index before
parsing it, then trusts only the SHA-256 entries in that signed index for
manifests and adapter files.

## What is signed

- Registry kind: `red-pen-adapters`, schema `6`.
- Algorithm: minisign 0.12 Ed25519, normal (not legacy) signatures.
- Message: `registry.json` exactly as committed. There is no re-serialisation.
- Sidecar: `registry.json.minisig`, at most 16 KiB.
- Trusted comment: exactly `registryId=<id> sequence=<n>`.
- The trusted comment must match `registry.json` and
  `registry.config.json`. The app refuses a mismatch.
- `sequence` strictly increases. The workflow tags `registry-v<sequence>`.
- `issuedAt` and `expiresAt` are UTC, seconds precision. The app refuses an
  expired trusted registry; an installed adapter may still run.

The signature covers the index, not the whole repository. The index covers
every adapter file by SHA-256. Never reuse a sequence, and never edit a tag.

## Keys and environments

Official and community registries use **different keys in separate GitHub
environments**. A key must never sign both tiers.

Key identity follows minisign/G1 exactly: the key id is the uppercase,
byte-reversed 8-byte minisign id, and the fingerprint is the SHA-256 of the
exact `.pub` file bytes (including its comment and trailing newline).
`tests/fixtures/g1-keys` cross-checks these against the app's published table.

| Tier | Environment | Secrets |
| --- | --- | --- |
| official | `registry-signing-official` | `MINISIGN_SECRET_KEY_B64`, `MINISIGN_PASSWORD` |
| community | `registry-signing-community` | `MINISIGN_SECRET_KEY_B64`, `MINISIGN_PASSWORD` |

Protect each environment with:

- required reviewers (at least one owner who is not the pull-request author);
- deployment branches/tags limited to `main` and `registry-v*`;
- no access from pull requests;
- environment-scoped secrets only;
- audit log review.

`MINISIGN_SECRET_KEY_B64` is the base64 of the encrypted minisign secret key.
`MINISIGN_PASSWORD` is its password. Both are read from the environment inside
the protected job and are never placed in argv, a repository file, an artifact,
or a log.

The production workflow also uses environment-scoped GitHub App credentials:

- environment variable `SIGNING_APP_ID`;
- environment secret `SIGNING_APP_PRIVATE_KEY`.

The App is installed on this registry repository with the minimum
`contents: write` permission. It mints a short-lived installation token with
`actions/create-github-app-token` (pinned by SHA), which checks out `main`,
pushes the signed commit, and pushes the `registry-v<sequence>` tag. Add the
App to the branch/tag ruleset bypass list when required review or status checks
would otherwise block the push. Do not use a broad personal access token.

Create `SIGNING_APP_ID` and `SIGNING_APP_PRIVATE_KEY` in each protected
environment (`registry-signing-official`, `registry-signing-community`), not as
repository-wide secrets. No PR workflow can see them.

## Pinned signer

`registry.config.json` records:

```json
"signerRepository": "eslam-allam/red-pen-registry-signing",
"signerCommit": "<40-character SHA>"
```

The signing job checks out that repository at that SHA and runs its
`redpen_signing` package. The signer repository is **public** and contains no
secrets, so the default checkout can read it without a cross-repository token.
It never runs signing code from the pull request or from the commit being
signed. Review and bump the pin deliberately in a normal pull request.

## Password handling

minisign 0.12 reads the password from a terminal. The signer therefore:

1. decodes `MINISIGN_SECRET_KEY_B64` to a mode-`0600` file under
   `$RUNNER_TEMP`;
2. opens a pseudo-terminal, disables `ECHO`, and starts minisign;
3. feeds `MINISIGN_PASSWORD` only when minisign asks for a password;
4. **discards every byte minisign writes**, because a PTY can echo KDF or
   password material;
5. kills the process group on timeout and reports only an exit status;
6. removes the temporary key in an `always()` step.

Do not use `minisign -W`. It creates an unencrypted key and is rejected by the
production procedure.

## Workflow sequence

`.github/workflows/sign.yml` runs on a push to `main` (including adapter and
config changes) or manually. A pull request never triggers it.

1. **Preflight** (no environment, `contents: read`): read the config with the
   registry's settings helper, check out the signer at the pinned SHA, require
   that SHA to be reachable from the signer repository's `main`, and run the
   pinned signer's full schema 7 / manifest 5 / API 2 tree validation. No
   secret exists yet.
2. **Signing job**: enter the environment from the config
   (`registry-signing-official` or `registry-signing-community`), with
   `contents: write` only in this job and `persist-credentials: false`.
3. Check out the registry at `main` and the signer at the pinned SHA. The
   signer is public and needs no cross-repository token.
4. Install the pinned signer validation dependency and the signer-owned,
   SHA-pinned minisign action. Nothing from the registry checkout is executed
   after this point.
5. Configure an ephemeral `GIT_ASKPASS` helper so tag fetch and push work on a
   private registry too. The signer writes the App token into a mode-`0700`
   helper at creation, uses it for fetch/commit/tag/push, and removes it in an
   `always()` step. The token is not written to the remote URL, argv, or logs.
6. Refresh tags **before** allocating a sequence.
7. Decode the key to `$RUNNER_TEMP` mode `0600`.
8. `prepare`: set `sequence = max(current, latest tag) + 1`, set `issuedAt` to
   now and `expiresAt` to now plus `signing.expiresInDays`, and write
   deterministic bytes. Assert the new sequence is above the refreshed latest
   tag and that the tag does not already exist.
9. Validate the prepared tree with the pinned signer (full schema 7 /
   manifest 5 / API 2, hashes, manifests, release metadata rules). Run signer
   commands from the signer checkout with `python -P` / `PYTHONSAFEPATH=1`,
   `PYTHONPATH` pointing at the signer, and absolute registry paths. A fake
   `redpen_signing` package in the registry commit cannot shadow the pinned
   signer.
10. Sign the exact bytes with the environment key.
11. Verify immediately with the committed public key and trusted comment.
12. Write `release.json` and `registry.sha256`; the signer asserts registry id,
    sequence, tag, tier, signer commit, timestamps, both digests, and key
    identity agree. Pre-signing validation uses `--skip-release`; release
    validation checks the fresh metadata.
13. Upload `registry.json`, `registry.json.minisig`, `registry.sha256`, and
    `release.json`.
14. Commit, tag `registry-v<sequence>`, and push using the minimal App token.
15. Remove the temporary key and askpass helper.

Isolation rule: after `MINISIGN_SECRET_KEY_B64` or `MINISIGN_PASSWORD` is
present, the job runs only pinned signer code, the pinned minisign binary, and
trusted runner tools (`git`, `sha256sum`, and SHA-pinned actions). It does not
execute `scripts/`, local actions, or any other file from the registry commit.

The signing job has `concurrency: registry-signing-<tier>`, so two runs cannot
allocate the same sequence. The commit message starts with
`chore(registry): sign sequence`, and the workflow skips signing for such a
commit to avoid a loop.

A manual dispatch with `dry_run: true` runs a separate read-only job. It
generates a throwaway **encrypted** key, prepares a copy, signs, verifies, and
confirms that a tampered registry fails. It never reads the signing
environment or production secrets.

## Pin reachability

CI checks the pinned signer SHA when signing is enabled:

```sh
cd signer
python -P -m redpen_signing.cli check-pin --repo-dir . --commit <sha>
```

The command verifies the checkout's `origin` is the expected signer repository,
unshallows if necessary, fetches the signer repository's `main`, and fails
unless the pinned commit is an ancestor of it. Official and community builds
hardcode `eslam-allam/red-pen-registry-signing`; third-party signing requires
the repository variable `SIGNER_REPOSITORY_ALLOWLIST`. After merging a signer
change, bump `signing.signerCommit` to the resulting signer `main` commit. A
branch-only SHA is not a final pin.

## Verifying locally

```sh
# Print key identity (safe to publish)
python scripts/key_id.py --public-key keys/official-2026.pub --json

# Verify exact bytes, registry id, sequence, and expiry
python scripts/verify.py \
  --registry registry.json \
  --sig registry.json.minisig \
  --public-key keys/official-2026.pub \
  --config registry.config.json --json

# Validate structure, hashes, and release metadata. The signature is not
# checked by default because a PR's index changes before the signer runs.
python scripts/validate.py

# Pre-signing / PR mode: ignore a release.json that still describes old bytes
python scripts/validate.py --skip-release

# Verify the sidecar when present; or require it (release mode)
python scripts/validate.py --verify-signature
python scripts/validate.py --require-signature
```

To test without a production key:

```sh
python scripts/sign.py --test-key
```

This creates an encrypted test key in a temporary directory, signs a prepared
copy, verifies it, tampers with the bytes, and checks that verification fails.

## App-side rules

The app must:

- fetch the index and sidecar with a size cap, verify before JSON parse, and
  retry once on CDN skew;
- require a valid signature for official and community registries;
- reject a missing, malformed, wrong-key, revoked, expired, replayed, or
  split-view index;
- check `registryId`, `sequence`, and the trusted comment;
- accept an unsigned or unknown-key third-party index only after explicit
  persistent consent;
- authenticate every downloaded file against the signed SHA-256 entry;
- install from the verified cached index, never from a frontend-supplied manifest.

## Artifacts and release

`release.json` contains the registry id, tier, sequence, tag, timestamps,
`registrySha256`, `signatureSha256`, key id, public-key fingerprint, signer
commit, workflow run, and generation time. It is written deterministically.

The tag push runs `.github/workflows/release.yml`, which validates
`--require-signature`, checks `registry.sha256` and `release.json`, verifies
with the committed public key, and creates a GitHub release with the index,
signature, checksum, metadata, and public keys.
