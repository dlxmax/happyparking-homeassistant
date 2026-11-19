"""HappyParking event engine: FCM push + poll fallback, de-duplicated."""
from __future__ import annotations

import asyncio
import json
import os
import time

import aiohttp

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_BASE_URL,
    CONF_DEVICE_ID,
    CONF_SCAN_INTERVAL,
    CONF_SITE_CODE,
    CONF_USER_ID,
    CONF_VERIFY_SSL,
    CONF_ENABLE_PUSH,
    CONF_ENABLE_NOTIFY,
    CONF_ENABLE_VISITORS,
    CREDENTIAL_KEYS,
    DEFAULT_DEVICE_ID,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_VERIFY_SSL,
    DEFAULT_ENABLE_PUSH,
    DEFAULT_ENABLE_NOTIFY,
    DEFAULT_ENABLE_VISITORS,
    DOMAIN,
    EVENT_CAR,
    EVENT_PUSH,
    EVENT_VISITOR,
    KIND_HOUSEHOLD,
    KIND_VISITOR,
    FIREBASE,
    LOGGER,
    MAX_POLL_PAGES,
    POLL_PAGE_SIZE,
)
from .describe import car_description
from .discovery import DiscoveryError, cloud_token_for, decode_token, local_token
from .feed import Feed


POLL_TICK_SECONDS = 30
WATCHDOG_SECONDS = 60
WATCHDOG_DOWN_CHECKS = 5  # minutes a reconnect may take before a rebuild

# Every push type the app knows. The server pushes a car's in/out only to
# accounts in its share group whose own subscription includes the matching
# type, so to receive all of them this account keeps every type on.
ALL_PUSH_TYPES = ("RESIDENT", "VISITOR", "UNKNOWN", "KIOSK", "HOMENET")


