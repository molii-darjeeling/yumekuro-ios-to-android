# Private data and publication

The public project is a reusable migration method and source toolkit. A new user supplies their own app installation, export, and authorization if needed. It is not a reference player's account.

Keep these private and out of Git history:

- Source app/data archives, backup databases, bundle binaries, artwork, voice clips, and raw movies.
- Original/encrypted/decrypted saves, preference plists, account identifiers, and character/progress lists associated with a player.
- Resource/save crypto constants derived locally; Google tokens, dispenser config, pairing codes, authenticated responses, signed URLs, and SSH/signing keys or passwords.
- Device serials/UDIDs, discovered container UUIDs, screenshots, runtime logs, absolute personal paths, and automatic coverage reports that reveal a user's account contents.
- Generated APKs and third-party binaries unless there is a separately reviewed distribution plan. They are not necessary for publishing the source workflow.

The ignored private workspace should be separate from tracked source. Before any publication, inspect an explicit tracked-file allowlist, scan text for secrets/personal values, and check that no archive, database, image, audio, video, native library, signing file, or large generated output is staged. Never use `git add` on the original rescue directory.

Common Android assets can be technically separated from saves and represented by the local supplement format. Such a pack must contain only resource rows authenticated against the original Android index, with no credentials or progress. Handle its provenance and distribution separately; this repository does not imply that an arbitrary user's full archive is safe to share. Merely stripping an account name from a ZIP is not a privacy review.

For a public issue, describe the device family/system version, supported profile or mismatch, exact generic logical resource name, and sanitized error type. Share a short redacted excerpt only if necessary. Do not attach full logs or a game save as the default debugging step.
