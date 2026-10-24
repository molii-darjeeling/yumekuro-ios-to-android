# Attribution and scope

This project contains independently written migration tools, runtime source, and research notes. It is not affiliated with the game's developers or publishers. No game APK, Unity asset, artwork, voice recording, player save, or third-party authentication credential is bundled.

The workflow uses external tools under their respective licenses: [UnityPy](https://github.com/K0lb3/UnityPy), [LIEF](https://github.com/lief-project/LIEF), [Frida](https://frida.re/), [Paramiko](https://www.paramiko.org/), [cryptography](https://cryptography.io/), Android SDK tools, and optionally [gplaydl](https://github.com/rehmatworks/gplaydl). Those dependencies are installed separately and are not relicensed by this project's MIT license.

The tiny null-cookie patch targets [gplaydl-authenticator](https://github.com/rehmatworks/gplaydl-authenticator), revision `32fc37413655d828437b435848f30523e40b7fd2`; it is not a distribution of that application. Respect the upstream app's source and license when building a repaired version. The optional Play module protocol was studied using [microG's AssetModule definitions](https://github.com/microg/GmsCore/blob/master/vending-app/src/main/proto/AssetModule.proto); generated files from that project are not copied here.

All game/media assets must come from an appropriate user-provided or otherwise authorized source. File hashes and native addresses identify the inspected build; they do not grant access to somebody else's account or missing content.
