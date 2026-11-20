# Public keys

This folder contains **public keys only**. It must never contain a private key
or password.

## Naming

```
keys/<tier>-<year>.pub
keys/<tier>-<next-year>.pub
```

Examples: `official-2026.pub`, `official-2027.pub`, `community-2026.pub`,
`community-2027.pub`.

## Adding a key

1. Generate an encrypted keypair outside the repository (see
   [docs/key-rotation.md](../docs/key-rotation.md)).
2. Copy only the `.pub` file here.
3. Print its identity:

   ```sh
   python scripts/key_id.py --public-key keys/official-2026.pub --json
   ```

4. Record the key id, SHA-256 fingerprint, and owner in `SECURITY.md`.
5. Keep the `.key` and `.password` in the private operator vault (0600) and an
   encrypted offline backup.

The authoritative identity convention matches the app and minisign:

- key id: uppercase, byte-reversed 8-byte minisign id (for example
  `E7A93C572FF84DB5`);
- fingerprint: SHA-256 of the exact `.pub` file bytes, including the untrusted
  comment and trailing newline.

`tests/fixtures/g1-keys` cross-checks both values against the app's published
key table.

## Rotation

- Commit the next public key before its secret is used.
- Update the protected environment secret with the next key.
- Bump the registry sequence with the signing workflow.
- Never reuse a key between official and community registries.
- Never edit an old signed tag to change keys.

## Verification

```sh
python scripts/verify.py \
  --registry registry.json \
  --sig registry.json.minisig \
  --public-key keys/official-2026.pub \
  --config registry.config.json
```
