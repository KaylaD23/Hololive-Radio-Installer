GTA Vice City PS2 bundled replacement payloads

Required files for the VC PS2 patch action:
- AMERICAN.GXT -> TEXT/AMERICAN.GXT
- VCPR.VB -> AUDIO/MUSIC/VCPR.VB
- FRONTEN2.TXD -> MODELS/FRONTEN2.TXD

Place all three files in this folder before building. The build script bundles every present file under Assets/, preserving its game-specific path. No root-level or cross-game fallback is used. All three files must be present and non-empty to enable patching.
