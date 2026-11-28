# 똑똑쌤 예약 상태기계 (v13)

> 2026-11-26 야간 자동 개발 3단계 산출물. `DATA-MODEL.md` §6.1의 7개 상태 enum을 **단일 전이 엔진**으로 확정하고, 앱의 모든 예약 상태 변경 경로를 그 엔진 하나로 모은 결과를 담는다.
>
> 현수 님 지시(2026-11-26 00:33) "디자인·UI는 내가 볼게. 너는 구조와 설계, 탄탄하게"에 따라 **화면 디자인은 바꾸지 않았다.** 이 문서는 표(상태·전이·행위자·알림·슬롯·정산)와 예외 흐름이 본체이고, 코드는 그 표를 그대로 옮긴 것이다.

## 0. 읽는 법

| 구분 | 어디에 있나 |
|---|---|
| 전이 표(코드) | `src/app.template.html` → `TtModel.RESERVATION_TRANSITIONS` |
| 안내 문구 템플릿(코드) | `TtModel.RESERVATION_NOTICES` |
| 검증·기록 함수 | `TtModel.canTransitionReservation`, `TtModel.transitionReservation` |
| 생성·체크인 | `TtModel.initReservation`, `TtModel.recordReservationEvent` |
| 알림·슬롯·정산 반영 | `TtModel.onReservationEffect`로 등록한 앱 핸들러(알림함·타임슬롯·정산 원장) |
| 데이터 정의 | `DATA-MODEL.md` §5 TimeSlot, §6 Reservation, §9 Notification, §10 SettlementLedger |

원칙 세 가지.

1. **상태는 코드(enum)로 저장하고 문구는 화면에서 붙인다.** 저장값은 `received`이고 화면에는 `접수 완료`가 나간다(`TtModel.reservationLabel`).
2. **모든 상태 변경은 `transitionReservation` 하나를 지난다.** 예약 생성·변경·취소·선생님 수락·거절·방문 완료가 모두 같은 검증을 거치므로, 화면마다 규칙이 어긋날 수 없다.
3. **허용되지 않는 전이는 상태를 바꾸지 않고 `{ ok:false, error, message }`로 돌려준다.** 예외(역방향·건너뛰기)는 운영자(`actor: 'operator'`) 권한으로만 열린다.

---

## 1. 상태 7종

| 코드 | 한국어 라벨 | 뜻 | 진입 조건 | 나갈 수 있는 곳 | 화면 노출 |
|---|---|---|---|---|---|
| `received` | 접수 완료 | 결제·접수만 된 상태. 선생님 미정(추천 배정) 가능 | 예약 생성 직후(항상 여기서 시작) / 선생님 배정 거절로 되돌아옴 | `assigned`, `confirmed`, `canceled` | 완료 화면 첫 단계 · 내 예약 |
| `assigned` | 선생님 배정 | 선생님은 정해졌고 방문 확정 전 | 운영자·자동 매칭이 후보를 배정 | `confirmed`, `received`(거절), `canceled` | 관리자·매칭(화면은 다음 단계) |
| `confirmed` | 예약 확정 | 날짜·시간·선생님이 확정 | 보호자가 선생님을 직접 골랐거나, 선생님이 요청을 수락 | `rescheduled`, `completed`, `canceled`, `no_show` | 내 예약 · 캘린더(.ics) |
| `rescheduled` | 일정 변경됨 | 변경 이력이 있는 확정 예약 | 보호자·선생님이 날짜·시간을 바꿈 | `confirmed`, `canceled`, `no_show`(운영자) | 내 예약 |
| `completed` | 방문 완료 | 방문·일지 작성까지 끝 | 선생님이 일지를 저장(방문 완료 처리) | 없음(최종) | 정산 대상 |
| `canceled` | 취소됨 | 취소·환불 규정 적용 | 보호자·운영자가 취소 | 없음(최종) | 내 예약 |
| `no_show` | 노쇼 | 방문 불가·연락 두절 | 선생님·운영자가 노쇼 처리 | 없음(최종) | 정산 제외 |

- **최종 상태(`completed`·`canceled`·`no_show`)에서는 어떤 전이도 허용하지 않는다.** 재확정·재취소는 새 예약으로 만든다(이력·정산이 섞이지 않게).
- `rescheduled`는 "확정이 깨진 상태"가 아니라 **"확정 + 변경 이력"**이다. 그래서 `rescheduled → confirmed`(새 시간으로 재확정)와 `rescheduled → canceled`가 열려 있다.
- `rescheduled → no_show`는 방문 당일 연락 두절을 운영자가 정리할 때만 쓴다(보호자·선생님 단독 불가).

