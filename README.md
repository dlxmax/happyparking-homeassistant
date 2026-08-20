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

The visit list is ordered by *entry* time and an exit is written back onto the
original row, so a car left parked while another comes and goes sinks down the
list. Each sweep therefore keeps paging until every visit still awaiting an exit
has been seen, rather than trusting the first page.

Each car event is exposed two ways:

- an **event entity** (`event.happyparking_car_in_out`) that fires `entered` /
  `exited` with the car record as attributes, and
- a **bus event** `happyparking_car` for classic automations.

Both carry a `source` of `push` or `poll`, so you can see which engine delivered
any given event. `exit_gate` and `exit_time` are `null` until the car actually
leaves — the server seeds the exit time with the entry time, so it cannot be
trusted on its own.

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

Adding the integration sends you to **HappyParking's own login page**
(`app.hparking.co.kr/happyparking/login`) — the same one the app uses, with both
**Kakao** and **HappyParking id** sign-in. Sign in there as you normally would,
then copy your login token back into Home Assistant:

> F12 → **Application** → **Local Storage** → `https://app.hparking.co.kr` → copy
> the value of `token`.

That token is a signed blob that already contains your building's parking server
address, your app user id and your site code, so nothing else has to be typed in.
The site code is its own identifier — it is not the server's subdomain — so it is
only ever read from the login, never guessed.

The token has to be copied by hand because HappyParking's login only ever returns
to HappyParking's own site, never to your Home Assistant.

If you would rather not use a browser, submit the box empty and you get two
alternatives: signing in with a **HappyParking id and password** directly, or
entering the **server details** yourself.

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

## Checking push

Push is registered, but not every site routes to a non-phone token, and a silent
failure looks exactly like a quiet car park. Two ways to tell:

- Any car event carries `source: push` or `source: poll`. A `poll` source with a
  lag close to your scan interval means push is not arriving.
- Call the **`happyparking.test_push`** service. The parking server is asked to
  push to Home Assistant's own token; if it arrives, a **`happyparking_push`**
  event appears on the bus (watch Developer Tools → Events). That event fires for
  every push received, so it works as a live indicator without needing the log.

## Notes

- To also catch VISITOR cars, the server exposes
  `/local/api/visitcar/visitor/appuser/{user_id}/recent` (same shape) — this
  integration handles household cars only.
- Push routing to a second (non-phone) token can vary by site; the poll engine
  covers you regardless.
- The integration ships its own icon in `custom_components/happyparking/brand/`;
  Home Assistant serves it locally from 2026.3 onwards.
