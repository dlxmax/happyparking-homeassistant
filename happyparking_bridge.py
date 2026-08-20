#!/usr/bin/env python3
"""
HappyParking -> Home Assistant bridge.

Sends a Home Assistant webhook whenever one of your registered household cars
enters or leaves the parking lot.

Two independent event engines, de-duplicated so you never get a double alert:
  1. FCM push  - the same real-time push the phone app receives (instant).
  2. /recent poll - reads the household in/out list from the parking server.
                    Acts as a reliable safety net / fallback.

Set POLL_FALLBACK_SEC=0 to go push-only once you've confirmed push delivery.

Config via environment variables:
  HA_WEBHOOK_URL   (required)  e.g. http://homeassistant.local:8123/api/webhook/happyparking
  LOCAL_BASE       local parking server base URL
  USER_ID          appUser id
  DEVICE_ID        a device id unique to this bridge (do NOT reuse the phone's)
  SITE_CODE        site id for push routing (defaults to the LOCAL_BASE subdomain)
  CREDS_PATH       where to persist FCM credentials
  POLL_FALLBACK_SEC  seconds between /recent polls (0 disables the poller)
"""
import asyncio, json, os, time, logging, urllib.request, urllib.error

log = logging.getLogger("hp-bridge")

# ---- config -----------------------------------------------------------------
HA_WEBHOOK_URL   = os.environ.get("HA_WEBHOOK_URL", "").strip()
LOCAL_BASE       = os.environ.get("LOCAL_BASE", "").rstrip("/")
USER_ID          = int(os.environ.get("USER_ID", "0"))
DEVICE_ID        = os.environ.get("DEVICE_ID", "hass-bridge-01")
# Site code the server uses to route a site's push events to registered tokens.
# Defaults to the LOCAL_BASE subdomain (e.g. https://<site>.hparking.co.kr -> <site>),
# which is the site identifier; override with SITE_CODE if your server differs.
def _derive_site_code(base):
    try:
        host = base.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0]
        return host.split(".", 1)[0]  # leftmost label
    except Exception:
        return ""
SITE_CODE        = os.environ.get("SITE_CODE", "").strip() or _derive_site_code(LOCAL_BASE)
CREDS_PATH       = os.environ.get("CREDS_PATH", os.path.join(os.path.dirname(__file__), "fcm_credentials.json"))
POLL_FALLBACK_SEC= int(os.environ.get("POLL_FALLBACK_SEC", "120"))

# Firebase project of the HappyParking app (from the APK). Stable app identity.
FIREBASE = dict(
    project_id="newhappyparkingvisitor",
    app_id="1:840195079176:android:a9e70a44ba57dac036a5bd",
    api_key="AIzaSyBf56YKbE5ZBhHAfnk_y0hT4H95HMbQMas",
    messaging_sender_id="840195079176",
    bundle_id="com.bnids.happyparking",
)

# ---- tiny http helpers ------------------------------------------------------
def _req(method, url, obj=None, timeout=20):
    data = json.dumps(obj).encode() if obj is not None else None
    r = urllib.request.Request(url, data=data, method=method,
                               headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            body = resp.read().decode()
            try: return resp.status, json.loads(body)
            except Exception: return resp.status, body
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]
    except Exception as e:
        return "ERR", str(e)[:200]

def get_recent(limit=10):
    st, j = _req("GET", f"{LOCAL_BASE}/local/api/visitcar/household/appuser/{USER_ID}/recent?limit={limit}&page=1")
    if st == 200 and isinstance(j, dict):
        return ((j.get("data") or {}).get("contents")) or []
    log.warning("recent fetch failed: %s", st)
    return []

def register_push(push_token):
    # Include the site code so the server routes this site's events to our token.
    # Sent under several key spellings since the exact one the server honors is
    # not documented; extras are harmless.
    body = {"userId": USER_ID, "deviceId": DEVICE_ID, "tokenStatus": 2,
            "pushToken": push_token}
    if SITE_CODE:
        body.update(siteCode=SITE_CODE, site_code=SITE_CODE)
    st, _ = _req("PUT", f"{LOCAL_BASE}/noti2/push", body)
    log.info("registered push token (device_id=%s, site=%s): %s", DEVICE_ID, SITE_CODE or "-", st)

