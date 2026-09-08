# 변경 내역 · Changelog

모든 항목은 한국어 다음에 영어가 이어집니다.
Every entry appears in Korean first and in English afterwards.

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