## 2. 전이 표 (허용)

`slot`은 타임슬롯 처리, `알림`은 나가는 안내, `정산`은 원장 트리거다.

| # | from → to | 행위자(허용) | slot | 알림(보호자/선생님) | 정산 |
|---|---|---|---|---|---|
| T1 | `received → assigned` | 운영자, 시스템 | hold(배정 대기) | 선생님 배정 / 새 방문 요청 | — |
| T2 | `received → confirmed` | 보호자, 선생님, 운영자, 시스템 | book(슬롯 점유) | 방문 확정 / 방문 확정 | — |
| T3 | `received → canceled` | 보호자, 운영자, 시스템 | release(슬롯 해제) | 예약 취소 / 방문 취소 | — |
| T4 | `assigned → confirmed` | 선생님, 운영자, 시스템 | book | 방문 확정 / — (본인 행동) | — |
| T5 | `assigned → received` | 운영자, 시스템 | release | 배정 재진행 / 배정 해제 | — |
| T6 | `assigned → canceled` | 보호자, 운영자, 시스템 | release | 예약 취소 / 방문 취소 | — |
| T7 | `confirmed → rescheduled` | 보호자, 선생님, 운영자 | hold(새 시간 재점유) | 일정 변경 / 일정 변경 | — |
| T8 | `confirmed → completed` | 선생님, 운영자, 시스템 | complete(재판매 방지) | 방문 완료 / 방문 완료 처리 | `pending` 행 생성 |
| T9 | `confirmed → canceled` | 보호자, 운영자, 시스템 | release | 예약 취소 / 방문 취소 | — |
| T10 | `confirmed → no_show` | 선생님, 운영자, 시스템 | complete | 노쇼 / 노쇼 | — (정산 제외) |
| T11 | `rescheduled → confirmed` | 보호자, 선생님, 운영자, 시스템 | book | 방문 확정 / 방문 확정 | — |
| T12 | `rescheduled → canceled` | 보호자, 운영자, 시스템 | release | 예약 취소 / 방문 취소 | — |
| T13 | `rescheduled → no_show` | 운영자, 시스템 | complete | 노쇼 / 노쇼 | — |

### 2.1 금지 전이 (대표)

| 금지 | 왜 막나 | 대신 하는 일 |
|---|---|---|
| `completed → *` (재취소·재확정·노쇼) | 정산·리포트가 이미 확정된 방문을 뒤집으면 원장이 흔들린다 | 정정이 필요하면 운영자가 원장을 `adjusted`로 남기고 새 예약을 만든다 |
| `canceled → *` | 취소·환불이 끝난 예약을 되살리면 결제·환불이 이중이 된다 | 새 예약 생성 |
| `no_show → *` | 정산 제외가 확정된 기록 | 새 예약 생성 |
| `received → completed` | 방문 확정 없이 완료될 수 없다(건너뛰기) | `received → confirmed → completed` |
| `received → rescheduled` | 변경할 확정 일정이 없다 | `confirmed`를 먼저 만든다 |
| `confirmed → confirmed`(재확정) | 이력이 늘기만 하고 의미가 없다 | 시간 변경은 `rescheduled` |
| `confirmed → assigned`(배정 취소) | 확정을 되돌리는 역방향 | 운영자 예외: `canceled` 후 재접수 |
| `canceled` 전이를 선생님이 | 보호자 결제·환불 권한 침범 | 선생님은 운영자에게 요청 |

## 3. 행위자와 권한

| 행위자 | 코드 | 할 수 있는 일 |
|---|---|---|
| 보호자 | `customer` | 접수, 확정(선생님 직접 선택), 일정 변경, 취소 |
| 선생님 | `teacher` | 배정 수락(확정), 일정 변경 요청, 방문 완료, 노쇼 처리 |
| 운영자 | `operator` | 배정·재배정, 배정 거절 처리, 모든 취소·노쇼 정리, 역방향 예외 |
| 시스템 | `system` | 자동 매칭·리마인드·배치(정산·슬롯 만료) |

- `actor`를 넘기지 않으면 `system`으로 기록된다. 화면 경로는 항상 실제 행위자를 넘긴다.
- 권한이 없는 조합은 `error: 'actor_not_allowed'`로 막고, 상태는 바꾸지 않는다.

## 4. 안내 문구 템플릿

지금은 **앱 내 알림(`Notification`)과 복사용 문구**로 쓴다. 문자·카카오 발송은 연결하지 않는다(야간 규칙: 메일·문자·전화 금지). `{no}` `{name}` `{date}` `{day}` `{time}` `{refund}`가 치환된다.

