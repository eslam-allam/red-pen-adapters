# Key rotation and revocation

Signing keys are long-lived only by convention. Plan rotation before you need
it, keep the next key ready, and never rotate by editing an old tag.

## Key set

Keep four independent minisign keypairs outside the repository:

| Tier | Current | Next |
| --- | --- | --- |
| official | `official-2026` | `official-2027` |
| community | `community-2026` | `community-2027` |

Each key has:

- `<name>.key` — encrypted secret key, mode `0600`;
- `<name>.pub` — public key, committed as `keys/<name>.pub`;
- `<name>.password` — random 32+ byte password, mode `0600`;
- an encrypted offline backup.

Never share a key between tiers. Never commit a `.key` or `.password` file.
Record only uppercase key ids and SHA-256 fingerprints of the exact `.pub`
file bytes in `SECURITY.md`.

## Routine rotation

1. Generate and back up the next key (or use the pre-generated next key).
2. Commit `keys/<next>.pub` in a normal reviewed pull request.
3. Ship an app release that embeds the next public key **before** it is used.
4. Add the next key's secret and password to the protected environment under
   the same `MINISIGN_SECRET_KEY_B64` / `MINISIGN_PASSWORD` names.
5. Dispatch signing. The registry now uses the new key with a higher
   `sequence`.
6. Confirm the app verifies the new signature and still accepts the old
   sequence for rollback policy.
7. Retire the old key from the environment after the app release is adopted.
8. Keep the old public key in the app for verification of historical releases,
   but refuse it for new signatures once revoked.

Rotate on a schedule you can explain (for example yearly) and immediately on
suspicion of compromise.

## Emergency rotation / revocation

If a key may be compromised:

1. **Stop signing** with the affected environment; remove reviewers or disable
   the environment secret.
2. Switch the environment to the next key.
3. Bump `sequence` by more than the attacker could have used. The workflow
   already takes `max(registry.sequence, latest tag) + 1`; inspect tags and
   releases for unexpected values.
4. Ship an app patch that:
   - embeds the next public key;
   - marks the old key id as revoked;
   - refuses new indexes signed by the revoked key;
   - keeps installed adapters runnable until the user updates.
5. Publish a security advisory naming the revoked key id and fingerprint (never
   the secret).
6. Preserve old signed tags for audit. Do not rewrite or delete them.
7. Rotate the GitHub App credentials and signing environment secrets too.

A revoked key id must fail closed even if the signature is cryptographically
valid.

## Offline emergency signing

The normal path is automated. If GitHub is unavailable or the App is broken,
use an offline machine with the encrypted backup:

1. check out the exact `main` commit in a clean directory;
2. verify the pinned signer SHA and review the diff;
3. run the signer helper to prepare the next sequence and timestamps;
4. validate, sign, and verify locally with the public key;
5. write `registry.sha256` and `release.json`;
6. transfer only the signed artifacts to the release process;
7. record the incident, including who signed, where, and the key id.

Never copy a secret key onto a CI runner or a repository checkout. Never use
`-W`. Delete temporary key files and shell history where practical.

## Backups

- Keep at least two encrypted offline copies in separate locations.
- Store the password separately from the key.
- Test restoration on a schedule using a throwaway key, not a production key.
- Record the backup location, owner, and last test date in the private runbook,
  not in this repository.
- If a backup is lost, rotate; do not keep using a key with uncertain custody.

## What not to do

- Do not reuse a sequence for different bytes.
- Do not edit or move an existing `registry-v*` tag.
- Do not sign a registry from a pull-request checkout.
- Do not put a key or password in an artifact, cache, issue, chat, or log.
- Do not use an unencrypted key because automation is inconvenient.
- Do not let one key sign both official and community registries.
