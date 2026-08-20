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
    EVENT_PUSH,
    FIREBASE,
    LOGGER,
    MAX_POLL_PAGES,
    POLL_PAGE_SIZE,
)


class FetchError(Exception):
    """The parking server could not be read."""


class HappyParkingCoordinator:
    """Owns the FCM listener and the poll loop, and dispatches car in/out events."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        # Options (set after setup) win over the values captured at login.
        data = {**entry.data, **entry.options}
        self.base = str(data[CONF_BASE_URL]).rstrip("/")
        self.user_id = int(data[CONF_USER_ID])
        self.site_code = str(data.get(CONF_SITE_CODE) or "").strip()
        self.device_id = str(data.get(CONF_DEVICE_ID) or DEFAULT_DEVICE_ID)
        self.verify_ssl = bool(data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL))
        self.scan_interval = int(data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        self.creds_path = hass.config.path(f".happyparking_fcm_{entry.entry_id}.json")

        self._seen: set[str] = set()
        # Visits that have entered but not yet exited. Their rows sink down the
        # list as newer visits arrive, so a sweep must page deep enough to reach
        # them or their exit is never noticed.
        self._open: set[int] = set()
        # Until history has been read once, everything on the server looks new.
        # Emitting then would replay old events as fresh notifications.
        self._primed = False
        self._listeners: set[Callable[[str, dict], None]] = set()
        self._tasks: list[asyncio.Task] = []
        self._fcm = None
        self._push_token: str | None = None
        self._session: aiohttp.ClientSession | None = None

    # -- listener registration (used by the event entity) --------------------
    @callback
    def add_listener(self, cb: Callable[[str, dict], None]) -> Callable[[], None]:
        self._listeners.add(cb)

        def _remove() -> None:
            self._listeners.discard(cb)

        return _remove

    # -- http ----------------------------------------------------------------
    async def _get_json(self, url: str) -> dict | list:
        """Read JSON, raising rather than passing a failure off as 'no data'."""
        assert self._session is not None
        try:
            async with self._session.get(url, ssl=self.verify_ssl) as resp:
                if resp.status != 200:
                    raise FetchError(f"GET {url} -> {resp.status}")
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            raise FetchError(f"GET {url} failed: {err}") from err

    async def _get_page(self, page: int) -> list[dict]:
        url = (
            f"{self.base}/local/api/visitcar/household/appuser/{self.user_id}"
            f"/recent?limit={POLL_PAGE_SIZE}&page={page}"
        )
        body = await self._get_json(url)
        if isinstance(body, dict):
            return ((body.get("data") or {}).get("contents")) or []
        return []

    # -- push ----------------------------------------------------------------
    async def _register_push(self, token: str) -> None:
        """Register our FCM token, then read back what the server actually stored."""
        assert self._session is not None
        # The Android app registers its token wrapped as FCM[...] (iOS uses
        # APNS[...]); only the web build, which never receives push, sends it
        # bare. The server appears to pick a transport off that prefix, so we
        # register the way a push-capable client does.
        wrapped = token if token.startswith("FCM[") else f"FCM[{token}]"
        self._push_token = wrapped
        # Exactly the payload the app sends - the server ignored a site code
        # when we sent one, so it is not ours to set here.
        body = {
            "userId": self.user_id,
            "deviceId": self.device_id,
            "tokenStatus": 2,
            "pushToken": wrapped,
        }
        try:
            async with self._session.put(
                f"{self.base}/noti2/push", json=body, ssl=self.verify_ssl
            ) as resp:
                text = (await resp.text())[:300]
            LOGGER.info(
                "push registration: device=%s status=%s response=%s",
                self.device_id,
                resp.status,
                text,
            )
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            LOGGER.warning("push registration failed: %s", err)
            return
        await self._log_registration()

    async def _log_registration(self) -> None:
        """Report the registration back as the server holds it."""
        try:
            rows = await self._get_json(
                f"{self.base}/noti2/push?deviceId={self.device_id}"
            )
        except FetchError as err:
            LOGGER.warning("could not read back push registration: %s", err)
            return
        for row in rows if isinstance(rows, list) else [rows]:
            stored = str(row.get("push_token") or "")
            LOGGER.info(
                "server holds: device=%s wrapped=%s site_code=%r status=%s types=%s",
                row.get("device_id"),
                stored.startswith(("FCM[", "APNS[")),
                row.get("site_code"),
                row.get("token_status"),
                row.get("push_type_list"),
            )

    async def async_test_push(self, message: str = "Home Assistant") -> str:
        """Ask the parking server to push to our own token, to prove delivery."""
        if not self._push_token:
            raise FetchError("no push token registered yet")
        assert self._session is not None
        payload = {"body": f"{message} 알림 테스트", "pushToken": self._push_token}
        async with self._session.post(
            f"{self.base}/noti2/0", json=payload, ssl=self.verify_ssl
        ) as resp:
            text = (await resp.text())[:300]
        LOGGER.info("test push requested: status=%s response=%s", resp.status, text)
        return text

    # -- event model ---------------------------------------------------------
    @staticmethod
    def _record_to_events(rec: dict) -> list[tuple[str, str, dict]]:
        vid = rec.get("visitCarId")
        exit_gate = rec.get("exitGateName")
        exit_time = rec.get("lvvhclDt")
        # The server seeds the exit time with the entry time and only fills the
        # gate in when the car actually leaves, so without a gate there is no
        # exit to report - and no exit time worth passing on.
        has_exit = bool(exit_gate and exit_time)
        base = {
            "car_no": rec.get("carNo"),
            "visit_car_id": vid,
            "section": rec.get("carSectionName"),
            "entry_gate": rec.get("entranceGateName"),
            "entry_time": rec.get("entvhclDt"),
            "exit_gate": exit_gate if has_exit else None,
            "exit_time": exit_time if has_exit else None,
            "parking_minutes": rec.get("parkingMinutes"),
        }
        out: list[tuple[str, str, dict]] = []
        if rec.get("entvhclDt"):
            out.append((f"{vid}:entered", "entered", {**base, "event_time": rec["entvhclDt"]}))
        if has_exit:
            out.append((f"{vid}:exited", "exited", {**base, "event_time": exit_time}))
        return out

    def _process(self, records: list[dict], source: str, emit: bool = True) -> None:
        for rec in reversed(records):  # oldest first so entered precedes exited
            vid = rec.get("visitCarId")
            for key, state, data in self._record_to_events(rec):
                if key not in self._seen:
                    self._seen.add(key)
                    if emit:
                        self._dispatch(state, data, source)
                if state == "entered":
                    self._open.add(vid)
                else:
                    self._open.discard(vid)

    @callback
    def _dispatch(self, state: str, data: dict, source: str) -> None:
        LOGGER.info("car %s %s (via %s)", data.get("car_no"), state, source)
        payload = {"state": state, "source": source, **data}
        self.hass.bus.async_fire(EVENT_CAR, payload)
        for cb in list(self._listeners):
            cb(state, {"source": source, **data})

    # -- engines -------------------------------------------------------------
    async def _sweep(self, source: str, emit: bool = True, deep: bool = False) -> None:
        """Read the visit list, deep enough to see exits on long-parked cars.

        A poll stops as soon as every visit still awaiting an exit has been
        seen. A deep sweep reads the whole window regardless, which is what
        priming needs: until the open visits are known there is no way to tell
        how far down the list they sit.
        """
        records: list[dict] = []
        found: set[int] = set()
        awaiting = set(self._open)
        for page in range(1, MAX_POLL_PAGES + 1):
            rows = await self._get_page(page)
            if not rows:
                break
            records.extend(rows)
            found.update(r.get("visitCarId") for r in rows)
            if not deep and awaiting <= found:
                break
        if missing := awaiting - found:
            LOGGER.warning(
                "%d visit(s) awaiting an exit were not found within %s pages: %s",
                len(missing),
                MAX_POLL_PAGES,
                sorted(missing),
            )
        self._process(records, source, emit=emit)

    async def async_start(self) -> None:
        self._session = aiohttp.ClientSession()
        await self._async_prime()
        self._tasks.append(self.entry.async_create_background_task(
            self.hass, self._run_poll(), "happyparking_poll"))
        self._tasks.append(self.entry.async_create_background_task(
            self.hass, self._run_push(), "happyparking_push"))

    async def _async_prime(self) -> bool:
        """Learn the existing history without notifying about any of it."""
        try:
            await self._sweep("prime", emit=False, deep=True)
        except FetchError as err:
            # Staying unprimed is the safe failure: the next attempt tries again
            # rather than announcing months of history as if it just happened.
            LOGGER.warning("could not read history, so not notifying yet: %s", err)
            return False
        self._primed = True
        LOGGER.info(
            "primed with %d known event(s); %d car(s) currently in",
            len(self._seen),
            len(self._open),
        )
        return True

    async def _run_poll(self) -> None:
        if self.scan_interval <= 0:
            return
        while True:
            await asyncio.sleep(self.scan_interval)
            try:
                if not self._primed:
                    await self._async_prime()
                    continue
                await self._sweep("poll")
            except asyncio.CancelledError:
                raise
            except FetchError as err:
                LOGGER.warning("poll failed: %s", err)
            except Exception as err:  # noqa: BLE001
                LOGGER.exception("poll error: %s", err)

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
            self.hass.loop.call_soon_threadsafe(self._on_push, notification, persistent_id)

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
            LOGGER.info("FCM listener started, waiting for pushes")
            while True:
                await asyncio.sleep(6 * 3600)
                await self._register_push(token)
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001
            LOGGER.exception("push engine error (poll still active): %s", err)

    @callback
    def _on_push(self, notification, persistent_id) -> None:
        """Record that a push arrived, then read the records it refers to."""
        LOGGER.info("PUSH RECEIVED id=%s payload=%s", persistent_id, notification)
        # Fired whatever the payload turns out to be, so push delivery can be
        # watched from Developer Tools without needing the log.
        self.hass.bus.async_fire(
            EVENT_PUSH, {"persistent_id": persistent_id, "payload": notification}
        )
        self.hass.async_create_task(self._refresh_after_push())

    async def _refresh_after_push(self) -> None:
        try:
            if self._primed:
                await self._sweep("push")
            else:
                await self._async_prime()
        except FetchError as err:
            LOGGER.warning("could not read records after push: %s", err)
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