| 전이 | 보호자에게 | 선생님에게 |
|---|---|---|
| T1 배정 | **선생님 배정이 끝났어요** — `{no}` 예약에 `{name}` 선생님이 배정됐어요. 방문 확정을 기다리고 있어요. | **새 방문 요청이 배정됐어요** — `{date}` (`{day}`) `{time}` · `{no}` 요청을 수락하면 방문이 확정돼요. |
| T2·T4·T11 확정 | **방문이 확정됐어요** — `{date}` (`{day}`) `{time}` · `{name}` 선생님이 방문합니다. 준비물과 집 안 동선을 확인해 주세요. | **방문이 확정됐어요** — `{no}` 일정으로 방문합니다. 출발 전 보호자에게 도착 예정 시간을 알려 주세요. |
| T7 변경 | **방문 일정이 변경됐어요** — `{no}` 방문이 `{date}` (`{day}`) `{time}`로 변경됐어요. 새 일정으로 캘린더를 다시 받을 수 있어요. | **보호자가 일정을 변경했어요** — `{no}` 방문이 `{date}` (`{day}`) `{time}`로 변경됐어요. 가능한 시간인지 확인해 주세요. |
| T8 완료 | **방문이 완료됐어요** — `{date}` 방문 일지와 회복 리포트가 올라왔어요. 보호자 화면에서 확인해 주세요. | **방문을 완료 처리했어요** — `{no}` 방문이 완료로 기록됐어요. 정산 원장에 지급 예정으로 올라갑니다. |
| T3·T6·T9·T12 취소 | **예약이 취소됐어요** — `{no}` 예약이 취소됐어요. {refund} | **방문이 취소됐어요** — `{no}` `{date}` (`{day}`) `{time}` 방문이 취소됐어요. 그 시간은 다시 열립니다. |
| T10·T13 노쇼 | **방문이 진행되지 않았어요** — `{no}` 방문이 노쇼로 기록됐어요. 새 일정으로 다시 예약해 주세요. | **노쇼로 기록됐어요** — `{no}` 방문이 노쇼로 처리됐어요. 정산에서는 제외됩니다. |
| T5 배정 거절 | **선생님 배정을 다시 진행해요** — `{no}` 예약의 담당 선생님이 어려워져 새 선생님을 찾고 있어요. 확정되면 바로 알려드릴게요. | **배정이 해제됐어요** — `{no}` 방문 배정이 해제됐어요. 다른 요청을 확인해 주세요. |
| 접수 | **`{no}` 접수 완료** — `{date}` (`{day}`) `{time}` 방문 예약이 접수됐어요. 선생님 배정이 끝나면 확정 안내를 보내드릴게요. | **새 방문 예약이 접수됐어요** — `{date}` (`{day}`) `{time}` · `{no}` 배정 후보로 검토해 주세요. |

- `{refund}`는 환불액이 있으면 `환불 예정 금액은 74,000원이에요.`, 없으면 `결제 내역이 없어 환불은 없어요.`로 치환된다.
- 보호자 화면의 알림함에는 `audience: 'customer'`만 보인다. 선생님 알림(`audience: 'teacher'`)은 같은 `Notification` 스키마에 `userId = tch-{teacherId}`로 저장만 하고, 파트너 알림함 화면은 다음 단계다.
- 행위자가 자기 일을 한 경우(선생님이 수락·완료) 그 선생님에게는 알림을 보내지 않는다.

## 5. 예외 흐름

### 5.1 선생님 배정 거절

```
assigned ──(선생님 거절)──▶ received(운영자 기록) ──매칭──▶ assigned ──수락──▶ confirmed
```
- 요청함의 요청 상태(`pending/accepted/rejected`)와 **예약 상태는 따로 둔다.** 요청이 `rejected`로 닫혀도 예약 기록은 `received`로 살아 있어 운영자가 새 선생님을 찾는다.
- 연결된 보호자 예약(`reservationNo`)이 있으면 함께 `assigned → received`로 되돌리고 `teacherId`를 비운다(추천 배정으로 표시).
- 거절한 선생님 본인에게는 알림을 보내지 않는다(`noTeacherNotice`).

### 5.2 보호자 일정 변경 (`rescheduled → confirmed`)

