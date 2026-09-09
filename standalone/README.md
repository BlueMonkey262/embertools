# standalone/

`fire_launcher_swap.py` — the `launcher_swap` mod as **one self-contained file**,
for people who just want the instant-launcher trick and don't want to clone the
repo. It embeds the pre-built helper APK as base64, so it needs only `python3` +
`adb` (no JDK, no Android SDK).

```bash
python3 fire_launcher_swap.py                 # target = Nova
python3 fire_launcher_swap.py --launcher lawnchair
python3 fire_launcher_swap.py --status
python3 fire_launcher_swap.py --undo
python3 fire_launcher_swap.py --debloat
```

Gist-friendly: drop it in a GitHub gist and it works as-is.

The embedded APK is built from [`../embertools/shared/launcher_swap/helper/`](../embertools/shared/launcher_swap/helper).
To regenerate after changing the helper, run `../../tools/make_standalone.py`
(builds the helper, re-embeds it here).
