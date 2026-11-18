# 해피파킹 for Home Assistant

**한국어** · [English](#happyparking-for-home-assistant)

우리 차나 손님 차가 아파트 주차장에 들어오고 나가는 순간을 바로 알 수 있고,
홈어시스턴트가 그에 맞춰 움직이게 할 수 있습니다. 해피파킹 앱을 쓰는 아파트에서
사용할 수 있습니다.

*비공식 통합구성요소입니다. 해피파킹이나 비엔인더스트리에서 만들거나 지원하지 않습니다.*

## 할 수 있는 일

- 차가 드나들 때마다 차량 번호와 게이트가 담긴 **알림**을 받습니다.
- **자동화 트리거**: *세대 차량 입차*, *세대 차량 출차*, *방문 차량 입차*,
  *방문 차량 출차*. 특정 차량에만 반응하게 할 수도 있습니다. 집에 오면 조명을
  켜거나, 가족이 도착하면 전기요를 켜는 식입니다.
- 어떤 차인지 알 수 있는 **로그북**: *12가3456 entered at Main gate*.
- 휴대폰 앱과 같은 푸시로 **즉시** 알려주고, 놓치는 일이 없도록 주기적으로도
  확인합니다.

## 설치

1. [![Marketplace에서 열기](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=dlxmax&repository=happyparking-homeassistant&category=integration)

   버튼을 누르면 홈어시스턴트의 **Marketplace**에 HappyParking이 열립니다.
   설치한 뒤 홈어시스턴트를 재시작하세요.
2. [![통합구성요소 추가](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=happyparking)

   이 버튼으로 통합구성요소를 추가하세요.

버튼이 동작하지 않으면 Marketplace에 이 저장소
(`https://github.com/dlxmax/happyparking-homeassistant`)를 **통합구성요소**
유형의 사용자 지정 저장소로 추가하세요.

## 로그인

설정 화면에 해피파킹 로그인 페이지 링크가 나타납니다.

1. 컴퓨터의 크롬이나 엣지에서 링크를 열고, 평소처럼 카카오나 해피파킹 아이디로
   로그인하세요.
2. **F12**를 누르고 **Application** → **Local Storage** →
   `https://app.hparking.co.kr`에서 **`token`** 값을 복사하세요.
3. 홈어시스턴트에 붙여 넣으세요. 아파트와 계정 정보는 여기서 읽어오므로 따로
   입력할 것이 없습니다.

컴퓨터가 없다면 칸을 비운 채 제출하세요. 해피파킹 아이디와 비밀번호로 로그인할 수
있습니다.

카카오로 로그인해 토큰을 붙여 넣었다면, 나중에 **재인증** 카드가 한 번 나타나
카카오 아이디를 묻습니다. 푸시 알림을 계속 받는 데 필요하며, 찾는 방법은 카드에
안내되어 있습니다.

## 자동화

자동화 편집기에서 **기기** → **HappyParking**을 고른 뒤 트리거를 선택하세요.
특정 차량에만 반응하게 하려면 **특정 차량만** 칸에 차량 번호 전체(`12가3456`)나
뒷자리(`3456`)를 입력하세요. 여러 대는 쉼표로 구분합니다.

예시: 해가 진 뒤 우리 차가 들어오면 현관 조명을 켭니다.

```yaml
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

통합구성요소의 **구성**에서 바꿀 수 있습니다.

| 옵션 | 기본값 | 설명 |
|---|---|---|
| 차량 입·출차 시 알림 표시 | 켜짐 | 알림을 직접 보낸다면 끄세요. 트리거는 그대로 동작합니다. |
| 방문 차량도 함께 확인 | 켜짐 | 세대 차량만 보려면 끄세요. |
| 실시간 푸시 알림 받기 | 켜짐 | 끄면 주기적인 확인만으로 동작합니다. |
| 푸시가 끊겼을 때 확인 주기 | 120초 | 푸시가 연결되지 않았을 때 확인하는 간격입니다. 연결되어 있으면 30분마다 확인합니다. |

## 팁

**로그북 깔끔하게 보기.** 차마다 차량 번호 없는 "entered"·"exited" 줄이 하나 더
남습니다. 차량 번호가 있는 줄만 남기려면 `configuration.yaml`에 다음을 추가하세요.
트리거와 자동화는 그대로 동작합니다.

```yaml
recorder:
  exclude:
    entities:
      - event.happyparking_car_in_out
      - event.happyparking_visitor_in_out
```

<details>
<summary><b>고급 사용자용</b></summary>

- **버스 이벤트.** 차가 드나들 때마다 `happyparking_car` 또는
  `happyparking_visitor` 이벤트가 발생합니다. `state`(`entered` 또는 `exited`),
  `car_no`, `entry_gate`, `entry_time`, `exit_gate`, `exit_time`(출차 전에는
  `null`), `kind`(`household` 또는 `visitor`), `source`(`push` 또는 `poll`),
  `device_id`가 담깁니다. 기기 트리거에서도 같은 값을 `trigger.event.data`로 받을
  수 있습니다.
- **이벤트 엔티티.** `event.happyparking_car_in_out`,
  `event.happyparking_visitor_in_out`.
- **푸시 테스트.** `happyparking.test_push` 액션을 실행하면 주차 서버가 테스트
  푸시를 보냅니다. 도착하면 개발자 도구 → 이벤트에 `happyparking_push`가
  나타납니다.
- **기타 옵션.** *이 브리지의 기기 ID*와 *서버 TLS 인증서 검증*은 거의 바꿀 일이
  없습니다. 확인 주기를 `0`으로 두면 푸시만 사용합니다.
- **브라우저 없이.** 로그인 칸을 비운 채 제출하면 서버 정보를 직접 입력할 수도
  있습니다.

</details>

## 그 밖에

변경 내역은 [CHANGELOG](CHANGELOG.md)에 있습니다. 이슈와 풀 리퀘스트를 환영합니다.

> 아래에 같은 내용이 영어로 이어집니다.
> The same guide in English follows below.

---

# HappyParking for Home Assistant

[한국어](#해피파킹-for-home-assistant) · **English**

Know the moment your car, or a visitor, enters or leaves your apartment's
parking lot, and let Home Assistant act on it. For apartments that use the
HappyParking (해피파킹) app.

*Unofficial. Not made or supported by HappyParking or BN Industry.*

## What you get

- **A notification** for each car coming or going, with the plate and the gate.
- **Automation triggers**: *Car entered*, *Car exited*, *Visitor entered*,
  *Visitor exited*, optionally for particular plates only. Turn the lights on
  when you get home, warm the bed when your partner arrives, and so on.
- **A logbook** that names each car: *12가3456 entered at Main gate*.
- **Instant alerts**, the same push the phone app gets, with a regular check in
  the background so nothing is missed.

## Install

1. [![Open in Marketplace](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=dlxmax&repository=happyparking-homeassistant&category=integration)

   The button opens HappyParking in your Home Assistant **Marketplace**.
   Install it, then restart Home Assistant.
2. [![Add integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=happyparking)

   Use this button to add the integration.

If the buttons don't work, add this repository
(`https://github.com/dlxmax/happyparking-homeassistant`) to the Marketplace by
hand as a custom repository of type **Integration**.

## Sign in

Setup shows a link to HappyParking's own login page.

1. Open it in Chrome or Edge on a computer and sign in as you always do, with
   Kakao or your HappyParking id.
2. Press **F12**, open **Application** → **Local Storage** →
   `https://app.hparking.co.kr`, and copy the value of **`token`**.
3. Paste it into Home Assistant. Your building and account are read from it,
   so there is nothing else to fill in.

No computer to hand? Leave the box empty and submit to sign in with a
HappyParking id and password instead.

If you signed in with Kakao by pasting the token, Home Assistant later asks
once, on a **Re-authenticate** card, for your Kakao id. It needs that to keep
push alerts running, and the card shows where to find it.

## Automations

In the automation editor choose **Device** → **HappyParking**, then a trigger.
To react to one car only, type its plate in **Only these plates**: the whole
plate (`12가3456`) or its last digits (`3456`). Separate several with commas.

Example: when your car comes home after dark, turn on the hallway light.

```yaml
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

Under **Configure** on the integration:

| Setting | Default | What it does |
|---|---|---|
| Show a notification for each car | On | Turn off if you send your own alerts. Triggers keep working. |
| Also watch visitor cars | On | Turn off to follow household cars only. |
| Receive instant push alerts | On | Turn off to rely on the regular check alone. |
| Check interval while push is down | 120 s | How often to check when push is not connected. While it is, the check runs every 30 minutes. |

## Tips

**A cleaner logbook.** Each car also leaves a bare "entered" or "exited" row.
To keep only the rows with the plate, add this to `configuration.yaml`.
Triggers and automations keep working.

```yaml
recorder:
  exclude:
    entities:
      - event.happyparking_car_in_out
      - event.happyparking_visitor_in_out
```

<details>
<summary><b>For advanced users</b></summary>

- **Bus events.** Every movement fires `happyparking_car` or
  `happyparking_visitor`, with `state` (`entered` or `exited`), `car_no`,
  `entry_gate`, `entry_time`, `exit_gate`, `exit_time` (both `null` until the
  car leaves), `kind` (`household` or `visitor`), `source` (`push` or `poll`)
  and `device_id`. Device triggers pass the same data as `trigger.event.data`.
- **Event entities.** `event.happyparking_car_in_out` and
  `event.happyparking_visitor_in_out`.
- **Testing push.** The `happyparking.test_push` action asks the parking server
  to send a test push. When it arrives, a `happyparking_push` event appears in
  Developer tools → Events.
- **Other options.** *Device ID for this bridge* and *Verify the server's TLS
  certificate* rarely need changing. A check interval of `0` means push only.
- **Without a browser.** Submitting the sign-in box empty also offers entering
  the server details by hand.

</details>

## More

Changes are listed in the [changelog](CHANGELOG.md). Issues and pull requests
are welcome.