def _header_param(header: str, name: str) -> str:
    """Pull one base64url value out of a Web Push header, padded.

    Takes `dh=...`, `p256ecdsa=...;dh=...`, a bare value, or the library's own
    `[3:]`-stripped leftovers, and returns the value with its `=` padding.
    """
    value = header
    for part in header.replace(",", ";").split(";"):
        part = part.strip()
        if part.startswith(f"{name}="):
            value = part[len(name) + 1 :]
            break
    value = value.strip().rstrip("=")
    return value + "=" * (-len(value) % 4)


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
        self.enable_push = bool(data.get(CONF_ENABLE_PUSH, DEFAULT_ENABLE_PUSH))
        self.enable_notify = bool(
            data.get(CONF_ENABLE_NOTIFY, DEFAULT_ENABLE_NOTIFY)
        )
        self.enable_visitors = bool(
            data.get(CONF_ENABLE_VISITORS, DEFAULT_ENABLE_VISITORS)
        )
        if not self.enable_push and self.scan_interval <= 0:
            # Both engines off would mean no events at all; polling is the
            # one that has to stay.
            self.scan_interval = DEFAULT_SCAN_INTERVAL
        self.creds_path = hass.config.path(f".happyparking_fcm_{entry.entry_id}.json")

        self.feeds: list[Feed] = [
            Feed(KIND_HOUSEHOLD, EVENT_CAR, "HappyParking")
        ]
        if self.enable_visitors:
            self.feeds.append(Feed(KIND_VISITOR, EVENT_VISITOR, "HappyParking visitor"))
        self._tasks: list[asyncio.Task] = []
        self._fcm = None
        # True only while the FCM listener is actually connected; polling slows
        # down to a safety sweep then, and speeds back up when it is not.
        self.push_healthy = False
        self._push_token: str | None = None
        self._session: aiohttp.ClientSession | None = None
        self._credentials = {k: data[k] for k in CREDENTIAL_KEYS if data.get(k)}
        self._local_token: str | None = None
        self._local_expiry = 0.0
        self._auth_lock = asyncio.Lock()
        self._reauth_requested = False

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

    async def _get_page(self, feed: Feed, page: int) -> list[dict]:
        url = (
            f"{self.base}/local/api/visitcar/{feed.kind}/appuser/{self.user_id}"
            f"/recent?limit={POLL_PAGE_SIZE}&page={page}"
        )
        body = await self._get_json(url)
        if isinstance(body, dict):
            return ((body.get("data") or {}).get("contents")) or []
        return []

    # -- parking server login -------------------------------------------------
    def _request_reauth(self, why: str) -> None:
        """Ask the user, once per run, for a credential the bridge can renew with."""
        if self._reauth_requested:
            return
        self._reauth_requested = True
        LOGGER.warning("push needs a HappyParking sign-in: %s", why)
        self.entry.async_start_reauth(self.hass)

    async def _bearer(self, force: bool = False) -> str | None:
        """The parking server's 24-hour login, renewed before it runs out."""
        if not self._credentials:
            self._request_reauth("no saved sign-in to renew the login with")
            return None
        async with self._auth_lock:
            if not force and self._local_token and time.time() < self._local_expiry:
                return self._local_token
            assert self._session is not None
            try:
                cloud = await cloud_token_for(self._session, self._credentials)
                owner = decode_token(cloud).get("userId")
                if owner is not None and int(owner) != self.user_id:
                    self._request_reauth("the saved sign-in belongs to another account")
                    return None
                token = await local_token(
                    self._session, self.base, cloud, self._credentials, self.verify_ssl
                )
            except DiscoveryError as err:
                LOGGER.warning("could not sign in to the parking server: %s", err.key)
                if err.key in ("login_failed", "kakao_not_registered", "no_credentials"):
                    self._request_reauth(err.key)
                return None
            self._local_token = token
            try:
                exp = float(decode_token(token).get("exp") or 0)
            except (DiscoveryError, TypeError, ValueError):
                exp = 0
            # Renew a few minutes early; without an expiry claim, assume the
            # app's 24 hours and renew well inside it.
            self._local_expiry = exp - 300 if exp else time.time() + 20 * 3600
            LOGGER.info("signed in to the parking server")
            return token

    async def _authed(self, method: str, url: str, **kwargs) -> tuple[int, str]:
        """Send a request with the parking server login, renewing it once on 401."""
        assert self._session is not None
        status, text = 0, ""
        for attempt in range(2):
            token = await self._bearer(force=attempt > 0)
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            async with self._session.request(
                method, url, headers=headers, ssl=self.verify_ssl, **kwargs
            ) as resp:
                status, text = resp.status, await resp.text()
            if status != 401 or token is None:
                break
        return status, text

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
        # Exactly the four fields the app itself sends. The site code is the
        # server's to fill in: its own client never sends one, and a PUT
        # carrying the correct code - under either spelling - is accepted and
        # then stored as "". There is no endpoint that sets it, so a blank
        # site code on our row is not something a client can fix.
        body = {
            "userId": self.user_id,
            "deviceId": self.device_id,
            "tokenStatus": 2,
            "pushToken": wrapped,
        }
        try:
            status, text = await self._authed(
                "PUT", f"{self.base}/noti2/push", json=body
            )
            LOGGER.info(
                "push registration: device=%s status=%s response=%s",
                self.device_id,
                status,
                text[:300],
            )
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            LOGGER.warning("push registration failed: %s", err)
            return
        if status == 200:
            await self._log_registration()
            await self._sync_push_sharing()

    async def _log_registration(self) -> None:
        """Report the registration back as the server holds it."""
        url = f"{self.base}/noti2/push?deviceId={self.device_id}"
        try:
            status, text = await self._authed("GET", url)
            if status != 200:
                raise FetchError(f"GET {url} -> {status}")
            rows = json.loads(text)
        except (FetchError, ValueError, aiohttp.ClientError, asyncio.TimeoutError) as err:
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
        payload = {"body": f"{message} 알림 테스트", "pushToken": self._push_token}
        status, text = await self._authed("POST", f"{self.base}/noti2/0", json=payload)
        LOGGER.info("test push requested: status=%s response=%s", status, text[:300])
        if status != 200:
            # Reporting success on a refusal is how this went unnoticed before.
            raise FetchError(f"the parking server answered {status}")
        return text[:300]

    # -- push sharing --------------------------------------------------------
    async def _authed_json(self, method: str, url: str, **kwargs) -> dict:
        """Like _authed, but require 200 and return the parsed JSON body."""
        status, text = await self._authed(method, url, **kwargs)
        if status != 200:
            raise FetchError(f"{method} {url} -> {status}")
        return json.loads(text) if text.strip() else {}

    async def _sync_push_sharing(self) -> None:
        """Make every car at our unit, and visitor alerts, push to this account.

        The app pushes a car's in/out only to the account that registered it,
        so a second household car - a partner's, say - reaches Home Assistant
        only through the poll, up to a poll interval late. We join each car's
        alert-share group and keep this account subscribed to every push type,
        so all of them arrive the instant they happen.

        Scoped to our own unit: the server is only ever asked for the cars at
        this account's own dong/ho. Every step is best-effort - any failure is
        logged and skipped, because push and poll still deliver every event.
        """
        try:
            dong, ho = await self._my_dong_ho()
            cars = await self._household_cars(dong, ho)
        except (FetchError, aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            LOGGER.warning("could not read the household car list to share pushes: %s", err)
            return
        for car in cars:
            await self._join_share_group(car)
        await self._ensure_push_types(cars)

    async def _my_dong_ho(self) -> tuple[str, str]:
        """This account's building/unit, which scopes the car list to our home."""
        url = f"{self.base}/local/api/cloud/registcar/getDongHo/{self.user_id}"
        data = (await self._authed_json("GET", url)).get("data") or {}
        dong, ho = data.get("addressDong"), data.get("addressHo")
        if not dong or not ho:
            raise FetchError("the server returned no unit for this account")
        return str(dong), str(ho)

    async def _a_household_plate(self) -> str | None:
        """Any registered household plate; getHomepage needs one to key on."""
        for rec in await self._get_page(self.feeds[0], 1):
            if rec.get("carNo"):
                return str(rec["carNo"])
        return None

    async def _household_cars(self, dong: str, ho: str) -> list[dict]:
        """Every registered car at this unit, each with its registCarId."""
        plate = await self._a_household_plate()
        if not plate:
            raise FetchError("no household plate seen yet to query the car list")
        from urllib.parse import quote  # noqa: PLC0415

        url = (
            f"{self.base}/local/api/cloud/registcar/getHomepage"
            f"?addressDong={quote(dong)}&addressHo={quote(ho)}"
            f"&carNo={quote(plate)}&appUserId={self.user_id}&parkingAllowTime=0"
        )
        body = await self._authed_json("GET", url)
        return ((body.get("data") or {}).get("registerCarList")) or []

    async def _join_share_group(self, car: dict) -> None:
        """Add this account to one car's alert-share group, if not already in it."""
        rcid = car.get("registCarId")
        if not rcid:
            return
        base = f"{self.base}/local/api/share/registcar"
        try:
            body = await self._authed_json("GET", f"{base}/{rcid}")
            members = [
                m["appUserId"]
                for m in (body.get("contents") or [])
                if m.get("appUserId") is not None
            ]
            if self.user_id in members:
                return
            members.append(self.user_id)
            status, text = await self._authed(
                "PUT", base, json={"registCarId": rcid, "appUserIds": members}
            )
        except (FetchError, aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            LOGGER.warning("could not share pushes for registCarId=%s: %s", rcid, err)
            return
        if status == 200:
            # Log the id, never the plate.
            LOGGER.info("now sharing push alerts for registCarId=%s to this account", rcid)
        else:
            LOGGER.warning("could not share pushes for registCarId=%s: %s", rcid, text[:200])

    async def _ensure_push_types(self, cars: list[dict]) -> None:
        """Keep this account subscribed to every push type (visitor included)."""
        mine = next((c for c in cars if c.get("appUserId") == self.user_id), None)
        current = {
            t for t in str((mine or {}).get("noticeSetup") or "").split(",") if t.strip()
        }
        if current.issuperset(ALL_PUSH_TYPES):
            return
        setup = ",".join(ALL_PUSH_TYPES)
        try:
            status, text = await self._authed(
                "PUT",
                f"{self.base}/local/api/registcar/noticeSetupUpdate",
                json={"appUserId": self.user_id, "noticeSetup": setup},
            )
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            LOGGER.warning("could not update push types: %s", err)
            return
        if status == 200:
            LOGGER.info("enabled all push types (visitor included) for this account")
        else:
            LOGGER.warning("could not update push types: %s", text[:200])

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

    def _process(
        self, feed: Feed, records: list[dict], source: str, emit: bool = True
    ) -> None:
        for rec in reversed(records):  # oldest first so entered precedes exited
            vid = rec.get("visitCarId")
            for key, state, data in self._record_to_events(rec):
                if key not in feed.seen:
                    feed.seen.add(key)
                    if emit:
                        self._dispatch(feed, state, data, source)
                if state == "entered":
                    feed.open[vid] = rec.get("entvhclDt") or ""
                else:
                    feed.open.pop(vid, None)

    @callback
    def _device_id(self) -> str | None:
        registry = dr.async_get(self.hass)
        identifier = (DOMAIN, self.entry.entry_id)
        # Newer HA scopes the lookup to the entry and deprecates the old call.
        if hasattr(registry, "async_get_device_by_identifier"):
            device = registry.async_get_device_by_identifier(
                identifier, self.entry.entry_id
            )
        else:
            device = registry.async_get_device(identifiers={identifier})
        return device.id if device else None

    @callback
    def _dispatch(self, feed: Feed, state: str, data: dict, source: str) -> None:
        LOGGER.info(
            "%s car %s %s (via %s)", feed.kind, data.get("car_no"), state, source
        )
        payload = {
            "state": state,
            "source": source,
            # Household and visitor already have their own event type; carrying
            # the kind as well means one automation can listen to both and still
            # tell them apart.
            "kind": feed.kind,
            **data,
        }
        # Deliberately no entity_id. Naming the event entity here would tie the
        # described logbook row to it, and then a recorder exclude could not drop
        # the entity's bare "entered" row without taking the row with the plate
        # down too. The device is named instead, which puts the plate row on the
        # device page; the recorder does not filter events by device.
        if device_id := self._device_id():
            payload["device_id"] = device_id
        self.hass.bus.async_fire(feed.event_type, payload)
        for cb in list(feed.listeners):
            cb(state, {"source": source, "kind": feed.kind, **data})
        if self.enable_notify:
            self._notify(feed, state, data)

    @callback
    def _notify(self, feed: Feed, state: str, data: dict) -> None:
        """Raise a persistent notification for one car movement.

        Turning this off must not cost the events themselves: the automations
        people hang off happyparking_car - lighting the hallway on arrival and
        so on - are the reason to run the integration at all, and they keep
        firing either way.
        """
        gate = data.get("entry_gate") if state == "entered" else data.get("exit_gate")
        message = f"{car_description(data)} {state}"
        if gate:
            message = f"{message} - {gate}"
        if event_time := data.get("event_time"):
            message = f"{message} @ {event_time}"
        persistent_notification.async_create(
            self.hass,
            message,
            title=feed.title,
            # One notification per visit and direction, so a re-read of the
            # same row replaces its notification instead of stacking a second.
            # The kind is in the id because the two lists are numbered by the
            # same server counter and could otherwise collide.
            notification_id=f"{DOMAIN}_{feed.kind}_{data.get('visit_car_id')}_{state}",
        )

    # -- engines -------------------------------------------------------------
    async def _sweep(
        self, feed: Feed, source: str, emit: bool = True, deep: bool = False
    ) -> None:
        """Read one visit list, deep enough to see exits on long-parked cars.

        A poll stops as soon as every visit still awaiting an exit has been
        seen. A deep sweep reads the whole window regardless, which is what
        priming needs: until the open visits are known there is no way to tell
        how far down the list they sit.
        """
        records: list[dict] = []
        found: set[int] = set()
        awaiting = dict(feed.open)
        # The list is ordered by entry time, so nothing still open can sit below
        # the oldest open entry. Reading past it means the rest are gone from the
        # window, not further down - which is what stops a vanished visit from
        # costing a full page walk on every poll, forever.
        floor = min(awaiting.values()) if awaiting else None
        pages = 0
        for page in range(1, MAX_POLL_PAGES + 1):
            rows = await self._get_page(feed, page)
            if not rows:
                break
            pages = page
            records.extend(rows)
            found.update(r.get("visitCarId") for r in rows)
            if deep:
                continue
            if awaiting.keys() <= found:
                break
            if floor is not None and (rows[-1].get("entvhclDt") or "") < floor:
                break
        if missing := set(awaiting) - found:
            LOGGER.warning(
                "%d %s visit(s) awaiting an exit are no longer in the list after "
                "%s page(s); giving up on them: %s",
                len(missing),
                feed.kind,
                pages,
                sorted(missing),
            )
            for vid in missing:
                feed.open.pop(vid, None)
        LOGGER.debug(
            "%s %s sweep read %d page(s), %d record(s)",
            feed.kind,
            source,
            pages,
            len(records),
        )
        self._process(feed, records, source, emit=emit)

    async def async_start(self) -> None:
        self._session = aiohttp.ClientSession()
        for feed in self.feeds:
            await self._async_prime(feed)
        self._tasks.append(self.entry.async_create_background_task(
            self.hass, self._run_poll(), "happyparking_poll"))
        if self.enable_push:
            self._tasks.append(self.entry.async_create_background_task(
                self.hass, self._run_push(), "happyparking_push"))
        else:
            LOGGER.info("push engine disabled; polling every %ss", self.scan_interval)

    async def _async_prime(self, feed: Feed) -> bool:
        """Learn one list's existing history without notifying about any of it."""
        try:
            await self._sweep(feed, "prime", emit=False, deep=True)
        except FetchError as err:
            # Staying unprimed is the safe failure: the next attempt tries again
            # rather than announcing months of history as if it just happened.
            LOGGER.warning(
                "could not read %s history, so not notifying yet: %s", feed.kind, err
            )
            return False
        feed.primed = True
        LOGGER.info(
            "%s primed with %d known event(s); %d car(s) currently in",
            feed.kind,
            len(feed.seen),
            len(feed.open),
        )
        return True

    async def _sweep_all(self, source: str) -> None:
        """Sweep every list, priming any that has not managed it yet.

        One list failing must not stop the other: a visitor list that is empty
        or unreachable at this site should cost nothing but a log line.
        """
        for feed in self.feeds:
            try:
                if not feed.primed:
                    await self._async_prime(feed)
                    continue
                await self._sweep(feed, source)
            except asyncio.CancelledError:
                raise
            except FetchError as err:
                LOGGER.warning("%s %s failed: %s", feed.kind, source, err)
            except Exception as err:  # noqa: BLE001
                LOGGER.exception("%s %s error: %s", feed.kind, source, err)

    async def _run_poll(self) -> None:
        if self.scan_interval <= 0:
            return
        last = time.monotonic()
        while True:
            await asyncio.sleep(POLL_TICK_SECONDS)
            # Polls at the configured interval even while push is up: the
            # server does not push every event.
            if time.monotonic() - last >= self.scan_interval:
                last = time.monotonic()
                await self._sweep_all("poll")

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

        coordinator = self

        class TolerantFcmPushClient(FcmPushClient):
            """firebase-messaging 0.4.5 dies on one unreadable message.

            It expects the dh and salt values padded and alone in their headers.
            When one is not, the client shuts down, the message is never acked,
            and Google hands it back on every reconnect, so no push ever gets
            through again. Normalise the headers, and if a message still cannot
            be read, log it, let it be acked, and treat it as a change notice.
            """

            def _app_data_by_key(self, p, key, do_not_raise=False):
                value = super()._app_data_by_key(p, key, do_not_raise)
                prefix = {"crypto-key": "dh", "encryption": "salt"}.get(key)
                if prefix and value:
                    value = f"{prefix}={_header_param(value, prefix)}"
                return value

            def _handle_data_message(self, msg):
                try:
                    super()._handle_data_message(msg)
                except Exception as err:  # noqa: BLE001
                    keys = sorted(x.key for x in msg.app_data)
                    LOGGER.warning(
                        "unreadable push id=%s (%s: %s); app_data keys=%s, raw %d bytes",
                        msg.persistent_id, type(err).__name__, err, keys,
                        len(msg.raw_data or b""),
                    )
                    coordinator.hass.loop.call_soon_threadsafe(
                        coordinator._on_push, {"unreadable": keys}, msg.persistent_id
                    )

        def new_client():
            return TolerantFcmPushClient(
                on_msg, cfg, creds, creds_updated,
                config=FcmPushClientConfig(
                    server_heartbeat_interval=20, client_heartbeat_interval=15
                ),
            )

        backoff = WATCHDOG_SECONDS
        token = None
        while True:
            try:
                self._fcm = new_client()
                token = await self._fcm.checkin_or_register()
                if creds is None:
                    creds = self._fcm.credentials
                    await self.hass.async_add_executor_job(self._save_creds, creds)
                await self._register_push(token)
                await self._fcm.start()
                LOGGER.info("FCM listener started, waiting for pushes")
                if await self._watch_fcm(token):
                    # It worked for a while, so this is a fresh failure.
                    backoff = WATCHDOG_SECONDS
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                LOGGER.exception("push engine error (polling continues): %s", err)
            self.push_healthy = False
            if self._fcm is not None:
                try:
                    await self._fcm.stop()
                except Exception:  # noqa: BLE001
                    pass
            LOGGER.info("restarting the FCM listener in %ss", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 3600)

    async def _watch_fcm(self, token: str) -> bool:
        """Return once the listener has been down for a while, so it can be rebuilt.

        Returns whether it was ever connected in between.

        The library can stop on its own (a decode error, giving up on
        reconnecting) without telling anyone, so its state is checked rather
        than trusted.
        """
        down_checks = 0
        since_register = 0.0
        was_healthy = False
        while True:
            await asyncio.sleep(WATCHDOG_SECONDS)
            since_register += WATCHDOG_SECONDS
            if since_register >= 6 * 3600:
                since_register = 0.0
                await self._register_push(token)
            fcm = self._fcm
            tasks = getattr(fcm, "tasks", None) or []
            listening = bool(fcm and fcm.do_listen and tasks and not tasks[0].done())
            if listening and fcm.is_started():
                if not self.push_healthy:
                    LOGGER.info("push listener connected")
                self.push_healthy = was_healthy = True
                down_checks = 0
                continue
            down_checks += 1
            if self.push_healthy:
                LOGGER.warning(
                    "push listener is not connected (state %s)",
                    getattr(fcm, "run_state", None),
                )
            self.push_healthy = False
            # A dead listen task never comes back; a reconnect in progress
            # gets a few minutes first.
            if not listening or down_checks >= WATCHDOG_DOWN_CHECKS:
                LOGGER.warning("push listener stopped; rebuilding it")
                return was_healthy

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
        # The push says only that something changed, not which list, so both
        # are read.
        await self._sweep_all("push")

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
