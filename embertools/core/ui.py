"""Minimal terminal UI helpers -- plain stdlib, colour if the terminal supports it."""

from __future__ import annotations

import os
import sys

_TTY = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
# orange / grey palette
ORANGE = "\033[38;5;208m" if _TTY else ""
GREY = "\033[38;5;245m" if _TTY else ""
DIM = "\033[2m" if _TTY else ""
BOLD = "\033[1m" if _TTY else ""
GREEN = "\033[38;5;114m" if _TTY else ""
RED = "\033[38;5;203m" if _TTY else ""
RESET = "\033[0m" if _TTY else ""


def banner() -> None:
    print(f"{ORANGE}{BOLD}  embertools{RESET}{GREY}  ·  reclaim your Fire tablet{RESET}\n")


def rule() -> None:
    print(f"{GREY}{'─' * 60}{RESET}")


def badge(status) -> str:
    if status.applied is True:
        return f"{GREEN}●{RESET}"
    if status.applied is False:
        return f"{GREY}○{RESET}"
    return f"{GREY}◍{RESET}"


def pick(mods, statuses, verb: str = "apply") -> list:
    """Interactive multi-select. Returns chosen mods."""
    print(f"{GREY}  pick mods to {verb} (e.g. '1 3', 'all', or blank to cancel){RESET}\n")
    for i, m in enumerate(mods, 1):
        st = statuses[m.meta.name]
        risk = "" if m.meta.risk == "low" else f" {ORANGE}[{m.meta.risk} risk]{RESET}"
        print(f"  {badge(st)} {ORANGE}{i:>2}{RESET}  {BOLD}{m.meta.name}{RESET}{risk}")
        print(f"       {GREY}{m.meta.summary}{RESET}")
        if st.detail:
            print(f"       {DIM}{st.detail}{RESET}")
    print()
    raw = input(f"{ORANGE}  > {RESET}").strip().lower()
    if not raw:
        return []
    if raw == "all":
        return list(mods)
    out = []
    for tok in raw.replace(",", " ").split():
        if tok.isdigit() and 1 <= int(tok) <= len(mods):
            out.append(mods[int(tok) - 1])
    return out


def confirm(prompt: str) -> bool:
    return input(f"{ORANGE}  {prompt} [y/N] {RESET}").strip().lower() in ("y", "yes")
