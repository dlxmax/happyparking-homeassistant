# HappyParking for Home Assistant

**English** · [한국어](#해피파킹-for-home-assistant)

A custom [Home Assistant](https://www.home-assistant.io/) integration that
notifies you the moment one of your registered **household** cars enters or
leaves your apartment parking lot, using the HappyParking (해피파킹) system by
BN Industry (비엔인더스트리, `com.bnids.happyparking`).

There is no official public API, so this talks to your building's own parking
server the same way the phone app does. You sign in during setup and everything
else is discovered from that login — nothing is hard-coded.

> Every section below appears in English first and in Korean afterwards.
> 아래 모든 항목은 영어 다음에 한국어가 이어집니다.

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
| Device ID for this bridge | a device id unique to this bridge (default `hass-happyparking`) |
| Poll fallback seconds | default `120`; `0` = push-only |
| Verify the server's TLS certificate | turn off only if your server uses a self-signed cert |
| Register a push token | uncheck to stay out of the parking server's push table; polling still delivers every event |
| Show a notification for each car entering or leaving | on by default; uncheck for events without the notifications |

Turning the notifications off does not cost you the events. The event entity and
the `happyparking_car` bus event fire either way, so automations built on them —
lighting the hallway on arrival, say — keep working with a silent notification
drawer.

## In the logbook

A car movement is written to the logbook by plate:

> **HappyParking** 00가0000 entered at Main gate

An event entity's own state is only ever the event type, so its row can say no
more than `entered` — which car it was, the one thing worth recording, is
missing. The movement is therefore described from the `happyparking_car` bus
event, where the plate is.

The described row names the event entity, so it shows up both in the main
Logbook and in the **Activity** list of the entity's own dialog. That naming is
also why there is no `logbook: exclude:` recipe here: excluding the entity would
take the described row down with the bare one, leaving the logbook emptier than
before rather than tidier.

The bare `entered` / `exited` row is still written alongside it. To drop it and
leave only the row with the plate, keep the entity out of the recorder — at the
cost of the entity's history graph:

```yaml
recorder:
  exclude:
    entities:
      - event.happyparking_car_in_out
```

## Example automation

The built-in notification covers the common case. Use the bus event when you
want your own wording or your own delivery (phone push, TTS, lights):

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

If you use an automation like this, turn **Show a notification for each car**
off so you do not get both.

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

---

# 해피파킹 for Home Assistant

[English](#happyparking-for-home-assistant) · **한국어**

비엔인더스트리의 **해피파킹**(`com.bnids.happyparking`) 시스템을 사용하는 아파트에서,
등록된 **세대 차량**이 주차장에 들어오거나 나가는 순간 알려주는
[홈어시스턴트](https://www.home-assistant.io/) 커스텀 통합구성요소입니다.

공식 공개 API가 없기 때문에, 휴대폰 앱과 똑같은 방식으로 우리 아파트의 주차 서버와
직접 통신합니다. 설정할 때 한 번 로그인하면 나머지 정보는 모두 그 로그인에서
읽어옵니다. 하드코딩된 값은 없습니다.

## 동작 방식

두 개의 엔진이 함께 돌고, 중복은 제거됩니다(알림이 두 번 오지 않습니다).

1. **FCM 푸시** — 주차 서버에 푸시 토큰을 등록하고, 휴대폰 앱이 받는 것과 같은
   실시간 푸시를 받습니다. 즉시 도착합니다.
2. **폴링(기본 120초)** — 세대 차량 입·출차 목록을 직접 읽는 안전장치입니다.
   푸시가 확실히 도착하는 것을 확인했다면 주기를 `0`으로 두어 푸시 전용으로 쓸 수
   있습니다.

방문 목록은 **입차 시각** 순으로 정렬되고 출차는 원래 행에 덮어써집니다. 그래서
다른 차가 오가는 동안 계속 주차되어 있던 차의 행은 목록 아래로 밀려납니다. 따라서
매번 첫 페이지만 믿지 않고, 아직 출차되지 않은 방문이 모두 확인될 때까지 페이지를
넘겨가며 읽습니다.

차량 이벤트는 두 가지 형태로 제공됩니다.

- **이벤트 엔티티** (`event.happyparking_car_in_out`) — `entered` / `exited`를
  발생시키며 차량 정보를 속성으로 담습니다.
- **버스 이벤트** `happyparking_car` — 기존 방식의 자동화에 사용합니다.

두 가지 모두 `source` 값으로 `push` 또는 `poll`을 담고 있어, 어느 엔진이 해당
이벤트를 전달했는지 알 수 있습니다. `exit_gate`와 `exit_time`은 차가 실제로 나가기
전까지 `null`입니다. 서버가 출차 시각을 입차 시각으로 미리 채워두기 때문에, 그 값만
보고 판단할 수 없습니다.

## 설치 (HACS)

1. HACS → **⋮** → **사용자 지정 저장소**.
2. `https://github.com/dlxmax/happyparking-homeassistant`를 **통합구성요소**
   카테고리로 추가합니다.
3. **HappyParking**을 설치한 뒤 **홈어시스턴트를 재시작**합니다.
4. 설정 → 기기 및 서비스 → **통합구성요소 추가** → **HappyParking**을 선택하고
   아래 방법으로 로그인합니다.

(수동 설치: `custom_components/happyparking/` 폴더를 홈어시스턴트의
`config/custom_components/`에 복사하고 재시작합니다.)

## 설정

통합구성요소를 추가하면 **해피파킹 자체 로그인 페이지**
(`app.hparking.co.kr/happyparking/login`)로 안내합니다. 앱에서 쓰는 것과 같은
페이지이며 **카카오**와 **해피파킹 아이디** 로그인을 모두 지원합니다. 평소처럼
로그인한 다음, 로그인 토큰을 홈어시스턴트에 붙여넣습니다.

> F12 → **Application** → **Local Storage** → `https://app.hparking.co.kr` →
> `token` 값을 복사

이 토큰은 서명된 값으로, 우리 아파트의 주차 서버 주소·앱 사용자 ID·사이트 코드를
이미 담고 있습니다. 그래서 그 밖에 입력할 것이 없습니다. 사이트 코드는 별도의
식별자이며 서버의 서브도메인이 **아닙니다**. 그래서 추측하지 않고 반드시 로그인
정보에서만 읽어옵니다.

토큰을 직접 복사해야 하는 이유는, 해피파킹 로그인이 항상 해피파킹 자체 사이트로만
돌아가고 사용자의 홈어시스턴트로는 절대 돌아오지 않기 때문입니다.

브라우저를 쓰기 어렵다면 입력란을 비운 채로 제출하세요. **해피파킹 아이디와 비밀번호**로
직접 로그인하거나, **서버 정보**를 직접 입력하는 두 가지 방법이 나타납니다.

설정을 마친 뒤 통합구성요소의 **구성**에서 다음 항목을 조정할 수 있습니다.

| 옵션 | 의미 |
|------|------|
| 이 브리지의 기기 ID | 이 브리지만의 고유한 기기 ID (기본값 `hass-happyparking`) |
| 폴링 주기(초, 0 = 푸시만 사용) | 기본값 `120`, `0`이면 푸시 전용 |
| 서버 TLS 인증서 검증 | 자체 서명 인증서를 쓰는 서버일 때만 해제 |
| 푸시 토큰 등록 | 해제하면 주차 서버의 푸시 목록에 등록하지 않습니다. 그래도 폴링이 모든 이벤트를 전달합니다 |
| 차량 입·출차 시 알림 표시 | 기본 켜짐. 해제하면 알림 없이 이벤트만 발생합니다 |

알림을 꺼도 이벤트는 그대로 발생합니다. 이벤트 엔티티와 `happyparking_car` 버스
이벤트는 어느 쪽이든 계속 동작하므로, 이를 이용한 자동화(예: 귀가 시 현관 조명
켜기)는 알림함만 조용해질 뿐 그대로 작동합니다.

## 로그북에서 보기

차량의 입·출차는 **차량 번호**와 함께 로그북에 기록됩니다.

> **HappyParking** 00가0000 entered at Main gate

이벤트 엔티티의 상태값은 이벤트 종류(`entered` 등)뿐이라, 엔티티가 스스로 남기는
줄에는 **어느 차량인지**라는 가장 중요한 정보가 빠집니다. 그래서 차량 번호가 들어
있는 `happyparking_car` 버스 이벤트를 따로 설명(describe)하여 기록합니다.

이렇게 기록된 줄은 이벤트 엔티티를 함께 지정하므로, 메인 **로그북**과 해당 엔티티
대화상자의 **활동(Activity)** 목록 양쪽에 모두 나타납니다. 바로 이 점 때문에 여기에는
`logbook: exclude:` 설정을 안내하지 않습니다. 엔티티를 제외하면 차량 번호가 담긴 줄까지
함께 사라져서, 로그북이 정리되는 것이 아니라 오히려 더 비어버립니다.

기본 `entered` / `exited` 줄은 그 옆에 그대로 남습니다. 이 줄을 없애고 차량 번호가
담긴 줄만 남기려면 해당 엔티티를 recorder에서 제외하면 됩니다. 다만 엔티티의 기록
그래프를 잃게 됩니다.

```yaml
recorder:
  exclude:
    entities:
      - event.happyparking_car_in_out
```

## 자동화 예시

기본 제공 알림으로 대부분의 경우는 충분합니다. 문구를 직접 정하거나 다른 방식으로
받고 싶을 때(휴대폰 푸시, TTS, 조명 등) 버스 이벤트를 사용하세요.

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

이런 자동화를 쓴다면 알림이 두 번 오지 않도록 **차량 입·출차 시 알림 표시** 옵션을
꺼두세요.

## 푸시 확인하기

푸시 토큰은 등록되지만, 모든 단지가 휴대폰이 아닌 토큰으로 푸시를 보내주는 것은
아닙니다. 게다가 조용히 실패한 상태는 그냥 차가 안 다니는 것과 구분되지 않습니다.
확인 방법은 두 가지입니다.

- 모든 차량 이벤트에는 `source: push` 또는 `source: poll`이 들어 있습니다. 폴링
  주기만큼 지연된 `poll` 이벤트만 온다면 푸시가 도착하지 않는 것입니다.
- **`happyparking.test_push`** 서비스를 호출하세요. 주차 서버가 홈어시스턴트 자신의
  토큰으로 푸시를 보내도록 요청합니다. 도착하면 버스에 **`happyparking_push`**
  이벤트가 나타납니다(개발자 도구 → 이벤트에서 확인). 이 이벤트는 수신되는 모든
  푸시마다 발생하므로, 로그를 보지 않고도 실시간 확인용으로 쓸 수 있습니다.

## 참고

- **방문 차량**까지 보려면 서버의
  `/local/api/visitcar/visitor/appuser/{user_id}/recent` 엔드포인트를 쓸 수 있습니다
  (형식은 동일). 이 통합구성요소는 세대 차량만 다룹니다.
- 휴대폰이 아닌 두 번째 토큰으로의 푸시 전달 여부는 단지마다 다를 수 있습니다.
  어느 경우든 폴링 엔진이 보완해 줍니다.
- 자체 아이콘을 `custom_components/happyparking/brand/`에 포함하고 있으며,
  홈어시스턴트 2026.3 버전부터 로컬에서 제공됩니다.
