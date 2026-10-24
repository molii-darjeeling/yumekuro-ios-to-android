# Device access: choose the least invasive sufficient route

## iPhone and iPad

For this migration they have the same relevant distinction: a normal backup/export is not unrestricted access to an app's private container. Device supervision can restrict connections or backups, but removing supervision is not a resource-extraction strategy.

Start with an existing computer backup, the app's own export, or supported file sharing. Inspect its actual contents. The goal is to obtain the original save **and** the downloaded game resources. Apple's [backup overview](https://support.apple.com/en-nz/108771) describes what ordinary backups include; [file sharing](https://support.apple.com/en-ca/119585) applies only to apps that expose it. Apps can also exclude recreatable/downloadable content from backup; see [Apple's file-system guidance](https://developer.apple.com/documentation/foundation/using-the-file-system-effectively).

Do not promise that "encrypted backup" means "all cached resources." Do not infer a usable export from the app's storage size alone. The AI should inspect a per-app file inventory and check whether the Octo cache/index and `Documents/Production` records are actually present.

## Full-container route when needed

The demonstrated full export used read-only SSH access to the game's app and data containers after supported system access had already been established. This repository does not jailbreak devices. The AI must look up the **current exact model/chip and iOS build** compatibility before suggesting such a route. For example, consult the [official Dopamine project](https://github.com/opa334/Dopamine) rather than assuming all versions work. Do not treat old screenshots or a successful installation of an app icon as compatibility proof.

Human checkpoint: explain the proposed tool and reason, possible reboots, and whether an ordinary export was insufficient; wait for the user's decision. Do not reset, restore, downgrade, remove management, or uninstall the game to obtain access.

If SSH is used:

1. Guide the user through installing/enabling the appropriate SSH service and choosing a terminal password, using the supported tool's current instructions.
2. Prefer a USB tunnel, e.g. an inspected `iproxy`/usbmux equivalent, or a trusted local network. The example config uses localhost port 2222 mapped to device port 22; do not assume such a tunnel already exists.
3. Verify the SSH host-key fingerprint through an independent device-side view before saving a `known_hosts` entry in `work/private/ssh_known_hosts`. Blindly accepting a scanned network key is not identity verification.
4. Enter the terminal password in the local terminal prompt, never in chat or a command-line argument. It is not the Apple Account password.
5. Discover app containers under `/var/containers/Bundle/Application/` and data containers under `/var/mobile/Containers/Data/Application/` (canonical `/private/var/...` paths can also appear). Inspect the `.app/Info.plist` and data container `.com.apple.mobile_container_manager.metadata.plist` identifiers. The intended identifier is `com.gcrest.yumekuro`; UUIDs differ on every installation.
6. Close the game on the source. Export the app-container **parent containing the `.app`** and the data-container contents separately. Do not follow dangling WebKit links or recursively copy unrelated apps.

The exporter accepts verified full paths as arguments. It does not discover identity by reusing another user's UUIDs. If a path resolves through `/var/mobile/...`, verify the canonical `/private/var/mobile/Containers/Data/Application/...` path before use.

## Android

The local destination does not require rooting Android in the demonstrated route. It is a separately signed debuggable application, so its private payload directory is accessible through `run-as` for that package.

Guide the human through enabling developer options and USB debugging for their actual phone. Use a data-capable cable and have the phone unlocked. The computer must read `adb devices -l` and see the selected device as `device`; `unauthorized` requires the human to approve the phone dialog. See [official ADB instructions](https://developer.android.com/tools/adb).

Do not assume USB installation is enabled just because debugging is authorized. Some phones show an additional installer or security prompt; pause for it. A missing dialog is not permission to loop installations indefinitely.

The included native profile is Android **user 0**, arm64-v8a. Private spaces, work profiles, and other Android users need explicit path/installation adaptations. Select the device serial in private config and use that serial consistently. If other tools contend for ADB, a dedicated server port can help, but it is not mandatory and must match every command.
