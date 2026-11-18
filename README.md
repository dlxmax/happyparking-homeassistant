# 해피파킹 for Home Assistant

**한국어** · [English](#happyparking-for-home-assistant)

우리 차나 손님 차가 아파트 주차장에 들어오고 나가는 순간을 바로 알 수 있고,
홈어시스턴트가 그에 맞춰 움직이게 할 수 있습니다. 해피파킹 앱을 쓰는 아파트용입니다.

*비공식 통합구성요소입니다. 해피파킹이나 비엔인더스트리에서 만들거나 지원하지 않습니다.*

- 차량 번호와 게이트가 담긴 **알림**
- 세대 차량과 방문 차량의 **자동화 트리거** (특정 차량만 지정 가능)
- 어떤 차인지 알 수 있는 **로그북**: *12가3456 entered at Main gate*
- 휴대폰 앱과 같은 푸시로 **즉시** 전달

## 설치

[![Marketplace에서 열기](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=dlxmax&repository=happyparking-homeassistant&category=integration)

설치하고 홈어시스턴트를 재시작한 뒤, **설정 → 기기 및 서비스**에서
**HappyParking**을 추가하세요.

## 로그인

1. 설정 중에 나오는 로그인 링크를 컴퓨터의 크롬이나 엣지에서 열고, 카카오나
   해피파킹 아이디로 로그인하세요.
2. **F12** → **Application** → **Local Storage** → `https://app.hparking.co.kr`에서
   **`token`** 값을 복사하세요.
3. 홈어시스턴트에 붙여 넣으세요.

컴퓨터가 없다면 칸을 비운 채 제출해 해피파킹 아이디와 비밀번호로 로그인하세요.

카카오 사용자는 **재인증** 카드에서 카카오 아이디를 한 번 더 입력하게 됩니다.
푸시에 필요하며, 찾는 방법은 카드에 안내되어 있습니다.

## 자동화

트리거로 **기기** → **HappyParking**을 고르세요. 특정 차량에만 반응하게 하려면
**특정 차량만** 칸에 차량 번호나 뒷자리를 입력하세요.

```yaml
# 해가 진 뒤 우리 차가 들어오면 현관 조명 켜기
triggers:
  - trigger: device
    domain: happyparking
    device_id: <HappyParking 기기>
    type: car_entered
    plate: "3456"
conditions:
  - condition: sun
    after: sunset
actions:
  - action: light.turn_on
    target:
      entity_id: light.hallway
```

## 설정 옵션

| 옵션 | 기본값 | |
|---|---|---|
| 차량 입·출차 시 알림 표시 | 켜짐 | 꺼도 트리거는 동작합니다. |
| 방문 차량도 함께 확인 | 켜짐 | |
| 실시간 푸시 알림 받기 | 켜짐 | 끄면 주기적으로만 확인합니다. |
| 푸시가 끊겼을 때 확인 주기 | 120초 | 푸시가 연결되어 있으면 30분마다 확인합니다. |

<details>
<summary><b>고급</b></summary>

- **버스 이벤트** `happyparking_car`, `happyparking_visitor`에는 `state`,
  `car_no`, `entry_gate`, `entry_time`, `exit_gate`, `exit_time`(출차 전에는
  `null`), `kind`, `source`(`push` 또는 `poll`), `device_id`가 담깁니다. 기기
  트리거에서도 같은 값을 `trigger.event.data`로 받을 수 있습니다.
- `happyparking.test_push`를 실행하면 서버가 테스트 푸시를 보내고,
  `happyparking_push` 이벤트로 나타납니다.
- 확인 주기를 `0`으로 두면 푸시만 사용합니다.
- 로그북에 차량 번호 없는 줄을 남기지 않으려면 `event.happyparking_car_in_out`과
  `event.happyparking_visitor_in_out`을 `recorder:`에서 제외하세요.

</details>

[변경 내역](CHANGELOG.md)

---

# HappyParking for Home Assistant

[한국어](#해피파킹-for-home-assistant) · **English**

Know the moment your car or a visitor enters or leaves your apartment's parking
lot, and let Home Assistant act on it. For apartments that use the HappyParking
(해피파킹) app.

*Unofficial. Not made or supported by HappyParking or BN Industry.*

- **Notifications** with the plate and the gate.
- **Automation triggers** for household and visitor cars, optionally for
  particular plates.
- **A logbook** that names each car: *12가3456 entered at Main gate*.
- **Instant**, via the same push the phone app gets.

## Install

[![Open in Marketplace](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=dlxmax&repository=happyparking-homeassistant&category=integration)

Install, restart Home Assistant, then add **HappyParking** under
**Settings → Devices & services**.

## Sign in

1. Open the login link shown during setup in Chrome or Edge on a computer, and
   sign in with Kakao or your HappyParking id.
2. Press **F12** → **Application** → **Local Storage** →
   `https://app.hparking.co.kr`, and copy **`token`**.
3. Paste it into Home Assistant.

No computer? Submit the box empty to sign in with a HappyParking id and
password.

Kakao users are asked once more, on a **Re-authenticate** card, for their Kakao
id. Push needs it; the card shows where to find it.

## Automations

Choose **Device** → **HappyParking** as the trigger. To react to one car only,
enter its plate, or its last digits, in **Only these plates**.

```yaml
# Hallway light when your car comes home after dark
triggers:
  - trigger: device
    domain: happyparking
    device_id: <your HappyParking device>
    type: car_entered
    plate: "3456"
conditions:
  - condition: sun
    after: sunset
actions:
  - action: light.turn_on
    target:
      entity_id: light.hallway
```

## Settings

| Setting | Default | |
|---|---|---|
| Show a notification for each car | On | Triggers work either way. |
| Also watch visitor cars | On | |
| Receive instant push alerts | On | Off means checking on a timer only. |
| Check interval while push is down | 120 s | Every 30 minutes while push is up. |

<details>
<summary><b>Advanced</b></summary>

- **Bus events** `happyparking_car` and `happyparking_visitor` carry `state`,
  `car_no`, `entry_gate`, `entry_time`, `exit_gate`, `exit_time` (`null` until
  the car leaves), `kind`, `source` (`push` or `poll`) and `device_id`. Device
  triggers expose the same as `trigger.event.data`.
- **`happyparking.test_push`** asks the server for a test push, which shows up
  as a `happyparking_push` event.
- A check interval of `0` means push only.
- To drop the logbook rows without a plate, exclude
  `event.happyparking_car_in_out` and `event.happyparking_visitor_in_out` from
  `recorder:`.

</details>

[Changelog](CHANGELOG.md)
