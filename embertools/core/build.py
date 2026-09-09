"""Build a helper APK from source, with no Gradle.

Pipeline: aapt2 compile/link -> javac -> d8 -> zipalign -> apksigner, using a
persistent debug keystore so rebuilds stay `adb install -r`-compatible.  The
Android SDK build-tools + one platform jar are bootstrapped into
~/.embertools/sdk on first use (or an existing SDK is reused).

Results are cached by a hash of the helper source tree.
"""

from __future__ import annotations

import hashlib
import os
import platform
import random
import shutil
import string
import subprocess
import tempfile
import zipfile
from pathlib import Path

HOME = Path.home() / ".embertools"
SDK_DIR = HOME / "sdk"
CACHE = HOME / "cache"
KEYSTORE = HOME / "debug.keystore"
HELPER_ID_FILE = HOME / "helper_id"

BUILD_TOOLS_VER = "34.0.0"
PLATFORM = "android-34"
CMDLINE_TOOLS_BUILD = "11076708"        # bump periodically; same number across OSes

# The helper source ships with this placeholder package; build_apk() rewrites it
# to a per-machine random id (persisted in HELPER_ID_FILE) so the app has no
# recognisable name for an OEM launcher blacklist to match.
PLACEHOLDER_PKG = "x.y.z"


def _rand_seg(n: int) -> str:
    return random.choice(string.ascii_lowercase) + "".join(
        random.choices(string.ascii_lowercase + string.digits, k=n - 1))


def helper_package() -> str:
    """A stable random package id for this machine's helper builds."""
    try:
        v = HELPER_ID_FILE.read_text().strip()
        if v.count(".") >= 1 and all(s.isidentifier() for s in v.split(".")):
            return v
    except Exception:
        pass
    pkg = ".".join(_rand_seg(random.randint(5, 8)) for _ in range(3))
    HOME.mkdir(parents=True, exist_ok=True)
    HELPER_ID_FILE.write_text(pkg + "\n")
    return pkg


class BuildError(RuntimeError):
    pass


# --------------------------------------------------------------------- tools --

def _java_home() -> Path:
    jh = os.environ.get("JAVA_HOME")
    if jh and (Path(jh) / "bin" / "javac").exists():
        return Path(jh)
    javac = shutil.which("javac")
    if javac:
        return Path(javac).resolve().parent.parent
    raise BuildError("No JDK found. Install a JDK (17+ recommended) or set JAVA_HOME.")


def _check_java(jh: Path) -> None:
    out = subprocess.run([str(jh / "bin" / "java"), "-version"],
                         capture_output=True, text=True).stderr
    import re
    m = re.search(r'version "(\d+)', out)
    if m and int(m.group(1)) < 11:
        raise BuildError(f"JDK {m.group(1)} is too old for the Android build tools; need 11+ (17 recommended).")


def _host_tag() -> str:
    s = platform.system().lower()
    return {"linux": "linux", "darwin": "mac", "windows": "win"}.get(s, "linux")


def _find_or_bootstrap_sdk() -> Path:
    for env in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        p = os.environ.get(env)
        if p and (Path(p) / "build-tools").exists():
            return Path(p)
    for cand in (Path.home() / "Android" / "Sdk", Path.home() / "Library" / "Android" / "sdk", SDK_DIR):
        if (cand / "build-tools").glob("*") and any((cand / "build-tools").glob("*")):
            return cand
    return _bootstrap_sdk()


def _bootstrap_sdk() -> Path:
    print("  bootstrapping Android SDK build-tools into ~/.embertools/sdk (~200 MB, one time)...")
    SDK_DIR.mkdir(parents=True, exist_ok=True)
    sdkmanager = _ensure_cmdline_tools()
    root = f"--sdk_root={SDK_DIR}"
    subprocess.run(f'yes | "{sdkmanager}" {root} --licenses', shell=True,
                   capture_output=True, text=True)
    r = subprocess.run([sdkmanager, root, "platform-tools",
                        f"build-tools;{BUILD_TOOLS_VER}", f"platforms;{PLATFORM}"],
                       capture_output=True, text=True, timeout=1800)
    if not (SDK_DIR / "build-tools" / BUILD_TOOLS_VER).exists():
        raise BuildError("SDK bootstrap failed:\n" + r.stdout[-2000:] + r.stderr[-2000:])
    return SDK_DIR


def _ensure_cmdline_tools() -> str:
    dest = SDK_DIR / "cmdline-tools" / "latest"
    bin_name = "sdkmanager.bat" if _host_tag() == "win" else "sdkmanager"
    if (dest / "bin" / bin_name).exists():
        return str(dest / "bin" / bin_name)
    import urllib.request
    url = (f"https://dl.google.com/android/repository/"
           f"commandlinetools-{_host_tag()}-{CMDLINE_TOOLS_BUILD}_latest.zip")
    zpath = SDK_DIR / "cmdline-tools.zip"
    print(f"  downloading {url}")
    urllib.request.urlretrieve(url, zpath)
    tmp = SDK_DIR / "_cmdline_tmp"
    with zipfile.ZipFile(zpath) as z:
        z.extractall(tmp)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(tmp / "cmdline-tools"), str(dest))
    shutil.rmtree(tmp, ignore_errors=True)
    zpath.unlink(missing_ok=True)
    os.chmod(dest / "bin" / bin_name, 0o755)
    return str(dest / "bin" / bin_name)


# ---------------------------------------------------------------------- build --

