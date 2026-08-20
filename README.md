# HappyParking for Home Assistant

A custom [Home Assistant](https://www.home-assistant.io/) integration that
notifies you the moment one of your registered **household** cars enters or
leaves your apartment parking lot, using the HappyParking (해피파킹) system by
BN Industry (비엔인더스트리, `com.bnids.happyparking`).

There is no official public API, so this talks to your building's own parking
server the same way the phone app does. You sign in during setup and everything
else is discovered from that login — nothing is hard-coded.

## How it works

Two engines, de-duplicated (no double alerts):

1. **FCM push** — registers a push token with the parking server and receives the
   same real-time push the phone app gets. Instant.
2. **Poll fallback** (default every 120 s) — reads the household in/out list
   directly. A reliable safety net; set the interval to `0` to go push-only once
   you've confirmed push delivery.

Each car event is exposed two ways:

- an **event entity** (`event.happyparking_car_in_out`) that fires `entered` /
  `exited` with the car record as attributes, and
- a **bus event** `happyparking_car` for classic automations.

## Install (HACS)

1. HACS → **⋮** → **Custom repositories**.
2. Add `https://github.com/dlxmax/happyparking-homeassistant`, category
   **Integration**.
3. Install **HappyParking**, then **restart Home Assistant**.
4. Settings → Devices & Services → **Add Integration** → **HappyParking**, and
   sign in (below).

(Manual install: copy `custom_components/happyparking/` into your HA
`config/custom_components/` folder and restart.)

## Setup

When you add the integration it asks how you sign in — the same way you sign in
to the app:

- **Kakao** — HA gives you the real HappyParking Kakao login link. Complete the
  login, then paste back the address you land on. (If the page moves on too
  fast, paste your login token instead; the dialog tells you where to find it.)
- **HappyParking id and password** — for accounts that were not created through
  a social login.
- **Enter server details myself** — a fallback if signing in does not work.

Either login gives back a signed token that already contains your building's
parking server address, your app user id and your site code, so those are filled
in for you. The site code is its own identifier — it is not the server's
subdomain — so it is only ever read from the login, never guessed.

Afterwards, **Configure** on the integration exposes:

| option | meaning |
|--------|---------|
| Device ID | a device id unique to this bridge (default `hass-happyparking`) |
| Poll fallback seconds | default `120`; `0` = push-only |
| Verify TLS certificate | turn off only if your server uses a self-signed cert |

## Example automation

```yaml
alias: HappyParking car in/out notification
triggers:
  - trigger: event
    event_type: happyparking_car
actions:
  - action: notify.notify
    data:
      title: "🚗 HappyParking"
      message: >-
        {{ trigger.event.data.car_no }}
        {{ '들어왔어요 (entered)' if trigger.event.data.state == 'entered'
           else '나갔어요 (exited)' }}
        — {{ trigger.event.data.entry_gate
              if trigger.event.data.state == 'entered'
              else trigger.event.data.exit_gate }}
```

## Notes

- To also catch VISITOR cars, the server exposes
  `/local/api/visitcar/visitor/appuser/{user_id}/recent` (same shape) — this
  integration handles household cars only.
- Push routing to a second (non-phone) token can vary by site; the poll engine
  covers you regardless.

## Icon

The app's mark is in `brands/happyparking/` (`icon.png` 256², `icon@2x.png` 512²).
For it to render in Home Assistant it must be added to the
[home-assistant/brands](https://github.com/home-assistant/brands) repository
under `custom_integrations/happyparking/`; that submission is separate from this
repo.
