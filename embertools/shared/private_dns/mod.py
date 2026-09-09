"""private_dns -- set system-wide Private DNS (DNS-over-TLS) to a filtering
resolver, which blocks ads and trackers across every app (including a
third-party launcher's own ad SDK).  No app, no VPN slot used.
"""

from __future__ import annotations

from embertools.core.mod import Mod, Meta, Status

RESOLVERS = {
    "adguard":  "dns.adguard-dns.com",
    "cloudflare-malware": "security.cloudflare-dns.com",
    "nextdns":  None,       # user supplies dns.nextdns.io/<id> via --dns
    "mullvad-adblock": "adblock.dns.mullvad.net",
    "quad9":    "dns.quad9.net",
}


class PrivateDns(Mod):
    meta = Meta(
        name="private_dns",
        summary="System-wide ad/tracker blocking via Private DNS (default: AdGuard)",
        supported=["*"],
        fireos=[7, 8],
        reversible=True,
        risk="low",
        confirm="Routes all DNS on the tablet through the chosen resolver. Continue?",
        order=40,
        options=[
            {"name": "dns", "label": "Resolver", "help": "Pick one or type a DoT hostname.",
             "type": "choice", "allow_custom": True,
             "choices": list(RESOLVERS), "default": "adguard"},
        ],
    )

    def _host(self, ctx) -> str:
        d = ctx.opts.get("dns", "adguard")
        if "." in d:                       # a raw hostname
            return d
        return RESOLVERS.get(d) or "dns.adguard-dns.com"

    def status(self, ctx) -> Status:
        mode = ctx.adb.get_global("private_dns_mode")
        spec = ctx.adb.get_global("private_dns_specifier")
        on = mode == "hostname" and bool(spec)
        return Status(on, f"{mode or 'off'} {spec}".strip())

    def apply(self, ctx) -> None:
        host = self._host(ctx)
        ctx.adb.put_global("private_dns_mode", "hostname")
        ctx.adb.put_global("private_dns_specifier", host)
        ctx.log(f"Private DNS -> {host}")
        ctx.log("verify: `adb shell ping -c1 doubleclick.net` should resolve to 0.0.0.0 / 127.0.0.1")
        ctx.state.mark_applied(self.meta.name, {"host": host})

    def revert(self, ctx) -> None:
        ctx.adb.put_global("private_dns_mode", "opportunistic")
        ctx.adb.shell("settings delete global private_dns_specifier")
        ctx.state.mark_reverted(self.meta.name)
        ctx.log("Private DNS back to automatic.")


MOD = PrivateDns()