def _tree_hash(src: Path, extra: str = "") -> str:
    h = hashlib.sha256()
    h.update(extra.encode())
    for f in sorted(src.rglob("*")):
        if f.is_file() and "/out/" not in str(f):
            h.update(f.relative_to(src).as_posix().encode())
            h.update(f.read_bytes())
    return h.hexdigest()[:16]


def _materialise(helper_dir: Path, package: str, dest: Path) -> Path:
    """Copy the helper tree to `dest`, rewriting PLACEHOLDER_PKG -> package
    (in file contents and in the src/ package path)."""
    shutil.copytree(helper_dir, dest, ignore=shutil.ignore_patterns("out"))
    ph_path = PLACEHOLDER_PKG.replace(".", "/")
    new_path = package.replace(".", "/")
    for f in list(dest.rglob("*")):
        if f.is_file() and f.suffix in (".java", ".xml"):
            t = f.read_text()
            if PLACEHOLDER_PKG in t:
                f.write_text(t.replace(PLACEHOLDER_PKG, package))
    old_src = dest / "src" / ph_path
    if old_src.is_dir():
        target = dest / "src" / new_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_src), str(target))
        # prune now-empty placeholder parents
        p = dest / "src" / ph_path
        for parent in list(p.parents):
            if parent == dest / "src":
                break
            try:
                parent.rmdir()
            except OSError:
                pass
    return dest


def _ensure_keystore(jh: Path) -> None:
    if KEYSTORE.exists():
        return
    HOME.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(jh / "bin" / "keytool"), "-genkeypair", "-keystore", str(KEYSTORE),
                    "-storepass", "android", "-keypass", "android", "-alias", "embertools",
                    "-keyalg", "RSA", "-keysize", "2048", "-validity", "12000",
                    "-dname", "CN=embertools debug"], check=True, capture_output=True)


def build_apk(helper_dir: Path, package: str | None = None, force: bool = False) -> Path:
    """Build the helper APK with package id `package` (default: helper_package()).
    Returns the cached APK path."""
    helper_dir = Path(helper_dir)
    if not (helper_dir / "AndroidManifest.xml").exists():
        raise BuildError(f"no AndroidManifest.xml in {helper_dir}")
    package = package or helper_package()

    CACHE.mkdir(parents=True, exist_ok=True)
    tag = _tree_hash(helper_dir, extra=package)
    cached = CACHE / f"helper-{tag}.apk"
    if cached.exists() and not force:
        return cached

    jh = _java_home()
    _check_java(jh)
    sdk = _find_or_bootstrap_sdk()
    bt = sdk / "build-tools" / _pick_build_tools(sdk)
    android_jar = sdk / "platforms" / _pick_platform(sdk) / "android.jar"
    aapt2, d8, zipalign, apksigner = (bt / "aapt2", bt / "d8", bt / "zipalign", bt / "apksigner")
    javac = jh / "bin" / "javac"

    def run(*args, **kw):
        r = subprocess.run([str(a) for a in args], capture_output=True, text=True, **kw)
        if r.returncode != 0:
            raise BuildError(f"{Path(str(args[0])).name} failed:\n{r.stdout}\n{r.stderr}")
        return r

    with tempfile.TemporaryDirectory(prefix="embertools-build-") as td:
        work = _materialise(helper_dir, package, Path(td) / "helper")
        manifest = work / "AndroidManifest.xml"
        out = work / "out"
        (out / "gen").mkdir(parents=True)
        (out / "classes").mkdir(parents=True)

        link_res = []
        if (work / "res").exists():
            run(aapt2, "compile", "--dir", work / "res", "-o", out / "res.zip")
            link_res = ["-R", str(out / "res.zip")]

        run(aapt2, "link", "-o", out / "base.apk", "-I", android_jar,
            "--manifest", manifest, *link_res, "--java", out / "gen",
            "--min-sdk-version", "22", "--target-sdk-version", "28", "--auto-add-overlay")

        srcs = [str(p) for p in list((work / "src").rglob("*.java")) + list((out / "gen").rglob("*.java"))]
        run(javac, "-source", "8", "-target", "8", "-encoding", "UTF-8", "-nowarn",
            "-Xlint:-options", "-bootclasspath", android_jar, "-cp", android_jar,
            "-d", out / "classes", *srcs)

        classes = [str(p) for p in (out / "classes").rglob("*.class")]
        run(d8, "--min-api", "22", "--lib", android_jar, "--output", str(out), *classes)

        app = out / "app.apk"
        shutil.copy(out / "base.apk", app)
        with zipfile.ZipFile(app, "a", zipfile.ZIP_DEFLATED) as z:
            z.write(out / "classes.dex", "classes.dex")

        aligned = out / "app-aligned.apk"
        run(zipalign, "-f", "-p", "4", app, aligned)
        _ensure_keystore(jh)
        run(apksigner, "sign", "--ks", KEYSTORE, "--ks-pass", "pass:android",
            "--key-pass", "pass:android", "--out", cached, aligned)
    return cached


def _pick_build_tools(sdk: Path) -> str:
    have = sorted((p.name for p in (sdk / "build-tools").glob("*")), reverse=True)
    if not have:
        raise BuildError("no build-tools in SDK")
    return BUILD_TOOLS_VER if BUILD_TOOLS_VER in have else have[0]


def _pick_platform(sdk: Path) -> str:
    have = sorted((p.name for p in (sdk / "platforms").glob("android-*")), reverse=True)
    if not have:
        raise BuildError("no platform in SDK")
    return PLATFORM if PLATFORM in have else have[0]