1. 보호자가 내 예약 → 일정 변경에서 새 날짜·시간을 고른다.
2. 엔진이 `canTransitionReservation(status, 'rescheduled', 'customer')`로 먼저 확인한다. `completed`·`canceled`면 화면에서 막는다.
3. 같은 선생님·같은 날·같은 시간에 살아있는 예약이 있으면(`slotConflict`) 저장하지 않는다.
4. 저장되면 `rescheduled`와 이력(`reason: '보호자 요청 일정 변경 → 11.28 (토) 14:00'`)이 남고, 보호자·선생님 알림이 나간다.
5. 선생님이 새 시간을 확인하면 `rescheduled → confirmed`로 다시 확정한다(현재 데모는 보호자 변경 직후 `rescheduled`로 두고, 재확정은 다음 단계 화면).

### 5.3 방문 당일 취소 / 노쇼 기준 (초안 · 현수 님 확인 필요)

| 상황 | 판단 | 상태 | 환불 | 근거 |
|---|---|---|---|---|
| 방문 24시간 전까지 취소 | 보호자 취소 | `canceled` | 전액(100%) | 기존 `refundPolicy` 유지 |
| 방문 24시간 이내 ~ 방문 시각 전 | 보호자 취소 | `canceled` | 50% | 기존 `refundPolicy` 유지 |
| 방문 시각 이후 보호자 취소 | 보호자 취소 | `canceled` | 환불 불가(0%) | 기존 규정 |
| 방문 시각 +30분까지 연락 없음 | 선생님 현장 대기 후 노쇼 처리 | `no_show` | 환불 없음(회차 차감 유지) | **초안** — 유예 시간은 운영 정책으로 확정 |
| 방문 전날 밤~당일 아침 연락 두절 | 운영자가 확인 후 노쇼 | `no_show` | 환불 없음 | **초안** |
| 선생님 사정으로 방문 불가 | 운영자 재배정 | `received`(재배정) | — | T5와 같은 경로, 보호자에게 `선생님 배정을 다시 진행해요` |

- 위 표의 유예 시간(30분)·노쇼 환불 기준은 **가정한 초안**이다. 현수 님이 정하면 이 표만 고치면 되고 코드는 상태 enum만 쓴다.
- 노쇼는 슬롯을 `completed`로 닫아 재판매를 막고, 정산 원장에는 만들지 않는다.

### 5.4 그 밖의 예외

| 예외 | 처리 |
|---|---|
| 같은 선생님·같은 시간 중복 | `slotConflict`로 저장 전 차단, 안내 토스트 |
| 결제 전 이탈 | 예약을 만들지 않는다(현재 데모는 결제 완료 시점에만 생성) |
| 예약 후 선생님 미배정 장기화 | `received`로 두고 운영자 매칭 대기열에서 처리 |
| 방문 완료 후 정정 | 원장 `adjusted`, 예약 상태는 `completed` 유지 |

## 6. 타임슬롯 상태 규칙

슬롯은 별도 테이블로 저장하지 않고 **예약에서 파생**한다(`TtModel.slotRows`). 상태는 아래 규칙으로 계산된다.

| 예약 상태 | 슬롯 상태 | 의미 |
|---|---|---|
| (예약 없음) | `open` | 예약 가능 |
| `received`(선생님 미정) | 슬롯 없음 | 배정 전이라 점유하지 않는다 |
| `assigned`·`confirmed`·`rescheduled` | `booked` | 점유 |
| `completed`·`no_show` | `completed` | 지난 방문, 재판매 금지 |
| `canceled` | `open`(해제) | 다시 예약 가능 |

- `held`(결제 진행 10분 잠금)와 `blocked`(휴무·이동시간)는 데이터 모델에만 있고 결제 연동 단계에서 쓴다.
- DB로 옮길 때는 `(teacher_id, date, start_time)` 유니크 제약이 같은 역할을 한다.

## 7. 정산 원장 규칙

| 전이 | 원장 |
|---|---|
| `→ completed` | 회차 1행 생성: `status: 'pending'`, `grossAmount` = 예약 결제액, `feeRate 0.2222`, `netAmount` = 지급액, `payoutDueDate` = 회차 완료 D+3 확정 후 첫 15일·말일(예: 11/26 완료 → 11/30), `reservationId` = 예약 id |
| `→ canceled` / `→ no_show` | 원장 없음(정산 제외) |
| 이미 같은 `reservationId` 행이 있음 | 다시 만들지 않는다(멱등) |

- 데모의 일지 기반 원장 행(`reservationId: null`, `scheduled`)과 공존한다. 일지를 다시 저장해도 예약 기반 행은 지워지지 않는다(`rebuildLedger`).
- 실제 송금·세금계산서는 이 원장에서 파생하며, 앱은 **기록만** 한다.

