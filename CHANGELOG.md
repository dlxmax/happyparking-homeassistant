# 변경 내역 · Changelog

모든 항목은 한국어 다음에 영어가 이어집니다.
Every entry appears in Korean first and in English afterwards.

## v0.9.0

### 한국어

**수정**

- **푸시 등록과 `test_push`가 다시 동작합니다.** 주차 서버가 이제 푸시 관련 요청에
  24시간짜리 로그인을 요구해, 지금까지는 모두 401로 거부되고 있었습니다.
  홈어시스턴트가 앱과 같은 방식으로 이 로그인을 받아 만료 전에 스스로 갱신합니다.
- **실제 입·출차 푸시가 이제 도착합니다.** 사용하던 FCM 라이브러리가 형식이 약간 다른
  메시지 하나를 해독하지 못하고 수신을 멈춰 버려, 그동안 어떤 푸시도 받지 못했습니다.
  서버는 처음부터 차량 알림을 보내고 있었습니다. 이제 이런 메시지도 읽을 수 있고,
  끝내 읽지 못한 메시지는 기록만 남기고 넘어가므로 수신이 멈추지 않습니다.
- `test_push`가 거부되었을 때 성공으로 보고하지 않고 오류를 표시합니다.

**변경**

- README를 더 간결하고 알기 쉽게 개편하고 설치 버튼을 넣었습니다. 아울러 푸시
  기능이 정식 버전으로 전환됨에 따라 옵션 이름에서 '베타' 표기를 제거했습니다.
- **차량 번호가 담긴 로그북 줄이 HappyParking 기기 페이지에도 나타납니다.** 이벤트
  엔티티가 이제 하나의 기기에 속하고, 버스 이벤트에 `device_id`가 담깁니다.
- 빈 `entered` / `exited` 줄을 없애는 방법이 다시 **recorder 제외**가 되었습니다.
  로그북 제외는 엔티티·기기 화면에서 적용되지 않습니다. v0.8.1부터 차량 번호 줄은
  엔티티를 가리키지 않으므로 recorder 제외로 함께 사라지지 않습니다. README를
  참고해 `logbook:` 제외를 `recorder:` 제외로 옮기세요.

**추가**

- **기기 트리거.** 자동화 편집기에서 HappyParking 기기를 선택하면 세대 차량
  입차·출차, 방문 차량 입차·출차 트리거를 사용할 수 있습니다. 특정 차량
  번호(전체 또는 뒷자리)로 조건을 좁힐 수 있으며, 해당 트리거를 사용하는 자동화는
  기기의 **관련 항목** 탭에 표시됩니다.
- **푸시 수신 감시.** 푸시 수신이 멈추면 1분 안에 감지하여 경고를 남기고 다시
  연결합니다. 이전에는 수신이 조용히 멈춰도 알 수 없었습니다.
- **푸시가 연결되어 있으면 폴링은 30분마다만** 수행합니다. 연결이 끊기면 설정한
  주기(기본 120초)로 바로 돌아갑니다.
- 카카오 아이디 또는 해피파킹 아이디·비밀번호로 설정하면 갱신용으로 저장됩니다.
  로그인 토큰만 붙여 넣어 설정한 기존 항목은 재인증 카드로 이 정보를 요청합니다.
  폴링에는 영향이 없습니다.
- HappyParking 기기 정보 카드에 해피파킹 웹 앱 링크가 생기고 비공식 브리지임을
  표시하며, 제조사를 HappyParking으로 표기하지 않습니다.

### English

**Fixed**

- **Push registration and `test_push` work again.** The parking server now
  requires a 24-hour login on its push endpoints, so both were being refused
  with 401. Home Assistant now gets that login the way the app does and renews
  it before it runs out.
- **Real car in/out pushes now arrive.** The FCM library could not decrypt one
  slightly differently formatted message, stopped listening, and was handed
  the same message again on every reconnect, so no push ever got through. The
  server had been sending car alerts all along. Such messages are now read,
  and any that still cannot be are logged and skipped, so listening never stops.
