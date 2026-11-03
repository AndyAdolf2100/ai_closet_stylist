"""Volc Engine V4 request signing (AK/SK).

Implements the HMAC-SHA256 signing protocol Volc uses across its APIs
(similar to AWS SigV4). Used to authenticate requests to VikingDB / MLP.

Reference (Volc signing spec):
  https://www.volcengine.com/docs/6291/65568

The signing service for VikingDB knowledge base APIs is `air` in region
`cn-beijing`; these are configurable in case Volc changes them later.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

SIGNING_ALGORITHM = "HMAC-SHA256"


@dataclass(frozen=True)
class SigningContext:
    ak: str = field(repr=False)
    sk: str = field(repr=False)
    region: str = "cn-beijing"
    service: str = "air"    # Volc VikingDB / MLP service name


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hmac_sha256(key: bytes, message: bytes) -> bytes:
    return hmac.new(key, message, hashlib.sha256).digest()


def _now_utc() -> tuple[str, str]:
    """Return (X-Date, YYYYMMDD) in Volc's required format."""
    now = _dt.datetime.now(_dt.timezone.utc)
    x_date = now.strftime("%Y%m%dT%H%M%SZ")
    return x_date, x_date[:8]


def _canonical_query(params: dict[str, Any] | None) -> str:
    if not params:
        return ""
    items: list[tuple[str, str]] = []
    for k, v in params.items():
        if v is None:
            continue
        items.append((str(k), "" if v is True else "" if v == "" else str(v)))
    items.sort()
    return "&".join(f"{quote(k, safe='-_.~')}={quote(v, safe='-_.~')}" for k, v in items)


def _canonical_headers(headers: dict[str, str]) -> tuple[str, str]:
    """Return (canonical_headers_block, signed_headers_list)."""
    lowered = {k.lower(): v.strip() for k, v in headers.items()}
    signed = sorted(lowered.keys())
    canonical_block = "".join(f"{k}:{lowered[k]}\n" for k in signed)
    return canonical_block, ";".join(signed)


def sign_request(
    ctx: SigningContext,
    method: str,
    host: str,
    path: str,
    body: bytes,
    query: dict[str, Any] | None = None,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, str]:
    """Compute the Volc V4 signature and return the full header set to send.

    The returned dict includes: Host, X-Date, X-Content-Sha256,
    Content-Type (json), Authorization, plus anything from `extra_headers`.
    """
    x_date, short_date = _now_utc()
    content_hash = _sha256_hex(body or b"")

    headers: dict[str, str] = {
        "Host": host,
        "X-Date": x_date,
        "X-Content-Sha256": content_hash,
        "Content-Type": "application/json",
    }
    if extra_headers:
        for k, v in extra_headers.items():
            headers[k] = v

    canonical_headers_block, signed_headers = _canonical_headers(headers)

    canonical_request = "\n".join([
        method.upper(),
        path or "/",
        _canonical_query(query),
        canonical_headers_block,
        signed_headers,
        content_hash,
    ])

    credential_scope = f"{short_date}/{ctx.region}/{ctx.service}/request"
    string_to_sign = "\n".join([
        SIGNING_ALGORITHM,
        x_date,
        credential_scope,
        _sha256_hex(canonical_request.encode("utf-8")),
    ])

    k_date = _hmac_sha256(ctx.sk.encode("utf-8"), short_date.encode("utf-8"))
    k_region = _hmac_sha256(k_date, ctx.region.encode("utf-8"))
    k_service = _hmac_sha256(k_region, ctx.service.encode("utf-8"))
    k_signing = _hmac_sha256(k_service, b"request")
    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = (
        f"{SIGNING_ALGORITHM} "
        f"Credential={ctx.ak}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )
    headers["Authorization"] = authorization
    return headers
