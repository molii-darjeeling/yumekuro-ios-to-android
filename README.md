# Yumekuro: iOS to Android, guided by your AI

Preserve your own **Yume Shokunin to Wasureji no Kuroi Yousei** (Yumekuro / ゆめくろ) offline installation on Android, using the original Unity client, menus, artwork, animations, and your own progress.

This repository gives a computer-enabled AI a migration runbook, reusable research, and source tools. It does **not** contain the game, downloadable artwork, somebody else's save, login credentials, or a ready-to-install APK.

## Start here — no technical knowledge required

Send your AI this repository link and say:

> Teach me how to do this.

You may say that in your own language. The AI should read [AGENTS.md](AGENTS.md) and [the AI runbook](docs/AI_RUNBOOK.md), ask about your devices, and guide you one small step at a time. It must stop when you need to connect a cable, unlock a device, approve an installation, authorize an account, or check something on screen.

Use an AI with access to a local computer and terminal. A chat-only AI can explain the steps, but it cannot see your USB devices or perform the migration for you. Keep the original iOS game installed until the Android result is verified.

## What we are trying to produce

- A separate, locally signed Android installation that retains the original game's interface and Unity behavior.
- Your own player progress, owned cards, story records, home configuration, and guild progress.
- Locally available stories, cards, CG, character models, room furniture, and audio, with verified resource dependencies.
- Original animations wherever their required resources are complete. An original full-size static card can replace an unavailable animation; a thumbnail is never silently passed off as a full image.
- No routine Google Play resource download after all required local assets are prepared.

The route has been demonstrated on the exact **Android 5.0.1 / versionCode 551 / arm64-v8a** client described in [the build profile](profiles/yumekuro-5.0.1-arm64.json). This is a research-assisted workflow, not a universal one-click migrator. The extracted tools have local validation; a clean-device end-to-end run of this public package remains to be done. Other builds need their native addresses and layouts revalidated.

Missing source content stays missing unless an authentic matching resource can be recovered. This project cannot recreate an image, voice, or animation that was never downloaded and is no longer obtainable. Former online-only systems and complete battle behavior are outside the verified result.

## Do I have to jailbreak?

**Not automatically.** First examine an ordinary backup or an application-provided export. If it contains the needed save and resource files, use it. A backup that restores progress may still omit downloadable assets. iPhone and iPad have the same basic sandbox limitation; device supervision is a separate issue.

Only when necessary, discuss a currently supported way to read the full app container. Never infer jailbreak compatibility from an old tutorial or this repository's date. See [device and export decisions](docs/DEVICE_ACCESS.md).

## Reading order

| Reader | Start with |
| --- | --- |
| Beginner using an AI | Give the AI this repository link; [what to expect](docs/START_HERE.md) |
| AI taking over a session | [AGENTS.md](AGENTS.md), [AI runbook](docs/AI_RUNBOOK.md), then the private `SESSION.md` |
| Someone implementing the migration | [Migration procedure](docs/MIGRATION.md), [technical reference](docs/TECHNICAL_REFERENCE.md) |
| Missing images, voices, people, or menus | [Troubleshooting](docs/TROUBLESHOOTING.md) |
| Optional Google Play assets / login crash | [Google Play route](docs/GOOGLE_PLAY.md) |
| Final verification | [Acceptance checklist](docs/ACCEPTANCE.md) |

All instructions are in English; the AI should converse in the user's preferred language. User data belongs in an ignored local workspace, not in this repository. Read [privacy and publication rules](docs/PRIVACY.md) before sharing logs or opening an issue.

## Tools, not bundled game files

`tools/yume.py` provides initialization, environment inspection, archive indexing, input extraction, resource planning, and runtime generation. The remaining tools preserve the original conversion checks: Android-index MD5 where exact reconstruction is possible, non-shader and stream preservation for adaptations, real dependency closure, and phone SHA-256 checks.

The AI should install dependencies only after a clear user checkpoint. It should not ask a beginner to paste the entire command list at once. Detailed commands and the private workspace layout are in [MIGRATION.md](docs/MIGRATION.md).

Original tooling is under [MIT](LICENSE); third-party tools retain their own terms. Game content is not redistributed. See [NOTICE](NOTICE.md).
