"""HappyParking event engine: FCM push + poll fallback, de-duplicated."""
from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Callable

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_BASE_URL,
    CONF_DEVICE_ID,
    CONF_SCAN_INTERVAL,
    CONF_SITE_CODE,
    CONF_USER_ID,
    CONF_VERIFY_SSL,
    DEFAULT_DEVICE_ID,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_VERIFY_SSL,
    EVENT_CAR,
    FIREBASE,
    LOGGER,
)


def derive_site_code(base_url: str) -> str:
    """The parking server subdomain is the site identifier (e.g. https://<site>.host -> <site>)."""
    try:
        host = base_url.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0]
        return host.split(".", 1)[0]
    except Exception:  # noqa: BLE001
        return ""


class HappyParkingCoordinator:
    """Owns the FCM listener and the poll loop, and dispatches car in/out events."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        data = entry.data
        self.base = str(data[CONF_BASE_URL]).rstrip("/")
        self.user_id = int(data[CONF_USER_ID])
        self.site_code = str(data.get(CONF_SITE_CODE) or "").strip() or derive_site_code(self.base)
        self.device_id = str(data.get(CONF_DEVICE_ID) or DEFAULT_DEVICE_ID)
        self.verify_ssl = bool(data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL))
        self.scan_interval = int(data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        self.creds_path = hass.config.path(f".happyparking_fcm_{entry.entry_id}.json")

        self._seen: set[str] = set()
        self._listeners: set[Callable[[str, dict], None]] = set()
        self._tasks: list[asyncio.Task] = []
        self._fcm = None
        self._session: aiohttp.ClientSession | None = None

    # -- listener registration (used by the event entity) --------------------
    @callback
    def add_listener(self, cb: Callable[[str, dict], None]) -> Callable[[], None]:
        self._listeners.add(cb)

        def _remove() -> None:
            self._listeners.discard(cb)

        return _remove

    # -- http ----------------------------------------------------------------
    async def _get_json(self, url: str) -> dict | None:
        assert self._session is not None
        try:
            async with self._session.get(url, ssl=self.verify_ssl) as resp:
                if resp.status != 200:
                    LOGGER.warning("GET %s -> %s", url, resp.status)
                    return None
                return await resp.json(content_type=None)
        except Exception as err:  # noqa: BLE001
            LOGGER.warning("GET %s failed: %s", url, err)
            return None

    async def _get_recent(self, limit: int = 10) -> list[dict]:
        url = (
            f"{self.base}/local/api/visitcar/household/appuser/{self.user_id}"
            f"/recent?limit={limit}&page=1"
        )
        j = await self._get_json(url)
        if isinstance(j, dict):
            return ((j.get("data") or {}).get("contents")) or []
        return []

    async def _register_push(self, token: str) -> None:
        assert self._session is not None
        body: dict = {
            "userId": self.user_id,
            "deviceId": self.device_id,
            "tokenStatus": 2,
            "pushToken": token,
        }
        if self.site_code:
            # exact key the server honors is undocumented; send both spellings, extras are harmless
            body["siteCode"] = self.site_code
            body["site_code"] = self.site_code
        try:
            async with self._session.put(
                f"{self.base}/noti2/push", json=body, ssl=self.verify_ssl
            ) as resp:
                LOGGER.info(
                    "registered push (device=%s site=%s): %s",
                    self.device_id,
                    self.site_code or "-",
                    resp.status,
                )
        except Exception as err:  # noqa: BLE001
            LOGGER.warning("push registration failed: %s", err)

    # -- event model ---------------------------------------------------------
    @staticmethod
    def _record_to_events(rec: dict) -> list[tuple[str, str, dict]]:
        vid = rec.get("visitCarId")
        car = rec.get("carNo")
        base = {
            "car_no": car,
            "visit_car_id": vid,
            "section": rec.get("carSectionName"),
            "entry_gate": rec.get("entranceGateName"),
            "entry_time": rec.get("entvhclDt"),
            "exit_gate": rec.get("exitGateName"),
            "exit_time": rec.get("lvvhclDt"),
            "parking_minutes": rec.get("parkingMinutes"),
        }
        out: list[tuple[str, str, dict]] = []
        if rec.get("entvhclDt"):
            out.append((f"{vid}:entered", "entered", {**base, "event_time": rec.get("entvhclDt")}))
        if rec.get("exitGateName") and rec.get("lvvhclDt"):
            out.append((f"{vid}:exited", "exited", {**base, "event_time": rec.get("lvvhclDt")}))
        return out

    def _process(self, records: list[dict], emit: bool = True) -> None:
        for rec in reversed(records):  # oldest first so entered precedes exited
            for key, state, data in self._record_to_events(rec):
                if key in self._seen:
                    continue
                self._seen.add(key)
                if emit:
                    self._dispatch(state, data)

    @callback
    def _dispatch(self, state: str, data: dict) -> None:
        LOGGER.info("car %s %s", data.get("car_no"), state)
        payload = {"state": state, **data}
        self.hass.bus.async_fire(EVENT_CAR, payload)
        for cb in list(self._listeners):
            cb(state, data)

    # -- engines -------------------------------------------------------------
    async def async_start(self) -> None:
        self._session = aiohttp.ClientSession()
        # Prime dedup with existing history WITHOUT notifying, so only NEW events fire.
        self._process(await self._get_recent(limit=20), emit=False)
        LOGGER.info("primed with %d known events; watching for car in/out", len(self._seen))
        self._tasks.append(self.entry.async_create_background_task(
            self.hass, self._run_poll(), "happyparking_poll"))
        self._tasks.append(self.entry.async_create_background_task(
            self.hass, self._run_push(), "happyparking_push"))

    async def _run_poll(self) -> None:
        if self.scan_interval <= 0:
            return
        while True:
            try:
                self._process(await self._get_recent(limit=10))
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                LOGGER.exception("poll error: %s", err)
            await asyncio.sleep(self.scan_interval)

    async def _run_push(self) -> None:
        try:
            from firebase_messaging import (  # noqa: PLC0415
                FcmPushClient,
                FcmPushClientConfig,
                FcmRegisterConfig,
            )
        except ImportError:
            LOGGER.warning("firebase-messaging not installed; push disabled (poll still works)")
            return

        cfg = FcmRegisterConfig(**FIREBASE)
        creds = None
        if os.path.exists(self.creds_path):
            creds = await self.hass.async_add_executor_job(
                lambda: json.load(open(self.creds_path))  # noqa: SIM115
            )

        def on_msg(notification, persistent_id, obj=None):  # runs in loop thread
            LOGGER.info("push received; refreshing records")
            self.hass.async_create_task(self._on_push())

        def creds_updated(new_creds):
            self.hass.async_add_executor_job(self._save_creds, new_creds)

        self._fcm = FcmPushClient(
            on_msg, cfg, creds, creds_updated,
            config=FcmPushClientConfig(server_heartbeat_interval=20, client_heartbeat_interval=15),
        )
        try:
            token = await self._fcm.checkin_or_register()
            if creds is None:
                await self.hass.async_add_executor_job(self._save_creds, self._fcm.credentials)
            await self._register_push(token)
            await self._fcm.start()
            LOGGER.info("FCM listener started")
            while True:
                await asyncio.sleep(6 * 3600)
                await self._register_push(token)
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001
            LOGGER.exception("push engine error (poll still active): %s", err)

    async def _on_push(self) -> None:
        try:
            self._process(await self._get_recent(limit=5))
        except Exception as err:  # noqa: BLE001
            LOGGER.exception("failed handling push: %s", err)

    def _save_creds(self, creds) -> None:
        with open(self.creds_path, "w") as fh:
            json.dump(creds, fh)

    async def async_stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        if self._fcm is not None:
            try:
                await self._fcm.stop()
            except Exception:  # noqa: BLE001
                pass
        if self._session is not None:
            await self._session.close()
