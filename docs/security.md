# Security model

The registry is a supply chain for code that runs against student files. A
registry compromise must not silently become code execution in the app.

## Assets

- the official and community minisign private keys and passwords;
- the signed registry index and its sequence;
- adapter manifests and scripts;
- the GitHub App key that can push `main` and tags;
- users' consent state for third-party registries.

## Trust boundaries

1. **GitHub repository** — reviewed by CODEOWNERS; protected `main` and tags.
2. **Signing workflow** — runs only from trusted `main`, inside a protected
   environment, with write access only in the signing job.
3. **Pinned signer** — a separate public repository checked out at a commit SHA;
   it is not modified by the PR being signed. After a signing secret is present,
   only this pinned code, the signer-owned minisign action, and trusted runner
   tools execute.
4. **minisign** — exact-byte signature; the key is password-encrypted.
5. **App verifier** — checks the signature before JSON parse, then checks every
   file hash from the verified index.
6. **Adapter sandbox** — separate lanes; the registry must not rely on the
   sandbox to compensate for an unsigned index.

## Threats and controls

| Threat | Control |
| --- | --- |
| Malicious PR adds code and gets it signed | PRs never access the signing environment; signing runs after merge from `main`; reviewer approval is required. |
| Compromised workflow edits the signer | Signer is checked out at a pinned SHA from a separate repository; the workflow references it explicitly. |
| Key or password leaks in logs | Password comes from the environment; PTY echo is disabled; all minisign output is discarded; only exit status is reported. |
| Unencrypted key in CI | `-W` is never used; the key is encrypted and decoded to a `0600` temp file. |
| Replay / split view | Strictly increasing `sequence`; `registry-v<sequence>` tag; app stores last sequence and digest per registry; expiry. |
| Wrong key or tier | Official and community keys are separate; environments are separate; app embeds both but maps them to fixed URLs. |
| Tampered manifest or script | Signed index lists SHA-256 for every file; app verifies each download. |
| Sequence race | Per-tier `concurrency`; tag existence check; latest tag plus current sequence. |
| Old tag rewritten | Tags are protected; never rotate by editing a tag; releases keep old artifacts. |
| Third-party registry impersonation | Unique `registryId`; app maps trust by URL and embedded key; unsigned/unknown requires explicit persistent consent. |
| Broad CI token | Top-level `contents: read`; signing job only `contents: write`; `persist-credentials: false`; minimal GitHub App. |
| Dependency compromise | Actions pinned by full SHA; Python validator pinned; minisign tarball pinned by SHA-256. |
| Expired index | Validator and app refuse an expired trusted registry; signing refreshes it. |

## Secret handling

Signing secrets:

- `MINISIGN_SECRET_KEY_B64` — base64 encrypted secret key;
- `MINISIGN_PASSWORD` — its password;
- `SIGNING_APP_PRIVATE_KEY` — minimal App key, scoped to the protected
  environment; the non-secret `SIGNING_APP_ID` is an environment variable.

Rules:

- secrets exist only in the protected environment, never as repository
  variables or PR-accessible secrets;
- no workflow triggered by `pull_request` may reference an environment;
- no secret is written to a file that is uploaded or committed;
- the temporary secret key is removed in an `always()` step;
- no one prints, `cat`s, or pastes a secret into a terminal, issue, or chat;
- rotate immediately if a secret may have been exposed.

`SIGNING_APP_ID` is not secret, but the App must have the minimum permissions
and be installed only on the registry repository (and the signer repository if
needed for checkout).

## Repository controls

- CODEOWNERS for schemas, scripts, keys, workflows, and the config.
- Required review and status checks on `main`.
- Protected `registry-v*` tags; no force push, no deletion.
- Secret scanning and push protection.
- Branch restriction for the protected environment: `main` and `registry-v*`.
- Required reviewers for the environment, including someone other than the
  change author.
- Audit log review for environment approvals and secret access.

## Supply chain

- `actions/checkout`, `actions/setup-python`, `actions/upload-artifact`, and
  `actions/create-github-app-token` are pinned by full commit SHA.
- minisign 0.12 is downloaded from the official release and checked against a
  pinned SHA-256 before extraction.
- `jsonschema` is pinned in CI.
- The public signer repository is pinned by SHA in `registry.config.json`; no
  cross-repository token is stored. CI requires the pin to be reachable from
  the signer's `main` before signing.
- The signer validates the full schema 6 itself: publisher is a string, adapter
  fields and files are checked, file paths reject `..`/colon/control, hashes
  and manifests are verified, and third-party registries may not use reserved
  official/community ids.
- No signing code is loaded from the commit being signed.

## App verification expectations

The app must fail closed when:

- the official/community signature is missing, malformed, or invalid;
- the key is wrong, unknown, or revoked;
- `registryId` or the trusted comment does not match;
- `sequence` is not greater than the stored sequence (replay);
- the index digest conflicts with a concurrently fetched view (split view);
- `expiresAt` has passed;
- a trusted file is missing a SHA-256 entry or its digest does not match;
- a third-party registry is unsigned/unknown-key and consent was not recorded.

An installed adapter may keep running after the index expires; new installs and
updates must not.

## Reporting

Report a suspected key compromise or signature bypass privately to the
maintainers listed in [SECURITY.md](../SECURITY.md). Do not open a public issue
with exploit details or key material.
