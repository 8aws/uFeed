"""Outbound-request guard against SSRF.

Users (and feeds, via redirects) choose the URLs the server fetches. Without a
guard, "add feed" could make the server call internal services: the Docker
network (db, cache, ai), the LAN (router, NAS admin panels) or localhost.

`public_client()` returns an httpx client whose request hook runs for every
request — including each redirect hop — and only allows http(s) to hosts that
resolve exclusively to public IP addresses. Set ALLOW_PRIVATE_FEEDS=true to
allow LAN feeds on a trusted, single-user install.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit

import httpx

from app.core.config import settings


class BlockedDestination(httpx.RequestError):
    """Raised (as an httpx error, so callers treat it as a failed fetch)."""


def _public(ip: str) -> bool:
    addr = ipaddress.ip_address(ip.split("%", 1)[0])
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return addr.is_global and not addr.is_multicast


async def check_destination(url: str) -> None:
    """Raise ValueError unless `url` is http(s) to public addresses only."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError(f"unsupported URL: {url[:80]}")
    if settings.allow_private_feeds:
        return
    host = parts.hostname
    try:
        ips = [str(ipaddress.ip_address(host))]
    except ValueError:
        port = parts.port or (443 if parts.scheme == "https" else 80)
        try:
            infos = await asyncio.get_running_loop().getaddrinfo(
                host, port, type=socket.SOCK_STREAM
            )
        except socket.gaierror as exc:
            raise ValueError(f"cannot resolve {host}") from exc
        ips = [info[4][0] for info in infos]
    if not ips or not all(_public(ip) for ip in ips):
        raise ValueError(f"destination not allowed: {host}")


async def _guard(request: httpx.Request) -> None:
    try:
        await check_destination(str(request.url))
    except ValueError as exc:
        raise BlockedDestination(str(exc), request=request) from exc


def public_client(**kwargs) -> httpx.AsyncClient:
    """httpx.AsyncClient that refuses private/internal destinations."""
    hooks = kwargs.pop("event_hooks", {}) or {}
    hooks = {**hooks, "request": [*hooks.get("request", []), _guard]}
    return httpx.AsyncClient(event_hooks=hooks, **kwargs)