def notify_ha(event):
    if not HA_WEBHOOK_URL:
        log.error("HA_WEBHOOK_URL not set; event dropped: %s", event); return
    st, _ = _req("POST", HA_WEBHOOK_URL, event)
    log.info("HA webhook %s for %s %s", st, event.get("car_no"), event.get("state"))

# ---- event model ------------------------------------------------------------
# A record represents one visit (entry, optionally exit). We emit:
#   state="entered" once we first see a record with an entry time
#   state="exited"  once that record gains an exit time
# Dedup key = (visitCarId, state); posted keys are remembered.
_seen = set()

def record_to_events(rec):
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
    out = []
    if rec.get("entvhclDt"):
        out.append(("entered", dict(base, state="entered", event_time=rec.get("entvhclDt"))))
    if rec.get("exitGateName") and rec.get("lvvhclDt"):
        out.append(("exited", dict(base, state="exited", event_time=rec.get("lvvhclDt"))))
    return [(f"{vid}:{state}", ev) for state, ev in out]

def process_records(records, emit=True):
    """Turn recent records into de-duplicated HA notifications."""
    # oldest first so entered fires before exited
    for rec in reversed(records):
        for key, ev in record_to_events(rec):
            if key in _seen:
                continue
            _seen.add(key)
            if emit:
                notify_ha(ev)

# ---- FCM push listener ------------------------------------------------------
async def run_push(loop):
    try:
        from firebase_messaging import FcmPushClient, FcmPushClientConfig, FcmRegisterConfig
    except ImportError:
        log.error("firebase-messaging not installed; push disabled. `pip install firebase-messaging`")
        return
    cfg = FcmRegisterConfig(**FIREBASE)
    creds = json.load(open(CREDS_PATH)) if os.path.exists(CREDS_PATH) else None

    def on_msg(notification, persistent_id, obj=None):
        # A push just means "something changed" — pull the authoritative record(s).
        log.info("push received: %s", json.dumps(notification, ensure_ascii=False)[:200])
        try:
            process_records(get_recent(limit=5))
        except Exception as e:
            log.exception("failed handling push: %s", e)

    def creds_updated(new_creds):
        json.dump(new_creds, open(CREDS_PATH, "w"))

    client = FcmPushClient(on_msg, cfg, creds, creds_updated,
                           config=FcmPushClientConfig(server_heartbeat_interval=20, client_heartbeat_interval=15))
    token = await client.checkin_or_register()
    if creds is None:
        json.dump(client.credentials, open(CREDS_PATH, "w"))
    register_push(token)
    await client.start()
    log.info("FCM listener started (token tail ...%s)", token[-8:])
    # periodic re-register so the server keeps our token active
    while True:
        await asyncio.sleep(6 * 3600)
        register_push(token)

# ---- polling fallback -------------------------------------------------------
async def run_poll():
    if POLL_FALLBACK_SEC <= 0:
        return
    log.info("poll fallback every %ss", POLL_FALLBACK_SEC)
    while True:
        try:
            process_records(get_recent(limit=10))
        except Exception as e:
            log.exception("poll error: %s", e)
        await asyncio.sleep(POLL_FALLBACK_SEC)

# ---- main -------------------------------------------------------------------
async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not HA_WEBHOOK_URL:
        log.warning("HA_WEBHOOK_URL is empty; set it or events go nowhere.")
    if not LOCAL_BASE or not USER_ID:
        log.error("LOCAL_BASE and USER_ID must be set (see README). Exiting.")
        return
    # Prime dedup with existing history WITHOUT notifying, so we only alert on NEW events.
    process_records(get_recent(limit=20), emit=False)
    log.info("primed with %d known events; watching for new car in/out", len(_seen))
    await asyncio.gather(run_push(asyncio.get_event_loop()), run_poll())

if __name__ == "__main__":
    asyncio.run(main())
