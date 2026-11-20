# Publishing a registry

This is the operator checklist for turning the template into a registry.
Official and community registries follow the same steps with different keys,
environments, and trust tiers.

## 1. Create the repository

1. Use **Use this template** on
   `eslam-allam/red-pen-adapters-template`.
2. Choose the owner and name, for example `eslam-allam/red-pen-adapters` or
   `eslam-allam/red-pen-adapters-community`.
3. Keep `main` as the default branch.
4. Enable secret scanning and push protection.
5. Protect `main` and `registry-v*`:
   - require a pull request and review;
   - require status checks (`Validate registry` and `Sign dry run`);
   - block force pushes and deletion;
   - restrict who can push tags.

## 2. Set the registry identity

Edit `registry.config.json`:

```json
{
  "registryId": "red-pen-official",
  "tier": "official",
  "repository": "eslam-allam/red-pen-adapters",
  "readmeBaseUrl": "https://raw.githubusercontent.com/eslam-allam/red-pen-adapters/main",
  "publisher": "Red Pen",
  "requireSignature": true,
  "signing": {
    "enabled": true,
    "environment": "registry-signing-official",
    "keyFile": "keys/official-2026.pub",
    "expiresInDays": 180,
    "signerRepository": "eslam-allam/red-pen-registry-signing",
    "signerCommit": "<reviewed signer SHA>",
    "requiredReviewers": 1
  }
}
```

Rules:

- `registryId` is a globally unique lowercase slug, not a repository path. Official must be `red-pen-official`; community must be `red-pen-community`; third-party registries choose their own slug and may not use those reserved ids.
- `publisher` is a non-empty string (not an object) and is copied into `registry.json`.
- `official` and `community` require their fixed registry id (see above),
  `requireSignature: true`,
  `signing.enabled: true`, and the exact environment
  `registry-signing-<tier>`.
- `third-party` may be unsigned while bootstrapping, but any signed index must
  still verify.
- `readmeBaseUrl` must be
  `https://raw.githubusercontent.com/<owner>/<repo>/main` with no trailing
  slash.
- Keep `signerRepository` separate from the registry repository.

Then update `registry.json` identity fields (`name`, `publisher` as a string)
and run the formatter:

```sh
python scripts/registry.py format registry.json registry.config.json
python scripts/update.py
python scripts/validate.py
```

## 3. Generate keys outside the repository

Never generate a key inside the checkout. Use a temporary directory with mode
`0700` and `umask 077`, or an offline machine. See
[docs/key-rotation.md](docs/key-rotation.md).

For each current key:

1. create an encrypted minisign keypair with a random 32+ byte password;
2. keep `<name>.key` and `<name>.password` outside the repository (0600);
3. copy only `<name>.pub` into `keys/`;
4. record the uppercase key id and `.pub`-file SHA-256 fingerprint in
   `SECURITY.md`;
5. keep an encrypted offline backup;
6. generate a next key and commit only its public key.

Verify the public key:

```sh
python scripts/key_id.py --public-key keys/official-2026.pub --json
```

`keys/` must contain public keys only. `.gitignore` blocks `*.key` and
`*.password`.

## 4. Create the protected environment

Create `registry-signing-official` or `registry-signing-community` in the
registry repository:

- required reviewers: at least one owner who is not the PR author;
- deployment branches: `main` and tags matching `registry-v*`;
- no access from pull requests;
- environment secrets `MINISIGN_SECRET_KEY_B64`, `MINISIGN_PASSWORD`, and
  `SIGNING_APP_PRIVATE_KEY`;
- environment variable `SIGNING_APP_ID`.

Upload the secret key as base64 without printing it:

```sh
umask 077
base64 -w0 /secure/path/official-2026.key > "$TMPDIR/key.b64"
gh secret set MINISIGN_SECRET_KEY_B64 --env registry-signing-official --body-file "$TMPDIR/key.b64"
rm -f "$TMPDIR/key.b64"
```

Do not paste a key or password into a terminal, a file in the repository, an
issue, or a chat. Verify with `gh secret list --env ...` (names only).

The signing job writes that App token into a mode-`0700` `GIT_ASKPASS` helper
for tag fetch, commit, tag, and push. Private registries therefore work without
a personal access token. The helper is removed in an `always()` step; the token
is not written to the remote URL, process arguments, or logs.

Create a GitHub App with only `contents: write` on the registry repository.
Store `SIGNING_APP_ID` as an **environment variable** and
`SIGNING_APP_PRIVATE_KEY` as an **environment secret** in each protected
environment. Install the App only on the registry repository; the signer
repository is public and needs no extra token. Add the App to the bypass list
for required-review/status-check rules so it can push `main` and
`registry-v*` tags.

## 5. Pin the signer

Copy the reviewed commit SHA from
`eslam-allam/red-pen-registry-signing` into
`signing.signerCommit`. The workflow checks out exactly that commit. Bump it
only in a reviewed pull request.

## 6. Test key dry run

Before production signing:

1. Open a pull request. `Validate registry` and `Sign dry run` must pass.
2. Confirm no workflow triggered by `pull_request` references a signing
   environment or secret.
3. Dispatch `Sign registry` with `dry_run: true`. It must prepare, sign,
   verify, and reject tampering with a throwaway encrypted key.
4. Confirm the run did not push, tag, or read `MINISIGN_SECRET_KEY_B64`.

## 7. First production signature

Dispatch `Sign registry` (or merge the first adapter change to `main`). The
workflow:

- enters the protected environment and waits for approval;
- bumps `sequence` above the latest `registry-v*` tag (the template starts at
  `sequence: 1`, so the first signed release is `sequence: 2`);
- writes fresh `issuedAt`/`expiresAt`;
- signs and verifies;
- commits, tags `registry-v<sequence>`, and pushes;
- uploads `registry.json`, `registry.json.minisig`, `registry.sha256`, and
  `release.json`.

The tag push runs `Release signed registry`. Check that the release assets
match the workflow artifacts.

## 8. Verify as the app will

```sh
python scripts/verify.py \
  --registry registry.json \
  --sig registry.json.minisig \
  --public-key keys/official-2026.pub \
  --config registry.config.json --json
```

Then verify a second time after downloading the release asset, not the working
tree. Keep the `main` raw URL backward compatible for older app versions.

## 9. Add adapters

For each adapter:

1. copy the folder pattern from `example/`;
2. give it a unique lowercase id equal to the folder name;
3. bump `manifest.version` and the README version line;
4. run `python scripts/update.py` and `python scripts/validate.py`;
5. open a pull request with the adapter and updated `registry.json`.

The signer runs only after review and merge. A pull request cannot sign.

## Third-party registries

Use a unique `registryId` and your own key. Do not reuse official or community
key ids. The app embeds no third-party key, so users must consent to an unsigned
or unknown-key registry. Publish the public key and fingerprints so users can
compare them.

## Troubleshooting

- `registry.json is out of date`: run `python scripts/update.py`.
- `not deterministic JSON`: run `python scripts/registry.py format ...`.
- `has expired`: merge an adapter/config change or dispatch the signer; do not
  hand-edit timestamps.
- `tag already exists`: another run signed that sequence. Do not force-push;
  inspect the run and let the next run allocate a higher sequence.
- `minisign did not request a password`: the key is unencrypted or corrupt.
  Replace it with a properly encrypted key.
