# Changelog · 변경 내역

Every entry appears in English first and in Korean afterwards.
모든 항목은 영어 다음에 한국어가 이어집니다.

## v0.7.0

### English

**Added**

- **Notifications are now built in, and optional.** A new option, *Show a
  notification for each car entering or leaving*, is on by default and can be
  switched off in **Configure**. Turning it off costs no events: the event entity
  and the `happyparking_car` bus event still fire, so automations built on them
  keep working. If you already notify from your own automation, turn this off so
  you do not get both.
- **The logbook now names the car.** A car movement is recorded as
  `00가0000 entered at Main gate` instead of a bare `entered`. The row appears
  both in the main Logbook and in the **Activity** list of the event entity's own
  dialog.

**Changed**

- The `happyparking_car` bus event now also carries `entity_id`, naming the
  event entity. This is what lets the described logbook row show up in the
  entity's Activity list; existing automations are unaffected.

**Notes**

- Do **not** hide the plain `entered` / `exited` row with a `logbook: exclude:`
  on this entity. Because the described row names the same entity, excluding it
  removes both and leaves the logbook emptier than before. Use a `recorder:`
  exclude instead, at the cost of the entity's history graph. See the README.
- This release also carries work that had only ever existed on one installation:
  the `enable_push` option, and a sweep that stops at the oldest still-open visit
  instead of walking every page forever once a visit drops out of the window.
  There was no v0.6.x release.

### 한국어

**추가**

- **알림 기능이 통합구성요소에 내장되었고, 끌 수 있습니다.** *차량 입·출차 시 알림
  표시* 옵션이 새로 생겼습니다. 기본은 켜짐이며 **구성**에서 해제할 수 있습니다.
  알림을 꺼도 이벤트는 그대로 발생합니다. 이벤트 엔티티와 `happyparking_car` 버스
  이벤트는 계속 동작하므로 이를 이용한 자동화는 영향을 받지 않습니다. 이미 직접
  만든 자동화로 알림을 받고 있다면, 알림이 두 번 오지 않도록 이 옵션을 꺼두세요.
- **로그북에 차량 번호가 표시됩니다.** 이제 단순한 `entered` 대신
  `00가0000 entered at Main gate` 형태로 기록됩니다. 이 줄은 메인 로그북과 이벤트
  엔티티 대화상자의 **활동(Activity)** 목록 양쪽에 모두 나타납니다.

**변경**

- `happyparking_car` 버스 이벤트에 이벤트 엔티티를 가리키는 `entity_id`가
  추가되었습니다. 이 값 덕분에 위의 로그북 줄이 엔티티의 활동 목록에도 표시됩니다.
  기존 자동화에는 영향이 없습니다.

**참고**

- 기본 `entered` / `exited` 줄을 감추려고 이 엔티티에 `logbook: exclude:`를 쓰지
  **마세요**. 차량 번호가 담긴 줄도 같은 엔티티를 가리키므로 함께 사라져서, 로그북이
  정리되는 것이 아니라 오히려 더 비어버립니다. 대신 `recorder:` 제외를 사용하세요.
  다만 엔티티의 기록 그래프를 잃게 됩니다. 자세한 내용은 README를 참고하세요.
- 이번 릴리스에는 그동안 한 대의 설치본에만 존재하던 작업도 함께 포함되었습니다.
  `enable_push` 옵션, 그리고 방문 기록이 목록에서 사라졌을 때 모든 페이지를 끝없이
  훑지 않고 가장 오래된 미출차 방문에서 멈추는 개선입니다. v0.6.x 릴리스는 없습니다.

## v0.5.0 and earlier · v0.5.0 및 이전

### English

Discovery of the parking server, user id and site code from a HappyParking
login; Kakao and id/password sign-in; the FCM push engine with a polling
fallback; and the sweep that catches exits on long-parked cars without
replaying history as fresh events.

### 한국어

해피파킹 로그인에서 주차 서버 주소·사용자 ID·사이트 코드를 자동으로 읽어오는 기능,
카카오 및 아이디/비밀번호 로그인, 폴링을 안전장치로 둔 FCM 푸시 엔진, 그리고 오래
주차된 차량의 출차를 놓치지 않으면서 과거 기록을 새 이벤트로 잘못 재생하지 않는
목록 조회 방식이 포함되어 있습니다.
