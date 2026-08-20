# HappyParking → Home Assistant bridge

Sends a Home Assistant notification whenever one of your registered **household**
cars enters or leaves your apartment parking lot, using the HappyParking
(해피파킹) system by BN Industry (비엔인더스트리, `com.bnids.happyparking`).

There is no official public API, so this talks to the app's own backend the same
way the phone app does. You supply your own account/site values via environment
variables (see **Config**).

## How it works

Two engines, de-duplicated (no double alerts):

1. **FCM push** — registers a push token with the parking server and receives the
   same real-time push the phone app gets. Instant. On a push it reads the
   authoritative record and forwards it to HA.
2. **`/recent` poll** (default every 120 s) — reads the household in/out list
   directly. Acts as a reliable fallback.

> On push routing: the receive side is proven (it logs into Google's MCS and
> holds the connection). Whether the parking server routes a real car event to a
> second (non-phone) token can vary by site. The **poll engine covers this
> regardless**, so notifications work either way. Once you see a push-driven
> alert land (log line `push received:`), you can set `POLL_FALLBACK_SEC=0` to go
> push-only.

## Setup

1. Copy this folder to the HA host, e.g. `/opt/happyparking-ha`.
2. Create the venv and install deps:
   ```
   python3 -m venv venv
   ./venv/bin/pip install -r requirements.txt
   ```
3. In Home Assistant, add the automation in `happyparking.automation.yaml`
   (it creates webhook id `happyparking`). Make sure you have a `notify.notify`
   target (mobile app, etc.).
4. Edit `happyparking-bridge.service` — set `HA_WEBHOOK_URL`, `LOCAL_BASE` and
   `USER_ID` for your account (see below) — then:
   ```
   sudo cp happyparking-bridge.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now happyparking-bridge
   journalctl -u happyparking-bridge -f
   ```

On first run the bridge creates and registers `fcm_credentials.json` (your push
identity). Keep that file; it is gitignored and must not be committed.

## Config (environment variables)

| var | required | meaning |
|-----|----------|---------|
| `HA_WEBHOOK_URL` | yes | where events are POSTed, e.g. `http://<ha-host>:8123/api/webhook/happyparking` |
| `LOCAL_BASE` | yes | your building's parking server base URL, e.g. `https://<your-site>.hparking.co.kr:9443` |
| `USER_ID` | yes | your appUser id |
| `DEVICE_ID` | no | a device id unique to this bridge (default `hass-bridge-01`; keep distinct from the phone) |
| `SITE_CODE` | no | site id used to route push events (defaults to the `LOCAL_BASE` subdomain) |
| `POLL_FALLBACK_SEC` | no | seconds between polls (default `120`; `0` = push-only) |
| `CREDS_PATH` | no | FCM identity store (default `./fcm_credentials.json`) |

## Webhook payload (what HA receives)

```json
{"car_no":"12가3456","state":"entered","section":"입주민차량",
 "entry_gate":"정문","entry_time":"2026-08-20T09:00:00",
 "exit_gate":null,"exit_time":null,"parking_minutes":0,
 "visit_car_id":999001,"event_time":"2026-08-20T09:00:00"}
```
`state` is `entered` or `exited`.

## Notes
- If your building's server hostname changes, update `LOCAL_BASE`.
- To also catch VISITOR cars, read
  `/local/api/visitcar/visitor/appuser/{USER_ID}/recent` (same shape) — not
  enabled here, which is household-only.