- `test_push` reports a refusal as an error instead of as success.

**Changed**

- The README is rewritten, shorter and plainer, with an install button. Push is
  no longer beta, and the option labels no longer say so.
- **The logbook rows with the plate now also show on the HappyParking device
  page.** The event entities now belong to one device, and the bus events carry
  its `device_id`.
- The way to drop the bare `entered` / `exited` rows is a **recorder exclude**
  again. A logbook exclude is ignored on entity and device pages. Since v0.8.1
  the plate rows don't name the entity, so a recorder exclude no longer takes
  them down too. Move your `logbook:` exclude to `recorder:` as the README shows.

**Added**

- **Device triggers.** Pick the HappyParking device in the automation editor
  to trigger on Car entered, Car exited, Visitor entered or Visitor exited,
  optionally narrowed to particular plates (whole, or the last digits).
  Automations that use them show on the device's **Related** tab.
- **A watchdog on push.** If the push listener stops, Home Assistant
  notices within a minute, logs a warning and reconnects it. Before, it could
  stop silently.
- **While push is connected, polling drops to every 30 minutes.** It returns
  to your interval (default 120 s) as soon as push is down.
- Setting up with a Kakao id, or a HappyParking id and password, now keeps it
  for renewing the login. Existing entries set up from a pasted token are asked
  for one through a re-authentication card. Polling is unaffected.
- The HappyParking device's info card links to the HappyParking web app and
  says the bridge is unofficial. It no longer names HappyParking as the
  manufacturer.

## v0.8.1

### 한국어

**수정**

- 버스 이벤트에 더 이상 `entity_id`를 담지 않습니다. 이제 이벤트 엔티티를
  `logbook: exclude:`로 제외하면 엔티티의 기본 `entered` / `exited` 줄만 사라지고
  차량 번호가 담긴 줄은 남습니다. 기존 안내였던 recorder 제외는 차량 번호 줄까지
  지웠으므로 로그북 제외로 바꿨습니다. 차량 번호 줄은 이제 엔티티의 **활동** 목록이
  아니라 메인 로그북에만 나타납니다.

### English

**Fixed**

- The bus events no longer carry `entity_id`. Excluding the event entities with
  `logbook: exclude:` now drops only their bare `entered` / `exited` rows and
  keeps the rows with the plate. The previous advice, a recorder exclude, took
  the plate rows down too, so it is replaced. The plate rows now appear in the
  main Logbook only, not in the entity's **Activity** list.

## v0.8.0

### 한국어

**추가**

- **방문 차량 지원.** 방문 차량 목록을 세대 차량과 **완전히 분리해서** 다룹니다.
  전용 엔티티 `event.happyparking_visitor_in_out`, 전용 버스 이벤트
  `happyparking_visitor`, 로그북에는 **HappyParking visitor**로 기록되고 알림
  제목도 따로 표시됩니다. **구성**의 *방문 차량도 함께 확인*으로 끌 수 있습니다.
- 두 이벤트 모두 `kind` 값(`household` 또는 `visitor`)을 담습니다. 하나의 자동화로
  양쪽을 받아 구분할 수 있습니다.

**변경**

- 문서를 한국어와 영어로 모두 제공하며, 한국어를 먼저 둡니다.
- **푸시는 베타임을 명시했습니다.** 단지에 따라 아예 동작하지 않을 수 있습니다.
  폴링이 항상 함께 돌기 때문에 이벤트를 놓치지는 않으며, 다만 폴링 주기만큼 늦게
  도착합니다. 옵션 이름과 README에 이 점을 분명히 적었습니다.

**수정**

- 홈어시스턴트를 종료할 때 발생하던 오류를 고쳤습니다. 정지 처리가 이벤트 루프가
  아닌 스레드에서 호출되어 `async_stop()`이 실제로 실행되지 않았고, 그 결과 HTTP
  세션과 FCM 클라이언트가 정리되지 않았습니다.

### English

**Added**