## 8. 이력(`statusHistory`) 스키마

```json
{
  "status": "canceled",
  "from": "confirmed",
  "to": "canceled",
  "actor": "customer",
  "reason": "방문 24시간 전 · 전액 환불",
  "at": "2026-11-26T02:11:04.512Z"
}
```

| 필드 | 설명 |
|---|---|
| `status` | 이 시점의 상태(=`to`) |
| `from` / `to` | 전이 전/후. 생성 시 `from: null` |
| `actor` | `customer` / `teacher` / `operator` / `system` (옛 데이터는 `by` 값을 옮겨 담는다) |
| `reason` | 사람이 읽는 사유(환불 규정 라벨, 배정 거절 등) |
| `at` | ISO 8601 UTC |

- 체크인 같은 **비전이 사건**은 `event: 'check_in' | 'check_in_cancel' | 'reschedule_request' | 'journal_shared'`로 `from === to`인 행을 남긴다.
- 예약 레코드의 `updatedAt`은 마지막 이력의 `at`과 같다.
- 옛 저장 데이터(한국어 상태·`by`만 있음)는 로드할 때 `normalizeReservation`이 위 형태로 바꾼다(멱등).

## 9. 코드 API

| 함수 | 입력 | 결과 |
|---|---|---|
| `RESERVATION_TRANSITIONS` | — | `from → to → { actors, slot, notify, kind, ledger }` |
| `canTransitionReservation(from, to, actor?)` | 상태 코드·라벨 모두 허용 | `true/false` (부작용 없음) |
| `transitionReservation(resv, to, meta)` | `meta: { actor, reason, at, refund }` | 성공 `{ ok:true, from, to, actor, at, notice }` / 실패 `{ ok:false, error, message }` |
| `initReservation(resv, meta)` | 새 예약 | `status: 'received'` + 이력 1건 |
| `recordReservationEvent(resv, event, meta)` | `check_in` 등 | 이력 1건 추가(상태 불변) |
| `onReservationEffect(fn)` | 콜백 | 알림·슬롯·정산 반영 |
| `RESERVATION_NOTICES` | — | 상태별 보호자/선생님 문구 |

실패 코드: `invalid_reservation`, `unknown_status`, `unknown_target`, `transition_not_allowed`, `actor_not_allowed`, `event_not_allowed`.

## 10. 앱에서 연결된 경로 (v13)

| 화면 · 동작 | 함수 | 전이 |
|---|---|---|
| 예약 결제 완료 (`결제하고 예약 완료`) | `completeBooking` | 생성 `received` → (선생님 직접 선택 시) `confirmed` |
| 내 예약 → 일정 변경 | `saveManageChange` | `confirmed/rescheduled → rescheduled` |
| 내 예약 → 예약 취소 | `cancelBookingNow` | `received/assigned/confirmed/rescheduled → canceled` |
| 선생님 요청 수락 | `[data-tp-accept]` | 요청 `assigned → confirmed` + 일정 생성 |
| 선생님 요청 거절 | `[data-tp-reject]` | 요청 `assigned → received`(재배정 대기) |
| 선생님 도착 체크인 | `[data-tp-checkin]` | 이벤트 `check_in` / `check_in_cancel` |
| 선생님 일지 저장 | `tpSaveJournal` | 같은 환자 확정 방문 `→ completed` + 원장 |
| 보호자 화면 도착 체크인 | `#checkinBtn` | 이벤트 `check_in` / `check_in_cancel` |

## 11. 아직 남은 일

1. ~~**관리자 화면의 상태 버튼**~~ — **v17 완료.** §2 표와 1:1로 `assigned`·`confirmed`·`completed`·`no_show`·`canceled`·`rescheduled`를 운영자가 직접 바꾸는 화면(`ADMIN-OPERATIONS.md`). T5 배정 해제·T13 노쇼·T7 일정 변경까지 노출된다.
2. **파트너 알림함 화면** — 선생님 알림은 지금 저장만 된다.
3. **`rescheduled → confirmed` 재확정 UI** — 보호자 변경 후 선생님이 확인하는 버튼(관리자 화면은 T11로 가능).
4. **서버 반영** — 이 표를 그대로 `reservations.status` CHECK 제약 + 트리거(알림·원장)로 옮기면 된다.
5. **노쇼 유예 시간·환불 기준 확정** — §5.3 초안을 현수 님이 정한다.
6. **운영자 취소 사유 선택** — 센터·선생님 사정(100% 환불)을 고르는 UI. 지금 운영자 취소는 시간 기준(보호자 구간) 견적만 쓴다.
