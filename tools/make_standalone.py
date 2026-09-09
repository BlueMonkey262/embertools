#!/usr/bin/env python3
"""Regenerate standalone/fire_launcher_swap.py.

Picks a fresh random helper package id, builds the helper APK with it, and
embeds it (base64) into the single-file script along with the matching
component constants.  Run after changing the helper or the launcher list.

    python3 tools/make_standalone.py
"""

import base64
import hashlib
import random
import re
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from embertools.core.build import build_apk  # noqa: E402

HELPER = ROOT / "embertools" / "shared" / "launcher_swap" / "helper"
STANDALONE = ROOT / "standalone" / "fire_launcher_swap.py"


def rand_seg(n: int) -> str:
    return random.choice(string.ascii_lowercase) + "".join(
        random.choices(string.ascii_lowercase + string.digits, k=n - 1))


def main() -> None:
    pkg = ".".join(rand_seg(random.randint(5, 8)) for _ in range(3))
    apk = build_apk(HELPER, package=pkg, force=True)
    data = apk.read_bytes()
    print(f"package {pkg}\nbuilt {apk.name}  {len(data)} bytes  "
          f"sha256={hashlib.sha256(data).hexdigest()[:16]}")

    b64 = base64.b64encode(data).decode()
    b64 = "\n".join(b64[i:i + 76] for i in range(0, len(b64), 76))

    src = STANDALONE.read_text()
    src = re.sub(r'^APP_ID\s*=\s*".*?"', f'APP_ID   = "{pkg}"', src, count=1, flags=re.M)
    src = re.sub(r'^# The helper APK .*$',
                 f'# The helper APK (~17 KB), base64.  Randomly-named package '
                 f'"{pkg}", debug-signed.', src, count=1, flags=re.M)
    src = re.sub(r'_APK_B64 = """\\\n.*?"""',
                 '_APK_B64 = """\\\\\n' + b64 + '"""', src, flags=re.S)
    STANDALONE.write_text(src)
    compile(src, str(STANDALONE), "exec")
    print(f"updated {STANDALONE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
