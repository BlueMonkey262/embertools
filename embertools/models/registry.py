"""Fire tablet model registry, keyed by ``ro.product.model``.

``fireos``: the major Fire OS line the device ships / tops out on.
  5 / 6  -> Android 5.1 / 7.1.  `pm disable-user com.amazon.firelauncher` still
           works there, so launcher_swap is not needed (use a legacy mod).
  7      -> Android 9.   launcher_swap (this project's instant-redirect method).
  8      -> Android 11.  launcher_swap needs the Fire OS 8 variant (WIP).

``quirks``: free-form flags mods may check (e.g. "tested", "low-ram", "fireos8").
"""

MODELS: dict[str, dict] = {
    # ---- Fire OS 7 / Android 9 — launcher_swap target devices ----
    "KFMAWI":  {"name": "Fire HD 10 (2019, 9th Gen)",     "soc": "MediaTek MT8183", "fireos": 7, "quirks": ["tested"]},
    "KFTRWI":  {"name": "Fire HD 10 (2021, 11th Gen)",    "soc": "MediaTek MT8183", "fireos": 7, "quirks": ["untested"]},
    "KFTRPWI": {"name": "Fire HD 10 Plus (2021)",         "soc": "MediaTek MT8183", "fireos": 7, "quirks": ["untested"]},
    "KFONWI":  {"name": "Fire HD 8 (2020, 10th Gen)",     "soc": "MediaTek MT8168", "fireos": 7, "quirks": ["untested"]},
    "KFMUWI":  {"name": "Fire 7 (2019, 9th Gen)",         "soc": "MediaTek MT8163", "fireos": 7, "quirks": ["untested", "low-ram"]},
    "KFKAWI":  {"name": "Fire HD 8 (2018, 8th Gen)",      "soc": "MediaTek MT8163", "fireos": 7, "quirks": ["untested"]},

    # ---- Fire OS 8 / Android 11 — launcher_swap variant WIP ----
    "KFQUWI":  {"name": "Fire 7 (2022, 12th Gen)",        "soc": "MediaTek MT8168",  "fireos": 8, "quirks": ["fireos8"]},
    "KFRAWI":  {"name": "Fire HD 8 (2022, 12th Gen)",     "soc": "MediaTek MT8169",  "fireos": 8, "quirks": ["fireos8"]},
    "KFRAPWI": {"name": "Fire HD 8 Plus (2022/2024)",     "soc": "MediaTek MT8169",  "fireos": 8, "quirks": ["fireos8"]},
    "KFRASWI": {"name": "Fire HD 8 (2024, 14th Gen)",     "soc": "MediaTek MT8169",  "fireos": 8, "quirks": ["fireos8"]},
    "KFTUWI":  {"name": "Fire HD 10 (2023, 13th Gen)",    "soc": "MediaTek MT8186",  "fireos": 8, "quirks": ["fireos8"]},
    "KFSNWI":  {"name": "Fire Max 11 (2023, 13th Gen)",   "soc": "MediaTek MT8188J", "fireos": 8, "quirks": ["fireos8"]},
}