- **Visitor car support.** The visitor list is handled **completely separately**
  from household cars: its own entity `event.happyparking_visitor_in_out`, its
  own bus event `happyparking_visitor`, logged as **HappyParking visitor**, and
  its own notification title. Switch it off with *Also watch visitor cars* in
  **Configure**.
- Both events now carry a `kind` of `household` or `visitor`, so one automation
  can listen to both and still tell them apart.

**Changed**

- Documentation is now in both Korean and English, Korean first.
- **Push is documented as beta.** It may not work at your site at all. Polling
  always runs alongside it so nothing is missed, events just arrive a poll
  interval later. The option label and the README now say so plainly.

**Fixed**

- An error on Home Assistant shutdown: the stop handler was called from a thread
  other than the event loop, so `async_stop()` was never awaited and the HTTP
  session and FCM client were left unclosed.

## v0.7.0

### 한국어

**추가**

- **알림 기능이 통합구성요소에 내장되었고, 끌 수 있습니다.** *차량 입·출차 시 알림
  표시* 옵션이 새로 생겼습니다. 기본은 켜짐이며 **구성**에서 해제할 수 있습니다.
  알림을 꺼도 이벤트는 그대로 발생하므로, 이를 이용한 자동화는 영향을 받지 않습니다.
- **로그북에 차량 번호가 표시됩니다.** 이제 단순한 `entered` 대신
  `00가0000 entered at Main gate` 형태로 기록됩니다. 이 줄은 메인 로그북과 이벤트
  엔티티 대화상자의 **활동(Activity)** 목록 양쪽에 모두 나타납니다.

**변경**

- 버스 이벤트에 이벤트 엔티티를 가리키는 `entity_id`가 추가되었습니다. 이 값 덕분에
  위의 로그북 줄이 엔티티의 활동 목록에도 표시됩니다.

**참고**

- 기본 `entered` / `exited` 줄을 감추려고 이 엔티티에 `logbook: exclude:`를 쓰지
  **마세요**. 차량 번호가 담긴 줄도 함께 사라집니다. 대신 `recorder:` 제외를
  사용하세요. 자세한 내용은 README를 참고하세요.
- 그동안 한 대의 설치본에만 존재하던 `enable_push` 옵션과, 방문 기록이 목록에서
  사라졌을 때 모든 페이지를 끝없이 훑지 않고 멈추는 개선도 함께 포함되었습니다.
  v0.6.x 릴리스는 없습니다.

### English

**Added**

- **Notifications are now built in, and optional.** A new option, *Show a
  notification for each car entering or leaving*, is on by default and can be
  switched off in **Configure**. Turning it off costs no events, so automations
  built on them keep working.
- **The logbook now names the car.** A car movement is recorded as
  `00가0000 entered at Main gate` instead of a bare `entered`. The row appears
  both in the main Logbook and in the **Activity** list of the event entity's own
  dialog.

**Changed**

- The bus event now also carries `entity_id`, naming the event entity. This is
  what lets the described logbook row show up in the entity's Activity list.

**Notes**

- Do **not** hide the plain `entered` / `exited` row with a `logbook: exclude:`
  on this entity: it removes the row with the plate too. Use a `recorder:`
  exclude instead. See the README.
- This release also carries the `enable_push` option and a sweep that stops
  instead of walking every page forever once a visit drops out of the window,
  both of which had only ever existed on one installation. There was no v0.6.x
  release.

## v0.5.0 및 이전 · v0.5.0 and earlier

### 한국어

해피파킹 로그인에서 주차 서버 주소·사용자 ID·사이트 코드를 자동으로 읽어오는 기능,
카카오 및 아이디/비밀번호 로그인, 폴링을 안전장치로 둔 FCM 푸시 엔진, 그리고 오래
주차된 차량의 출차를 놓치지 않으면서 과거 기록을 새 이벤트로 잘못 재생하지 않는
목록 조회 방식이 포함되어 있습니다.

### English

Discovery of the parking server, user id and site code from a HappyParking
login; Kakao and id/password sign-in; the FCM push engine with a polling
fallback; and the sweep that catches exits on long-parked cars without
replaying history as fresh events.
