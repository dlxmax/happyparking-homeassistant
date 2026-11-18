"""Turn a HappyParking login into the values the integration needs.

A successful login (Kakao or id/password) returns a signed token whose payload
carries the app user id and the address of the building's parking server, so
nothing has to be typed by hand.
"""
from __future__ import annotations

import base64
import binascii
import json
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

import aiohttp

from .const import (
    CLOUD_URL,
    CONF_BASE_URL,
    CONF_KAKAO_ID,
    CONF_LOGIN_ID,
    CONF_PASSWORD,
    CONF_SITE_CODE,
    CONF_USER_ID,
    LOGGER,
    LOGIN_URL,
)

JWT_RE = re.compile(r"^[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]*$")
TIMEOUT = aiohttp.ClientTimeout(total=20)


class DiscoveryError(Exception):
    """A failure with a config-flow error key attached."""

    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


def login_url() -> str:
    """HappyParking's own login page, with every sign-in method it offers."""
    return LOGIN_URL


def _b64decode(data: str) -> bytes:
    """Decode base64/base64url that may be missing its padding."""
    data = data.strip().replace("-", "+").replace("_", "/")
    return base64.b64decode(data + "=" * (-len(data) % 4))


def decode_token(token: str) -> dict[str, Any]:
    """Read the payload out of the login token."""
    parts = token.split(".")
    if len(parts) != 3:
        raise DiscoveryError("invalid_token")
    try:
        return json.loads(_b64decode(parts[1]).decode("utf-8"))
    except (ValueError, binascii.Error, UnicodeDecodeError) as err:
        raise DiscoveryError("invalid_token") from err


def process_local_server_address(encoded: str) -> str:
    """Mirror the app's handling of the encoded parking server address."""
    try:
        address = _b64decode(encoded).decode("utf-8").strip()
    except (ValueError, binascii.Error, UnicodeDecodeError) as err:
        raise DiscoveryError("no_server") from err
    if not address:
        raise DiscoveryError("no_server")
    if address.startswith("http:"):
        address = "https:" + address[len("http:") :]
    if not address.startswith("https:"):
        address = f"https://{address}"
    if "localserver" in address and ":9443" in address:
        address = address.replace(":9443", "")
    else:
        address = f"{address}:9443"
    return address.rstrip("/")


def server_host(base_url: str) -> str:
    """The host part of a parking server URL."""
    return base_url.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0]


def parse_pasted_login(raw: str) -> tuple[str | None, str | None]:
    """Accept whatever the user pasted back and return (token, kakao_id).

    Handles the address bar after login (which carries the login response), the
    response on its own, a bare token, or a bare Kakao account id.
    """
    raw = (raw or "").strip().strip('"')
    if not raw:
        raise DiscoveryError("invalid_login_token")

    if raw.startswith(("http://", "https://")):
        query = urlparse(raw)
        params = parse_qs(query.query) | parse_qs(query.fragment)
        for key in ("response", "token", "kakaoId"):
            if values := params.get(key):
                return parse_pasted_login(values[0])
        raise DiscoveryError("invalid_login_token")

    if raw.startswith("{"):
        try:
            payload = json.loads(raw)
        except ValueError as err:
            raise DiscoveryError("invalid_login_token") from err
        data = payload.get("data") or {}
        if isinstance(data, dict) and data.get("token"):
            return str(data["token"]), None
        if payload.get("token"):
            return str(payload["token"]), None
        raise DiscoveryError("login_failed")

    if JWT_RE.match(raw):
        return raw, None

    if raw.isdigit():
        return None, raw

    raise DiscoveryError("invalid_login_token")


async def _cloud_json(
    session: aiohttp.ClientSession, method: str, url: str, **kwargs: Any
) -> dict[str, Any]:
    try:
        async with session.request(method, url, timeout=TIMEOUT, **kwargs) as resp:
            body = await resp.json(content_type=None)
    except aiohttp.ClientError as err:
        LOGGER.debug("HappyParking cloud request failed: %s", err)
        raise DiscoveryError("cannot_connect") from err
    if not isinstance(body, dict):
        raise DiscoveryError("login_failed")
    return body


