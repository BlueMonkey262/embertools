"""embertools command-line entry point."""

from __future__ import annotations

import argparse
import sys

from .core import ui
from .core.adb import Adb, AdbError
from .core.device import Device
from .core.mod import Context, discover
from .core.state import State


def _connect(args) -> tuple[Adb, Device]:
    if Adb.any_unauthorized(args.adb):
        sys.exit("! Device shows as 'unauthorized' — tap 'Allow USB debugging' on the tablet.")
    devs = Adb.list_devices(args.adb)
    if not devs:
        sys.exit("! No device. Check the cable, enable Developer options → USB debugging, "
                 "then `adb devices`.")
    serial = args.serial or devs[0]
    if len(devs) > 1 and not args.serial:
        sys.exit(f"! Multiple devices {devs} — pass --serial <id>.")
    adb = Adb(serial=serial, adb_bin=args.adb)
    dev = Device.detect(adb)
    return adb, dev


def _ctx(adb, dev, opts) -> Context:
    return Context(adb=adb, dev=dev, state=State(adb), opts=opts)


def _statuses(mods, ctx) -> dict:
    out = {}
    for m in mods:
        try:
            out[m.meta.name] = m.status(ctx)
        except Exception as e:
            from .core.mod import Status
            out[m.meta.name] = Status(None, f"status error: {e}")
    return out


def cmd_list(args):
    adb, dev = _connect(args)
    ui.banner()
    print(f"  {dev.describe()}\n")
    mods = discover(dev)
    ctx = _ctx(adb, dev, vars(args))
    st = _statuses(mods, ctx)
    for m in mods:
        tag = f" {ui.ORANGE}· via embertools{ui.RESET}" if ctx.state.is_applied(m.meta.name) else ""
        print(f"  {ui.badge(st[m.meta.name])} {ui.BOLD}{m.meta.name}{ui.RESET}"
              f"  {ui.GREY}{m.meta.summary}{ui.RESET}{tag}")
        if st[m.meta.name].detail:
            print(f"     {ui.DIM}{st[m.meta.name].detail}{ui.RESET}")


def cmd_status(args):
    cmd_list(args)


def cmd_apply(args):
    adb, dev = _connect(args)
    ui.banner()
    print(f"  {dev.describe()}\n")
    mods = discover(dev)
    ctx = _ctx(adb, dev, vars(args))

    if args.mods:
        want = _select_named(mods, args.mods)
    else:
        want = ui.pick(mods, _statuses(mods, ctx))
    if not want:
        print("  nothing selected.")
        return

    want.sort(key=lambda m: m.meta.order)
    for m in want:
        if m.meta.risk != "low" and not args.yes and not ui.confirm(
                f"{m.meta.name} is {m.meta.risk} risk — continue?"):
            continue
        ui.rule()
        print(f"  {ui.ORANGE}▶ {m.meta.name}{ui.RESET}")
        try:
            m.apply(ctx)
        except Exception as e:
            print(f"  {ui.RED}✗ {m.meta.name} failed: {e}{ui.RESET}")
            if not args.keep_going:
                sys.exit(1)
    ui.rule()


def cmd_revert(args):
    adb, dev = _connect(args)
    ui.banner()
    print(f"  {dev.describe()}\n")
    all_mods = discover(dev)
    by_name = {m.meta.name: m for m in all_mods}
    ctx = _ctx(adb, dev, vars(args))
    applied = ctx.state.applied_mods()

    if args.mods == ["all"]:
        targets = applied
    elif args.mods:
        targets = args.mods
    elif applied:
        # interactive: pick which applied mods to revert
        chosen = ui.pick([by_name[n] for n in applied if n in by_name],
                         _statuses([by_name[n] for n in applied if n in by_name], ctx),
                         verb="revert")
        targets = [m.meta.name for m in chosen]
    else:
        print("  nothing applied to revert.")
        return

    if not targets:
        print("  nothing selected.")
        return
    for name in targets:
        m = by_name.get(name)
        if not m:
            print(f"  ? unknown / unavailable mod: {name}")
            continue
        ui.rule()
        print(f"  {ui.ORANGE}↩ {name}{ui.RESET}")
        try:
            m.revert(ctx)
        except Exception as e:
            print(f"  {ui.RED}✗ {e}{ui.RESET}")
    ui.rule()


def _select_named(mods, names):
    by = {m.meta.name: m for m in mods}
    out = []
    for n in names:
        if n == "all":
            return list(mods)
        if n in by:
            out.append(by[n])
        else:
            sys.exit(f"! no mod '{n}' for this device. `embertools list` to see options.")
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="embertools",
                                description="Modular, no-root toolkit for Amazon Fire tablets.")
    p.add_argument("--serial", help="adb device serial (if more than one attached)")
    p.add_argument("--adb", default="adb", help="path to adb")
    sub = p.add_subparsers(dest="cmd")

    lp = sub.add_parser("list", help="list mods available for the connected device")
    lp.set_defaults(func=cmd_list)

    sp = sub.add_parser("status", help="show current state of every mod")
    sp.set_defaults(func=cmd_status)

    ap = sub.add_parser("apply", help="apply one or more mods (interactive if none named)")
    ap.add_argument("mods", nargs="*", help="mod names, or 'all'")
    ap.add_argument("--launcher", default="nova",
                    help="launcher_swap target: nova | lawnchair | <pkg>/<HomeActivity>")
    ap.add_argument("--dns", default="adguard",
                    help="private_dns resolver: adguard | quad9 | mullvad-adblock | <hostname>")
    ap.add_argument("--keyboard", default="heliboard",
                    help="keyboard mod: heliboard | florisboard | unexpected | thumbkey | "
                         "anysoftkeyboard | simple | gboard")
    ap.add_argument("--reboot", action="store_true", help="reboot where a mod recommends it")
    ap.add_argument("--yes", action="store_true", help="don't prompt on medium/high-risk mods")
    ap.add_argument("--keep-going", action="store_true", help="continue if a mod fails")
    ap.set_defaults(func=cmd_apply)

    rp = sub.add_parser("revert",
                        help="revert mods: no args = interactive pick from applied; "
                             "'all' = every applied mod; or name them")
    rp.add_argument("mods", nargs="*")
    rp.set_defaults(func=cmd_revert)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if not getattr(args, "func", None):
        args = build_parser().parse_args((argv or []) + ["list"])
    try:
        args.func(args)
    except AdbError as e:
        sys.exit(f"! {e}")
    except KeyboardInterrupt:
        sys.exit("\n  cancelled.")
