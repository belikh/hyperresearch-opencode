"""SSRF containment for agent-chosen fetch URLs (P1-4 hardening).

Fetch URLs enter this program from agent output and third-party API
responses, so they are attacker-influenceable. Every direct-fetch lane
(crawl4ai PDF download, builtin HTML) validates through here BEFORE any
request is issued, and again on every redirect target, so internal
infrastructure (loopback, RFC1918, link-local metadata services, …) cannot be
probed or exfiltrated through a vault-bound WebResult.

Checks enforced by :func:`validate_url_public`, in order:

- scheme must be http/https (file://, gopher://, ftp:// … rejected);
- hostname present, no embedded credentials;
- the hostname must resolve via ``socket.getaddrinfo``, and EVERY address it
  resolves to must be globally routable. This rejects loopback (127/8, ::1),
  private (RFC1918, fc00::/7 ULA), link-local (169.254/16 including the
  169.254.169.254 cloud-metadata service, fe80::/10), unspecified (0.0.0.0,
  ::), documentation/benchmarking/reserved ranges, and multicast — anything
  ``ipaddress`` does not consider global fails closed.

Known limitation (documented, out of scope): DNS rebinding. The resolution
here and the connection made afterwards are two separate events, so an
attacker-controlled authoritative DNS server can answer differently between
them. Closing that TOCTOU requires pinning the validated address at connect
time; the threat model for this tool treats it as accepted residual risk.
"""

from __future__ import annotations

import ipaddress
import socket
import urllib.request
from typing import Any
from urllib.parse import urljoin, urlparse

# Redirect statuses httpx would have auto-followed for us.
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_ALLOWED_SCHEMES = frozenset({"http", "https"})

MAX_REDIRECT_HOPS = 5


class UnsafeUrlError(ValueError):
    """A URL failed public-address validation (SSRF guard). The message says why."""


def _address_kind(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str:
    """Human-readable class of a blocked address, for the rejection message."""
    if ip.is_loopback:
        return "loopback"
    if ip.is_link_local:
        return "link-local"
    if ip.is_unspecified:
        return "unspecified"
    if ip.is_multicast:
        return "multicast"
    if ip.is_private:
        return "private"
    return "non-globally-routable"


def validate_url_public(url: str) -> str:
    """Validate that `url` is http(s) resolving only to globally routable IPs.

    Returns the URL unchanged when safe; raises :class:`UnsafeUrlError`
    otherwise. See the module docstring for the exact rule set (and the
    documented DNS-rebinding limitation).
    """
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise UnsafeUrlError(f"unparseable URL {url!r}: {exc}") from exc

    scheme = parsed.scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise UnsafeUrlError(f"scheme {scheme!r} is not http(s): {url!r}")

    host = parsed.hostname
    if not host:
        raise UnsafeUrlError(f"URL has no hostname: {url!r}")
    if parsed.username or parsed.password:
        raise UnsafeUrlError(f"credentials embedded in URL: {url!r}")

    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as exc:
        raise UnsafeUrlError(f"DNS resolution failed for {host!r}: {exc}") from exc

    for info in infos:
        # str() coercion mirrors core/oa.py::check_oa_url — typeshed types the
        # address field as `str | int`; the scope-id strip handles IPv6
        # link-local zone indices ("%eth0") that ipaddress cannot parse.
        addr = str(info[4][0])
        try:
            ip = ipaddress.ip_address(addr.split("%")[0])
        except ValueError:
            raise UnsafeUrlError(
                f"host {host!r} resolved to unparseable address {addr!r}"
            ) from None
        if ip.is_multicast or not ip.is_global:
            kind = _address_kind(ip)
            raise UnsafeUrlError(
                f"host {host!r} resolves to non-public address "
                f"{ip} ({kind}); blocked"
            )

    return url


def guarded_get(
    url: str,
    *,
    timeout: float,
    headers: dict[str, str] | None = None,
    verify: bool = True,
    max_hops: int = MAX_REDIRECT_HOPS,
) -> Any:
    """httpx GET with SSRF validation of the start URL AND every redirect hop.

    Replaces ``httpx.get(..., follow_redirects=True)``, which followed a
    poisoned Location header straight into loopback without ever re-checking.
    Each hop re-validates before its request, so a redirect chain that leaves
    the public internet dies at the first bad target with an
    :class:`UnsafeUrlError`. More than `max_hops` redirects also raises.

    Returns the terminal httpx.Response. `-> Any` keeps callers decoupled from
    the httpx Response type across versions (mirrors `_import_pymupdf`).
    """
    import httpx

    current = url
    for _hop in range(max_hops + 1):
        validate_url_public(current)
        resp = httpx.get(
            current,
            follow_redirects=False,
            timeout=timeout,
            verify=verify,
            headers=headers,
        )
        if resp.status_code in _REDIRECT_STATUSES and "location" in resp.headers:
            # Relative Locations resolve against the hop that issued them.
            current = urljoin(str(resp.url), resp.headers["location"])
            continue
        return resp
    raise UnsafeUrlError(f"more than {max_hops} redirects while fetching {url!r}")


class GuardedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """urllib redirect handler that re-validates every hop before following.

    The default handler followed redirects blindly (the builtin provider's
    fallback lane). Here each new location goes through the same public-address
    rule as the start URL, raising :class:`UnsafeUrlError` instead of issuing
    the next request.
    """

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,  # typeshed's fp/header types churn between releases; Any keeps
        code: int,  # the override stable under --strict, same policy as builtin.py
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        validate_url_public(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def guarded_urlopen(url: str, *, timeout: float) -> Any:
    """urllib.request.urlopen behind :class:`GuardedRedirectHandler`.

    The start URL is validated up front; each redirect hop is validated inside
    the opener. Typeshed types urlopen()'s return as IO[Any]-shaped with no
    `.url`, so `-> Any` matches the existing builtin.py convention there.
    """
    validate_url_public(url)
    opener = urllib.request.build_opener(GuardedRedirectHandler())
    req = urllib.request.Request(url, headers={"User-Agent": "hyperresearch/0.1"})
    return opener.open(req, timeout=timeout)