async def token_for_kakao_id(session: aiohttp.ClientSession, kakao_id: str) -> str:
    """Exchange a Kakao account id for a HappyParking login token."""
    body = await _cloud_json(
        session, "GET", f"{CLOUD_URL}/api/users/signin/kakao", params={"kakaoId": kakao_id}
    )
    data = body.get("data") or {}
    if body.get("code") == "NOT_FOUND":
        raise DiscoveryError("kakao_not_registered")
    if not isinstance(data, dict) or not data.get("token"):
        raise DiscoveryError("login_failed")
    return str(data["token"])


async def token_for_password(
    session: aiohttp.ClientSession, login_id: str, password: str
) -> str:
    """Log in with a HappyParking id and password."""
    body = await _cloud_json(
        session,
        "POST",
        f"{CLOUD_URL}/api/users/signin2",
        json={"loginId": login_id, "loginPassword": password},
    )
    token = body.get("token") or (body.get("data") or {}).get("token")
    if not token:
        raise DiscoveryError("login_failed")
    return str(token)


async def cloud_token_for(
    session: aiohttp.ClientSession, credentials: dict[str, Any]
) -> str:
    """Sign in to the cloud again with whatever renewal credential was kept."""
    if kakao_id := credentials.get(CONF_KAKAO_ID):
        return await token_for_kakao_id(session, str(kakao_id))
    if (login_id := credentials.get(CONF_LOGIN_ID)) and credentials.get(CONF_PASSWORD):
        return await token_for_password(
            session, str(login_id), str(credentials[CONF_PASSWORD])
        )
    raise DiscoveryError("no_credentials")


def _unwrap_token(body: dict[str, Any]) -> str | None:
    data = body.get("data")
    if isinstance(data, dict) and data.get("token"):
        return str(data["token"])
    if body.get("token"):
        return str(body["token"])
    return None


async def local_token(
    session: aiohttp.ClientSession,
    base_url: str,
    cloud_token: str,
    credentials: dict[str, Any],
    verify_ssl: bool = True,
) -> str:
    """Trade a cloud login for the parking server's own 24-hour login.

    Mirrors the app: the cloud token's payload carries the key the parking
    server checks, and the login id is the Kakao id or the HappyParking id.
    """
    payload = decode_token(cloud_token)
    key = payload.get("secureKey") or payload.get("tokenKey") or payload.get("securityKey")
    user_id = payload.get("userId")
    if not key or user_id is None:
        raise DiscoveryError("invalid_token")
    login_id = (
        credentials.get(CONF_KAKAO_ID)
        or credentials.get(CONF_LOGIN_ID)
        or payload.get("loginId")
        or ""
    )
    body = await _cloud_json(
        session,
        "POST",
        f"{base_url}/local/api/login/cloud",
        json={"userId": user_id, "loginId": str(login_id), "tokenKey": key},
        ssl=verify_ssl,
    )
    token = _unwrap_token(body)
    if not token:
        raise DiscoveryError("login_failed")
    return token


def config_from_token(token: str) -> dict[str, Any]:
    """The base URL, user id and site code implied by a login token."""
    payload = decode_token(token)
    user_id = payload.get("userId")
    if user_id is None:
        raise DiscoveryError("invalid_token")
    address = payload.get("localServerAddress")
    if not address:
        raise DiscoveryError("no_server")
    base_url = process_local_server_address(str(address))
    # The site code is its own identifier and is not the server's subdomain,
    # so it is only ever taken from the login - never guessed from the URL.
    site_code = str(payload.get("siteCode") or payload.get("site_code") or "")
    return {
        CONF_BASE_URL: base_url,
        CONF_USER_ID: int(user_id),
        CONF_SITE_CODE: site_code,
    }
