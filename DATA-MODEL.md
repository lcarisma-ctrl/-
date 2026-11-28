# 똑똑쌤 데이터 모델 (v12 확정안)

> 2026-11-26 야간 자동 개발 2단계 산출물. 현수 님 지시(2026-11-26 00:33) "디자인·UI는 내가 볼게. 너는 구조와 설계, 탄탄하게"에 따라 **화면은 그대로 두고 데이터 구조만** 확정했다.
>
> 지금 앱은 브라우저 `localStorage`(SafeStorage) 데모다. 이 문서는 그 데모 데이터를 **나중에 PostgreSQL/Supabase로 그대로 옮길 수 있는 정규화 스키마**로 정의하고, 앱 코드(`src/app.template.html`)가 같은 필드명·ID·상태 enum·타임스탬프 규칙을 쓰도록 맞춘 결과를 담는다.

## 0. 이 문서를 읽는 규칙

1. **필드명은 앱 상태(localStorage)의 키와 1:1이다.** 표의 `필드`는 앱 코드와 저장 JSON에서 실제로 쓰는 이름이고, `DB 컬럼`은 옮길 때의 snake_case 이름이다. 이름이 둘인 이유는 기존 화면·테스트를 깨지 않으면서 이전이 기계적으로 되게 하기 위해서다.
2. **모든 엔티티는 `id`(문자열 PK)와 `createdAt`/`updatedAt`(ISO 8601 UTC, 예: `2026-11-25T19:30:00.000Z`)을 가진다.** 표시용 시각(`when`, `date` 등)은 저장하지 않고 화면에서 계산하거나, 호환을 위해 둔 **파생 필드**다(아래 각주).
3. **상태는 한국어 문구가 아니라 enum 코드로 저장한다.** 화면 문구는 `라벨` 열의 값을 렌더링 시점에 붙인다. 데모에 이미 저장된 한국어 상태값은 로드할 때 자동 변환한다(§9 마이그레이션).
4. **삭제는 소프트 삭제**를 기본으로 한다(`status`를 `canceled`/`withdrawn`/`inactive`로). 행을 지우지 않아야 정산·환불·분쟁 대응이 가능하다.
5. 시간대는 저장 UTC, 표시 `Asia/Seoul`. 방문 날짜는 `dateIso`(`YYYY-MM-DD`, 한국 시간 기준 날짜)로 저장한다.

### ID 규칙

| 접두사 | 엔티티 | 예 |
|---|---|---|
| `reg-` | Region | `reg-서울`, `reg-서울-강남구` |
| `usr_` | User | `usr_lq3k9f2x7a` |
| `tch_` | Teacher | `tch_park` (데모는 슬러그 `park`) |
| `trg_` | TeacherRegion | `trg_park_1` |
| `slot-` | TimeSlot | `slot-park-2026-11-27-1030` |
| `res_` | Reservation | `res_lq3k9f2x7a` |
| `rev_` | Review | `rev_lq3k9f2x7a` |
| `cpn_` | Coupon(상품) | `cpn_welcome` |
| `ucp_` | UserCoupon(발급) | `ucp_lq3k9f2x7a` |
| `ntf_` | Notification | `ntf_lq3k9f2x7a` |
| `stl_` | SettlementLedger | `stl_lq3k9f2x7a` |
| `pas_` | Pass(상품) | `pas_p8` |
| `wlt_` | UserPass(보유 이용권) | `wlt_lq3k9f2x7a` |
| `pay_` | Payment(결제·영수증) | `pay_lq3k9f2x7a` |
| `app_` | TeacherApplication | `app_lq3k9f2x7a` |
| `jnl_` | JournalEntry | `jnl_lq3k9f2x7a` |
| `msg_` | ChatMessage | `msg_lq3k9f2x7a` |

- 새 레코드는 `TtModel.newId(prefix)`가 만든다: `<접두사>_<36진수 시각><랜덤>` — 정렬은 시각으로, 충돌은 랜덤으로 막는다.
- **사람이 읽는 번호는 PK와 분리한다.** 예약은 `id`와 별개로 `no`(예: `TT-261127-4821`)를 갖는다. 고객센터·영수증·캘린더(.ics UID)는 `no`를 쓴다. DB에서는 `reservations.reservation_no`에 `UNIQUE`를 건다.
- 지역 ID는 한글 슬러그(`reg-서울-강남구`)다. 운영에서는 `code`에 행정표준코드(법정동코드 10자리)를 채우고 그 값을 조인 키로 쓴다. 데모는 `code = null`.

---

## 1. Region — 시·도 / 시·군·구 / 동 마스터

지역을 코드가 아니라 **데이터**로 둔다. 지역 추가는 개발이 아니라 INSERT다.

앱 위치: `REGIONS`(시·도→시·군·구 목록) + `TtModel.buildRegionMaster()` 결과 `REGION_MASTER`

| 필드 | DB 컬럼 | 타입 | 설명 |
|---|---|---|---|
| `id` | `id` | text PK | `reg-서울`, `reg-서울-강남구` |
| `level` | `level` | enum(`province`,`district`,`dong`) | 3단계 계층 |
| `parentId` | `parent_id` | text FK→Region.id, null | 시·도는 null |
| `name` | `name` | text | `강남구`, `대치동` |
| `fullName` | `full_name` | text | `서울 강남구` (검색·표시용) |
| `code` | `code` | text null | 행정표준코드(법정동코드). 운영에서 채움 |
| `sortOrder` | `sort_order` | int | 화면 노출 순서 |
| `status` | `status` | enum(`active`,`inactive`) | `inactive`는 신규 접수 중단 |
| `createdAt` | `created_at` | timestamptz | |
| `updatedAt` | `updated_at` | timestamptz | |

- v18 데모 마스터: **시·도 17 + 시·군·구 53 + 동 42**. 동은 `REGION_DONGS`(`'시·도 시·군·구' → [동]`) 데이터로 채운다(시드 선생님 `regionDetail`의 동 + 수도권 일부). 전국 동(약 3,500)은 서버 단계에서 행정표준코드와 함께 넣는다.
- 마스터에 없는 지역 문자열은 버리지 않는다. 선생님 지역은 `regionId = null` + `rawName`(원문)으로 보존하고 `미매핑`으로 표시해 마스터를 늘려 간다(§4). v18에서 시드 선생님 17행은 **전부 매핑**됐다(미매핑 0).
- 지역·동을 늘리는 일은 코드 수정이 아니라 데이터 추가다. 절차·조회 함수·캐시는 **`SCALING-ARCHITECTURE.md` §2**가 정본이다.

## 2. User — 보호자·회원

앱 위치: `account.profile` (데모는 1명: `현수`)

| 필드 | DB 컬럼 | 타입 | 설명 |
|---|---|---|---|
| `id` | `id` | text PK | `usr_lq3k9f2x7a` |
| `role` | `role` | enum(`customer`,`admin`) | 선생님 권한은 Teacher 소속으로 판단 |
| `name` | `name` | text | 보호자 이름 |
| `phone` | `phone` | text(암호화) | 예약 확정·방문 안내에만 사용 |
| `phoneVerifiedAt` | `phone_verified_at` | timestamptz null | |
| `regionId` | `region_id` | text FK→Region.id null | 대표 지역(동 단위) |
| `status` | `status` | enum(`active`,`dormant`,`withdrawn`) | 탈퇴는 `withdrawn`(파기 정책 §8) |
| `termsAgreedAt` | `terms_agreed_at` | timestamptz null | 필수 약관 동의 시각 |
| `createdAt` | `created_at` | timestamptz | |
| `updatedAt` | `updated_at` | timestamptz | |

## 3. Teacher — 선생님

앱 위치: `teachers[]` (정적 시드), 파트너 본인 정보는 `partner`

| 필드 | DB 컬럼 | 타입 | 설명 |
|---|---|---|---|
| `id` | `id` | text PK | 데모는 `park` 등 슬러그 |
| `userId` | `user_id` | text FK→User.id null | 선생님 로그인 계정 |
| `name` | `name` | text | 공개 화면은 `maskTeacherName()` 결과 |
| `license` | `license` | enum(`물리치료사`,`작업치료사`,`간호조무사`) | 면허 종류 |
| `occupation` | `occupation` | enum(위와 같음) | **v15** 직종. 현재 `license`와 같은 값 |
| `licenseNo` | `license_no` | text | 국가면허 번호(원본). **공개 화면 금지** |
| `licenseYear` | `license_year` | int null | **v15** 취득 연도(공개 가능) |
| `verification` | `verification` | jsonb | **v15** 검증 3단계 `{identity, license, career}` = `verified`/`pending`/`failed` |
| `verificationVerifiedAt` | `verification_verified_at` | jsonb | **v15** 단계별 통과 시각(ISO, 미통과 null) |
| `licenseVerifiedAt` | `license_verified_at` | timestamptz null | `verification.license`의 호환 필드. **미확인 상태에 "검증" 문구 금지** |
| `years` | `career_years` | int | 경력 연차 |
| `careerHighlights` | `career_highlights` | text[] | **v15** 주요 경력 2~3줄(공개 동의 범위) |
| `tags` | `specialties` | text[] | `뇌졸중`, `보행재활` 등 |
| `quote` | `intro` | text | 한 줄 소개(40자 이내) |
| `availableSummary` | `available_summary` | text | **v15** `평일 오전 · 주말 오후` |
| `availableDays` / `availableTimes` | `available_days` / `available_times` | text[] | **v15** `['월','수','금']` / `['오전','오후']` |
| `firstAvailable` | `first_available` | date | **v15** `2026-11-27` |
| `maxWeeklyVisits` | `max_weekly_visits` | int | **v15** 주당 최대 방문 횟수 |
| `transport` | `transport` | enum(`차량`,`대중교통`) | **v15** 이동 수단 |
| `regionDetail` | `region_detail` | text | **v15** 활동 지역 **시·구·동까지만**(공개는 `publicRegionText()`) |
| `zone` | `zone` | text | 수도권/영남/호남 등 권역(목록 필터용) |
| `rating` | `rating_cached` | numeric(2,1) | **비정규화 캐시**. Review 집계가 원본 |
| `reviews` | `review_count_cached` | int | 위와 같음 |
| `status` | `status` | enum(`pending`,`approved`,`paused`,`rejected`) | 승인 전 노출 금지 |
| `approvedAt` | `approved_at` | timestamptz null | |
| `createdAt` / `updatedAt` | | timestamptz | |

> 평점·후기 수를 컬럼에 두는 이유: 목록·검색에서 매번 집계하지 않기 위해서다. 후기 등록/숨김 시 트리거(또는 배치)로 갱신하고, 원본은 Review다.

> **v15:** 검증 3단계는 `verification` 하나로 닫았다(단계 정의는 코드 상수·문서가 정본, 데이터는 상태만). 규칙·마스킹·화면 적용 지점은 **`TEACHER-VERIFICATION.md`**가 정본이고 이 표는 저장 필드만 옮긴 것이다. `licenseNo` 원본은 보관하되 공개 투영(`teacherPublicProfile`)에는 `licenseMasked`(`제○○-○○○○호`)만 나가고, `exportBundle`은 둘을 함께 내보낸다. 시드 8명 중 이하늘·윤지수는 `career: 'pending'`(카드에 경력 배지 없음), 관리자 심사 큐의 신규 지원서 2건은 3단계 모두 `pending`이다.

## 4. TeacherRegion — 선생님 × 지역 (다대다)

앱 위치: `TtModel.teacherRegionRows(teachers)`

| 필드 | DB 컬럼 | 타입 | 설명 |
|---|---|---|---|
| `id` | `id` | text PK | `trg_park_1` |
| `teacherId` | `teacher_id` | text FK→Teacher.id | |
| `regionId` | `region_id` | text FK→Region.id null | 동 단위 우선, 마스터에 없으면 null |
| `rawName` | `raw_name` | text | 원문 토큰(`일산`, `고양`, `파주`) |
| `priority` | `priority` | int | 1이 대표 지역 |
| `status` | `status` | enum(`active`,`paused`) | 잠시 활동 중지 |
| `createdAt` / `updatedAt` | | timestamptz | |

- 유니크: `(teacher_id, region_id)` (단, `region_id IS NULL`은 rawName으로 별도 유니크).
- 선생님 1명 : 여러 동, 보호자 1명 : 여러 회차 — 둘 다 이 구조로 표현한다.
- **매칭 대기열 쿼리**(접수 → 후보 선생님): `Reservation.regionId`와 `TeacherRegion.regionId` 교집합 ∩ `Teacher.status='approved'` ∩ `TimeSlot.status='open'`(해당 날짜·시간). 결과를 후보 목록으로 보여주고 배정하면 `Reservation.teacherId`와 `TimeSlot.status='booked'`를 함께 갱신한다.
- **v18에서 공백 해소**: `파주`→`reg-경기-파주시`, `서대문`→`reg-서울-서대문구`를 마스터에 등록해 시드 선생님 `TeacherRegion` 17행이 모두 `regionId`를 갖는다. 배정 후보 교집합도 문자열 비교가 아니라 id 비교로 계산한다(`matchCandidateTeachers`).
- 선생님 활동 지역은 아직 **시·군·구 단위**로 저장된다(`regions` 문자열). 동 단위 등록 UI(파트너 화면)와 동까지의 `TeacherRegion` 행은 `SCALING-ARCHITECTURE.md` §14 L1의 남은 일이다. 지금은 방문 지역이 동이어도 `matchRegionIdSet()`이 부모 구를 포함해 교집합을 계산한다.

## 5. TimeSlot — 일정 충돌 방지 슬롯

앱 위치: `TtModel.slotRows(teacherId, dateIso, times, bookings)`

| 필드 | DB 컬럼 | 타입 | 설명 |
|---|---|---|---|
| `id` | `id` | text PK | `slot-park-2026-11-27-1030` |
| `teacherId` | `teacher_id` | text FK→Teacher.id | |
| `dateIso` | `date` | date | `YYYY-MM-DD` (KST 기준) |
| `startTime` | `start_time` | time | `10:30` |
| `endTime` | `end_time` | time | `11:30` (기본 60분) |
| `durationMin` | `duration_min` | int | 60 |
| `status` | `status` | enum(`open`,`held`,`booked`,`blocked`,`completed`) | `held`=결제 진행 중 임시 잠금(10분), `blocked`=선생님 휴무·이동시간 |
| `reservationId` | `reservation_id` | text FK→Reservation.id null | `booked`일 때 필수 |
| `createdAt` / `updatedAt` | | timestamptz | |

- **유니크 제약 `(teacher_id, date, start_time)`** 하나로 이중 예약을 DB에서 막는다. 앱에서도 결제·일정 변경 직전에 `TtModel.slotConflict()`로 같은 선생님·같은 날·같은 시간의 살아있는 예약을 확인하고, 있으면 저장하지 않고 안내한다.
- `held` 만료(10분)는 배치/스케줄러로 `open` 복구. 결제 실패 시 즉시 `open`.
- 방문 완료 시 `completed`. 노쇼면 `blocked`가 아니라 예약 상태 `no_show`로 남기고 슬롯은 `completed` 처리(재판매 방지).

## 6. Reservation — 예약 (핵심)

앱 위치: `account.bookings[]`

| 필드 | DB 컬럼 | 타입 | 설명 |
|---|---|---|---|
| `id` | `id` | text PK | `res_lq3k9f2x7a` |
| `no` | `reservation_no` | text UNIQUE | `TT-261127-4821` 사람이 읽는 번호 |
| `userId` | `user_id` | text FK→User.id | |
| `teacherId` | `teacher_id` | text FK→Teacher.id null | 배정 전 null/빈 값(`추천 배정`) |
| `regionId` | `region_id` | text FK→Region.id null | 방문 지역(동 단위) |
| `addressText` | `address_text` | text(암호화) | 상세 주소. **목록·지도에 절대 노출 금지** |
| `symptomCodes` | `symptom_codes` | text[] | `stroke`, `knee_postop` 등 코드. 자유서술 금지 |
| `passId` | `pass_id` | text FK→Pass.id | 구매한 상품 |
| `walletId` | `wallet_id` | text FK→UserPass.id null | 차감할 보유 이용권 |
| `timeSlotId` | `time_slot_id` | text FK→TimeSlot.id null | 확정 슬롯 |
| `dateIso` | `scheduled_date` | date | `2026-11-27` |
| `time` | `start_time` | time | `10:30` |
| `status` | `status` | enum(§6.1) | |
| `statusHistory` | `status_history` | jsonb | `[{status, from, to, actor, reason, at, event?}]` 감사 이력 — 상세는 `RESERVATION-STATE-MACHINE.md` §8 |
| `amount` | `amount` | int | 실제 결제액(원) |
| `amountList` | `amount_list` | int | 정가 |
| `amountDiscount` | `amount_discount` | int | 쿠폰 할인 |
| `couponId` | `user_coupon_id` | text FK→UserCoupon.id null | 사용한 쿠폰 |
| `paymentStatus` | `payment_status` | enum(`unpaid`,`paid`,`refund_pending`,`refunded`) | |
| `canceledAt` | `canceled_at` | timestamptz null | |
| `cancelReason` | `cancel_reason` | text null | |
| `refund` | `refund_amount` | int null | |
| `refundLabel` | `refund_policy_label` | text null | `방문 24시간 전 · 전액 환불` |
| `createdAt` / `updatedAt` | | timestamptz | |

파생(호환) 필드: `date`(`11.27`), `day`(`금`), `teacher`(선생님 표시명), `region`(지역 표시 문자열). 화면이 이미 이 이름을 쓰고 있어 남겨 두되, **원본은 `dateIso`/`time`/`teacherId`/`regionId`**다.

> **v14:** 예약 생성 시 보호자가 고른 증상이 `symptomCodes`(코드 배열, `stroke`·`knee_postop` 등)로 함께 저장된다. 화면 라벨은 `TtModel.symptomLabel()`로 되돌린다. 접수 요약(`buildIntakeSummary`)은 `regionId`의 시·군·구까지만 쓰고 `addressText`는 넣지 않는다(§12-1).

### 6.1 예약 상태 enum과 전이

| 코드 | 라벨 | 뜻 | 들어가는 곳 |
|---|---|---|---|
| `received` | 접수 완료 | 결제·접수만 된 상태 | 완료 화면 첫 단계 |
| `assigned` | 선생님 배정 | 선생님은 정해졌고 방문 확정 전 | 관리자·매칭 |
| `confirmed` | 예약 확정 | 날짜·시간·선생님 확정 | 결제 완료 직후(데모) |
| `rescheduled` | 일정 변경됨 | 날짜·시간 변경 이력 있음 | 내 예약 |
| `completed` | 방문 완료 | 체크아웃·일지 작성 완료 | 정산 대상 |
| `canceled` | 취소됨 | 취소·환불 규정 적용 | 내 예약 |
| `no_show` | 노쇼 | 방문 불가·연락 두절 | 정산 제외 |

전이(허용): `received → assigned → confirmed → completed`, `confirmed → rescheduled → confirmed`, `received|assigned|confirmed|rescheduled → canceled`, `confirmed → no_show`. **역방향·건너뛰기는 관리자 예외 처리로만** 한다.

> **v13에서 확정:** 위 전이를 `TtModel.RESERVATION_TRANSITIONS` 단일 엔진으로 옮기고, 행위자별 허용/금지·알림 문구·슬롯 변화·정산 트리거까지 표로 닫았다. 표의 정본은 **`RESERVATION-STATE-MACHINE.md`**이고, 이 절은 요약이다. 거절(`assigned → received`)과 `rescheduled → no_show`는 v13에서 운영자 전용 예외로 추가됐다.

누가 무엇을 하는지(§7의 문서 4번 "상담·매칭 흐름"과 같은 표):

| 전이 | 주체 | 보호자에게 나가는 안내 |
|---|---|---|
| 접수(`received`) | 보호자 | "접수 완료" 알림 + 예약번호 |
| 배정(`assigned`) | 관리자/자동 매칭 | "선생님 배정" 알림(선생님 이름·면허) |
| 확정(`confirmed`) | 선생님 수락 | "방문 확정" 알림 + 캘린더(.ics) |
| 변경(`rescheduled`) | 보호자/선생님 | "일정 변경" 알림 + 새 .ics |
| 완료(`completed`) | 선생님 체크아웃 | 회복 리포트 알림 |
| 취소(`canceled`) | 보호자/관리자 | 환불 예정 금액·기한 안내 |
| 노쇼(`no_show`) | 선생님/관리자 | 재예약 안내 |

## 7. Review — 후기

앱 위치: `account.myReviews[]`, `teacherDetails[id].reviews[]`

| 필드 | DB 컬럼 | 타입 | 설명 |
|---|---|---|---|
| `id` | `id` | text PK | |
| `reservationId` | `reservation_id` | text FK→Reservation.id | **방문 1건당 후기 1건**(유니크) |
| `userId` | `user_id` | text FK→User.id | |
| `teacherId` | `teacher_id` | text FK→Teacher.id | |
| `rating` | `rating` | int 1~5 | |
| `body` | `body` | text | 자유서술. 진단명·개인정보 최소화 |
| `tags` | `tags` | text[] | `친절`, `설명` 등 |
| `who` | `author_label` | text | `김*자 보호자` 마스킹 표시명 |
| `status` | `status` | enum(`published`,`hidden`,`reported`) | 신고·숨김 |
| `createdAt` / `updatedAt` | | timestamptz | |

## 8. Coupon / UserCoupon — 쿠폰 상품과 발급

앱 위치: `couponStore[]` (데모는 상품·발급을 한 배열에 합쳐 둠), 코드 사전 `COUPON_CODES`

### 8.1 Coupon (상품)

| 필드 | DB 컬럼 | 타입 | 설명 |
|---|---|---|---|
| `id` | `id` | text PK | `cpn_welcome` |
| `code` | `code` | text UNIQUE null | `WELCOME` |
| `title` | `title` | text | `정규 회차권 10,000원 할인` |
| `sub` | `description` | text | 사용 조건 문구 |
| `type` | `discount_type` | enum(`free`,`amount`,`percent`) | |
| `amount` | `discount_value` | int | 무료권은 0, 정률이면 % |
| `target` | `target` | enum(`eval`,`paid`,`all`) | 적용 상품군 |
| `validFrom` / `validUntil` | | timestamptz | 발급 가능 기간 |
| `status` | `status` | enum(`active`,`paused`,`expired`) | |
| `createdAt` / `updatedAt` | | timestamptz | |

### 8.2 UserCoupon (발급)

| 필드 | DB 컬럼 | 타입 | 설명 |
|---|---|---|---|
| `id` | `id` | text PK | |
| `userId` | `user_id` | text FK→User.id | |
| `couponId` | `coupon_id` | text FK→Coupon.id | |
| `status` | `status` | enum(`available`,`used`,`expired`,`revoked`) | |
| `issuedAt` | `issued_at` | timestamptz | |
| `expireAt` | `expires_at` | timestamptz | |
| `usedAt` | `used_at` | timestamptz null | |
| `usedReservationId` | `used_reservation_id` | text FK→Reservation.id null | |
| `createdAt` / `updatedAt` | | timestamptz | |

파생(호환): `used`(bool) = `status === 'used'`, `expire`(`2026.12.26` 표시), `usedOn`(예약번호).

## 9. Notification — 알림

앱 위치: `notifStore[]`

| 필드 | DB 컬럼 | 타입 | 설명 |
|---|---|---|---|
| `id` | `id` | text PK | 데모 시드는 의미 있는 ID 유지(`nt-visit`) |
| `userId` | `user_id` | text FK→User.id | |
| `kind` | `kind` | enum(`visit`,`remind`,`report`,`coupon`,`system`) | 아이콘 분기 |
| `title` / `body` | | text | |
| `linkTarget` | `link_target` | text | `account`, `report`, `coupon` 등 화면 키 |
| `status` | `status` | enum(`unread`,`read`,`archived`) | |
| `sentAt` | `sent_at` | timestamptz | |
| `readAt` | `read_at` | timestamptz null | |
| `createdAt` / `updatedAt` | | timestamptz | |

파생(호환): `read`(bool), `when`(`오늘 10:20` 표시 문자열).

## 10. SettlementLedger — 회차별 정산 대장

앱 위치: `partner.ledger[]` (데모 시드 + `TtModel.settlementRows()`가 일지에서 생성), 요약은 `partner.settlement`

| 필드 | DB 컬럼 | 타입 | 설명 |
|---|---|---|---|
| `id` | `id` | text PK | |
| `reservationId` | `reservation_id` | text FK→Reservation.id null | 데모 일지는 예약과 1:1이 아니어서 null 허용 |
| `journalId` | `journal_id` | text FK→JournalEntry.id null | 완료 근거 |
| `teacherId` | `teacher_id` | text FK→Teacher.id | |
| `visitDate` | `visit_date` | date | |
| `grossAmount` | `gross_amount` | int | 환자 결제 합계(회차 단가) |
| `feeRate` | `fee_rate` | numeric(4,3) | 기본 `0.2222` (2026-11-26 확정: 90,000 → 70,000) |
| `feeAmount` | `fee_amount` | int | 결제액 − 지급액 |
| `netAmount` | `net_amount` | int | 지급액(보호자 결제액의 78%) |
| `status` | `status` | enum(`pending`,`scheduled`,`paid`,`held`,`adjusted`) | `held`=분쟁·환불 보류 |
| `payoutDueDate` | `payout_due_date` | date | 예: 회차 완료 D+3 확정 후 첫 15일·말일 |
| `paidAt` | `paid_at` | timestamptz null | 실제 송금은 나중(지금은 기록만) |
| `memo` | `memo` | text | 조정 사유 |
| `createdAt` / `updatedAt` | | timestamptz | |

- 회차 1건 = 원장 1행. **지급 상태의 원본은 이 원장**이고, 월 합계는 집계값이다.
- 수수료율은 선생님 계약마다 다를 수 있으므로 `feeRate`를 행에 박아 둔다(나중에 요율이 바뀌어도 과거 정산이 안 흔들리게).
- 실제 송금·세금계산서는 이 원장에서 파생하며, 이 앱은 **기록만** 한다.

## 11. 부속 테이블 (기존 화면이 쓰는 데이터)

| 엔티티 | 앱 위치 | 핵심 필드 | 비고 |
|---|---|---|---|
| `Pass` (이용권 상품) | `passes[]` | id, name, sessions, price, listPrice, per, tag, status, createdAt/updatedAt | 가격표는 데이터. 화면 하드코딩 금지 |
| `UserPass` (보유 이용권) | `account.passes[]` | id, userId, passId, total, remaining, purchased, expire, status(`active`,`exhausted`,`expired`,`refunded`), createdAt/updatedAt | 회차 차감은 예약 확정 시 |
| `Payment` (결제·영수증) | `account.receipts[]` | id, reservationId, no, date, item, amount, listAmount, discount, coupon, method, status(`unpaid`,`paid`,`refund_pending`,`refunded`), createdAt/updatedAt | 환불도 Payment 행 추가(음수 금액) |
| `TeacherApplication` | `adminStore.applications[]`, `partner` | id, name, occupation, license, licenseNo, licenseYear, years, fields, days, availableTimes, transport, intro, province, districts, rate, docs, **verification**(3단계, 신규=pending), status(`pending`,`needs_update`,`approved`,`rejected`), submittedAt, createdAt/updatedAt | 승인 시 Teacher 생성 |
| `JournalEntry` | `partner.journals[]` | id, teacherId, reservationId(null), patientLabel, visitDate, walkSpeed, kneeRom, painScore, memo, status(`draft`,`shared`,`archived`), createdAt/updatedAt | 건강정보 분리 보관 대상 |
| `ChatThread` / `ChatMessage` | `chatStore{}` | threadId, teacherId, userId, as(`customer`,`teacher`), messages[{id, from, body, createdAt}] | 데모는 자동 응답 |
| `PaymentMethod` | `cardStore[]` | id, userId, label, kind(`card`,`pay`), last4, expiry, isDefault, status, createdAt/updatedAt | 카드 원번호는 저장 금지(빌링키만) |
| `RegionNotice` | `REGION_NOTICE_KEY` | id, regionId, userId, createdAt | "우리 동네 열리면 알림" |

## 12. 개인정보·건강정보 원칙 (설계 제약)

1. **최소 수집**: 예약에 필요한 이름·연락처·방문 지역(동까지)·증상 코드만. 주민번호·상세 병력·진단서는 받지 않는다. 상세 주소는 **예약 확정 후 배정된 선생님에게만** 공개한다.
2. **건강정보 분리**: 측정값(보행속도·관절가동범위·통증점수)과 일지는 `journal_entries`에 분리하고, 진단명 자유서술 대신 코드·수치로 남긴다. 접근 권한은 본인·담당 선생님·최소 관리자.
3. **지도·목록 비노출**: 지도와 선생님 목록에는 **동 단위 클러스터**만. 개인 주소·전화·실명은 API 응답에 포함하지 않는다(목록 API와 상세 API를 분리).
4. **암호화**: 전화번호·주소·건강 측정값은 저장 시 암호화(Supabase `pgsodium`/앱 레벨). 로그·분석에 원문을 남기지 않는다.
5. **권한(RLS)**: 보호자는 자기 예약·이용권·알림·후기만, 선생님은 배정된 예약·일지만, 관리자는 심사·정산. 역할을 넘는 조회는 DB에서 차단.
6. **보존·파기**: 탈퇴 시 이름·연락처·주소는 즉시 파기(또는 비식별화), 전자상거래법상 결제·계약 기록은 5년 분리 보관. 건강 측정값은 목적 달성 후 파기.
7. **감사 로그**: 예약 상태 변경은 `statusHistory`, 정산 지급은 `settlement_ledger.paidAt`으로 추적한다. 누가 바꿨는지(`by`)를 남긴다.

## 13. 확장 대비 (현수 님 질문 2026-11-26 00:40 "사업이 커지면?")

- **지역**: 마스터 INSERT만으로 확장. 앱 코드 수정 없음.
- **다대다**: 선생님 1:N 지역, 보호자 1:N 회차, 선생님-환자 배정 이력은 Reservation으로 남는다.
- **매칭 대기열**: 지역·전문분야·가능시간 교집합 쿼리(§4). 사람이 검색하지 않아도 후보가 나온다.
- **일정 충돌**: `(teacher_id, date, start_time)` 유니크 + `held` 임시 잠금.
- **정산**: 회차별 원장 → 월 배치 집계. 요율 변경에도 과거 불변.
- **병목은 코드가 아니라 운영 인력**: 방문 1건당 상담·배정·사후 처리에 약 15분을 가정하면, 하루 20건에서 5시간(0.6명), 50건에서 12.5시간(1.6명)이 필요하다. **하루 30건 부근에서 전담 1명**이 필요하다는 것이 이 가정의 결론이다(가정치이며 실제 측정으로 교체 필요).
- **배정 자동화**: ① 선생님이 가능 시간·지역·분야를 직접 등록 ② 보호자는 지역·증상·시간만 선택 ③ 교집합 후보만 노출 ④ 배정·확정·리마인드 문구 템플릿. 사람이 개입할 예외는 거절·일정 변경·노쇼·컴플레인·후보 0명 5종이다.
- **v18 정본**: 지역 3단계 마스터, 교집합 엔진, 매칭 대기열, 예외 분류, 리마인드 문구, 운영 인력·공급 기준표, 자동 배정 단계(L2~L4)는 **`SCALING-ARCHITECTURE.md`**가 정본이다. 위 15분 가정을 구성 요소로 다시 계산하면 **자동화 후 9.2분/건, 자동화 전 20분/건**이고, 하루 30건에서 자동 0.8명 / 수동 1.7명이 필요하다(모두 가정치).

## 14. localStorage → DB 이전 절차

1. 앱에서 `TtModel.exportBundle(ctx)`를 실행하면 아래 표의 테이블별 배열이 나온다(브라우저 콘솔 `__ttokttokModel.export()`).
2. INSERT 순서: `regions → users → teachers → teacher_regions → passes → coupons → user_passes → user_coupons → time_slots → reservations → payments → reviews → notifications → teacher_applications → journal_entries → settlement_ledger`.
3. FK는 모두 위 순서로 채워지고, `null` 허용 FK는 §4·§10의 사유로 비어 있을 수 있다.
4. 이전 후 `__ttokttokModel.integrity()`가 `{ ok: true }`인지 확인한다(아래 검사 항목).
5. 이전 후에도 데모는 계속 localStorage로 돌아간다. 서버 연결은 다음 단계.

### 저장 키 ↔ 테이블

| localStorage 키 | 테이블 |
|---|---|
| `ttokttok_account_v3` (`schemaVersion: 12`) | users, user_passes, reservations, payments, reviews, journal 연결 |
| `ttokttok_partner_v1` | teachers(본인), teacher_applications, journal_entries, settlement_ledger, 방문 요청/일정 |
| `ttokttok_admin_v1` | teacher_applications, 심사 결정 이력 |
| `ttokttok_coupons_v1` | coupons + user_coupons |
| `ttokttok_notifs_v1` | notifications |
| `ttokttok_cards_v1` | payment_methods |
| `ttokttok_region_v1`, `ttokttok_region_notice_v1` | users.region_id, region_notices |
| `ttokttok_chat_v1` | chat_threads, chat_messages |
| `ttokttok_favs_v1` | (다음 단계) favorites |
| `ttokttok_role_v1`, `ttokttok_phone_v1` | 세션·표시용(테이블 아님) |

## 15. 마이그레이션 규칙 (기존 저장 데이터 보호)

| 옛 값 | 새 값 |
|---|---|
| `status: '예약 확정'` | `confirmed` |
| `status: '일정 변경됨'` | `rescheduled` |
| `status: '취소됨'` | `canceled` |
| `status: '방문 완료'` | `completed` |
| `status: '접수 완료'` | `received` |
| `status: '선생님 배정'` | `assigned` |
| `status: '결제 완료'` (영수증) | `paid` |
| `status: '환불 처리 중'` | `refund_pending` |
| `read: true` (알림) | `status: 'read'`, `read=true` 유지 |
| `used: true` (쿠폰) | `status: 'used'`, `used=true` 유지 |
| `id` 없음 | `TtModel.newId()`로 생성(예약 `no`는 유지) |
| `createdAt` 없음 | 최초 로드 시각으로 채움(이후 불변) |
| `date: '11.27'`, `dateIso` 없음 | `dateIso`를 연도 포함해 계산 |

- 로드 시 `TtModel.normalize*()`가 **멱등**하게 적용된다(두 번 돌려도 같다).
- JSON이 깨졌거나 형태가 다르면 기존처럼 시드로 폴백한다(SafeStorage 원칙 유지).
- 마이그레이션은 **읽기 시 변환 + 즉시 저장**이다. 옛 키는 그대로 두어 이전 버전(v11) 링크가 열려도 데이터가 살아 있다.

## 16. 앱 코드 정렬 결과 (v12 → v13)

| 영역 | v12에서 한 것 |
|---|---|
| ID | 예약·이용권·영수증·후기·쿠폰 발급·결제수단·지원서·일지·채팅 메시지·정산에 `id` 추가. 예약번호(`no`)는 그대로 |
| 상태 | 예약 상태를 enum 코드로 저장하고 화면 문구는 `reservationLabel()`로 변환. 영수증·알림·쿠폰도 enum + 파생 bool |
| 시각 | `createdAt`/`updatedAt` ISO(UTC) 전 레코드. 예약은 `statusHistory` |
| 지역 | `REGION_MASTER`(시·도/시·군·구), `regionIdOf`, `regionIdFromText`, `teacherRegionRows` |
| 슬롯 | `slotRows`, `slotConflict` — 결제·일정 변경 직전 충돌 검사, 예약된 슬롯은 선택 불가 |
| 정산 | `settlementRows` — 완료 일지에서 회차별 원장 생성(지급액·수수료·상태) |
| 안전 | 모든 정규화가 try/catch·기본값. 손상 JSON·옛 데이터·저장 불가 환경에서도 앱이 멈추지 않음 |
| 검증 | `__ttokttokModel`(modelVersion, statuses, regionMaster, export, integrity, slots) + jsdom 데이터 모델 테스트 |
| 상태기계(v13) | `RESERVATION_TRANSITIONS`·`canTransitionReservation`·`transitionReservation`·`initReservation`·`recordReservationEvent`. 모든 예약 상태 변경 경로(생성·변경·취소·선생님 수락/거절·체크인·방문 완료)가 이 엔진을 거치고, 전이 시 `statusHistory`(`from`/`to`/`actor`/`reason`/`at`)·알림·파생 슬롯·정산 원장(`pending`)이 함께 갱신된다. 표·문구·예외는 `RESERVATION-STATE-MACHINE.md` |
| 접수(v14) | `generateReservationId`(예약번호 `TT-YYMMDD-XXXX` 중복검사 발급)·`isValidReservationNo`·`verifyReservationSaved`+`useIntakeReader`(저장 확인: `persisted`/`storageMode`/`reservationId`/`checkedAt`)·`buildIntakeSummary`(보호자 전달용 접수 요약)·`symptomCodesOf`/`symptomLabel`(증상 라벨↔코드). 예약 생성 시 `symptomCodes`가 함께 저장된다(§6). 운영 절차는 `INTAKE-OPERATIONS.md` |
| 검증(v15) | `VERIFICATION_STEPS`(identity/license/career)·`verificationOf`·`isVerified`·`getVerificationBadges`(통과 단계만, 미확인엔 금지 문구 미생성)·`pendingVerificationSteps`·`verificationFromDocs`(관리자 서류 확인 → 단계 전환)·`maskTeacherName`·`maskLicenseNo`(`제○○-○○○○호`)·`publicRegionText`(시·구·동)·`teacherPublicProfile`·`newTeacherApplication`(신규=pending). Teacher·TeacherApplication에 `verification`, 시드 선생님에 직종·취득연도·경력 요약·가능 시간·첫 방문·주당 최대·이동 수단·시·구·동 지역을 채우고 카드·상세 시트·관리자 심사 화면을 이 함수 결과로 통일했다. 규칙은 `TEACHER-VERIFICATION.md` |
| 운영자 예약 큐(v17) | 관리자 콘솔 `#adminResvSec` + `renderAdminResv`·`adminResvCardHtml`·`adminTransitionBooking`. 저장소의 예약(`account.bookings`)을 상태 7종으로 필터(전체/접수/배정/확정/변경/완료/취소·노쇼)하고, 카드마다 `canTransitionReservation(현재, 다음, 'operator')`가 true인 전이 버튼만 그린다(T1~T13 1:1). 실행은 `transitionReservation(..., { actor:'operator', reason })` 한 곳만 지나므로 예약 `status`·`statusHistory`(actor=operator)·알림·파생 슬롯·정산 원장이 v13 규칙대로 함께 갱신되고 보호자 화면에 즉시 반영된다. 배정은 후보 선생님(지역 일치 우선) 선택 + `slotConflict` 차단, 취소는 `applyCancelEffects`로 보호자 취소와 같은 환불·회차 복구 규칙을 쓴다. 안내 문구는 `RESERVATION_NOTICES`(마지막 이력의 notify 키)로 보호자·선생님 문구를 만들어 복사만 한다. **저장은 localStorage(로컬 데모) — 서버·DB 미연결**, 화면 상단에 고정 고지. 전이 표·서버 교체 포인트는 `ADMIN-OPERATIONS.md` |
| 규모 확장·자동 매칭(v18) | 지역 마스터를 3단계(시·도 17 / 시·군·구 53 / 동 42)로 확장하고 데이터(`REGIONS`·`REGION_DONGS`)만으로 지역을 늘리게 했다. 파주·서대문 공백을 해소해 시드 `TeacherRegion` 17행이 모두 `regionId`를 가진다. `TtModel`에 `regionPath`·`regionAncestorIds`·`regionChildren`·`regionTextOf`·`dongIdOf`·`dongIdFromText`·`matchRegionIdSet`·`weekdayOf`·`timeBucketOf`·`weekRangeOf`·`hoursUntil`·`teacherRegionIds`·`teacherAvailability`(요일·시간대·첫 방문일·주간 한도·슬롯)·`matchCandidateTeachers`(지역∩시간 교집합 + 증상은 순위, `matchedBy`/`reasons`/`score`/`blockedBy`)·`buildMatchingQueue`(미배정·재확정 대기열 + 후보 수·1순위)·`classifyOperationalExceptions`(선생님 거절·당일 변경·노쇼·컴플레인·후보 0명)·`buildReminderNotice`(D-1/30분 전)를 추가했다. 관리자 배정 드롭다운은 교집합 후보를 먼저 보여주고 나머지는 기존 지역·평점 순으로 뒤에 붙이며, 카드에 "교집합 후보 n명 · 1순위" 1줄이 붙는다(기존 클래스만 사용, `<style>` 144,471자 동일). 엔진은 **계산만** 한다(저장·발송 없음). 설계·수치·운영 인력 기준표는 **`SCALING-ARCHITECTURE.md`** |
| 방문 일지·주간 리포트·재평가·안전(v20) | `TtModel`에 ① 2분 빠른 일지 — `QUICK_SCALE`(통증·컨디션 1~5)·`QUICK_ACTIVITIES`(8종)·`QUICK_FOCUS`(6종)·`normalizeQuickLog`·`quickLogMissing`/`quickLogMissingLabel`·`quickLogFilled`·`buildQuickJournal`(필수 3종 검증 후 `pain5`/`condition5`/`activities`/`note`/`nextFocus`/`quick:true` 저장, `status:'shared'`)·`quickJournalLine` ② 주간 보호자 리포트 — `journalIsoOf`·`weekRangeOf` 기준 `buildWeeklyReport`(회차·방문일수·컨디션/통증 추이·동작 횟수·특이사항·다음 주 집중)·`weeklyReportText`(공유용 텍스트) ③ 4주 재평가 — `REEVAL_INTERVAL_DAYS=28`·`reevalStateOf`(due/soon/waiting·overdueDays·cycle)·`reevalBadgeOf`·`firstVisitIsoOf`(취소·노쇼 제외)·`buildReevalAlerts` ④ 안전 — `startVisit`/`endVisit`(사건 `visit_start`/`visit_end`, `visitStartedAt`/`visitEndedAt`)·`visitWindowOf`·`visitMinutes`·`SAFETY_CONTACTS`(119·센터·스마트콜)·`SAFETY_STEPS`·`HEALTH_DATA_POLICY`(§12 최소 수집·분리·파기 원칙). 화면: 파트너 `#tpQuickCard`·`#schedHtml`의 방문 시작/종료, 보호자 `#weeklyCard`/`#weeklySheet`·`#journalReeval`·`#visitTimeLine`·`#safetySheet`, 관리자 `#adminReevalBoard`. 저장 필드는 JournalEntry에 `pain5`·`condition5`·`activities[]`·`note`·`nextFocus`·`quick`, Reservation에 `visitStartedAt`·`visitEndedAt`가 추가된 것뿐이고(모두 선택), 서버 이전 시 그대로 옮기면 된다. 문서 정본은 이 절·`STRUCTURE-BACKLOG.md` 5번 |
| 정산 일정·4주 재평가 시드·사업자 표기(v21) | ① 정산일 표기를 **회차 완료 D+3 정산 확정 · 월 2회(15일·말일) 지급**으로 통일 — `TtModel.SETTLEMENT_RULE`(`confirmDays:3`, `payDays:[15,'end']`, `label`)·`settlementRuleText`·`nextPayoutDue(visitIso)`·`payoutDueLabel`(예: 2026-11-26 완료 → 2026-11-30 지급, 2026-11-28 → 2026-12-15). `PRICING.settlementDayOfMonth`(10)를 폐기하고 `settlementConfirmDays`·`settlementPayDays`로 교체, 원장 `payoutDueDate`·파트너 정산 화면(`#tpSettle`·`#tpSettleDetail`)이 같은 함수를 쓴다. ② 기본 시드에 **36일 전 '방문 완료' 1건**(`TT-261019-4811`, 무료 평가, `firstVisitIso`)을 추가 — 관리자 「오늘 처리할 일」 `4주 재평가` 보드(D+8)·보호자 `#journalReeval` 배지가 기본으로 보인다(날짜는 오늘 기준 상대값). 지난 완료·노쇼 예약 카드는 변경·취소·캘린더 버튼 없이 `문의`·`내역`만 그린다. ③ 앱 하단에 사업자 표기 — 시작 화면 `#gateBizInfo`·약관 시트 `#faqBizInfo`에 `상호 똑똑쌤 · 대표 임현수 · 사업자등록번호 발급 진행 중 · 문의 031-919-8577`(기존 `.gate-legal`/`.sheet-note` 클래스만 사용, CSS 바이트 동일). 회차권 가격(320,000·592,000·840,000)은 건드리지 않았다 |
| 내 주변(동 단위)·일지 사진(v22) | ① **선생님 찾기 '목록 / 내 주변(동 단위)' 탭** — 기본은 v15 검증 카드 목록 그대로, `#teacherViewTabs`(`.segmented`)로 전환하고 `#nearPanel`에서 시·도 → 시·군·구 → 동네 클러스터 요약 카드를 보여준다. 계산은 `TtModel.teacherProvinceOf`·`teacherDongList`(regionDetail·`dongs` 마스터 id → 동)·`teacherDistrictList`(동을 모르는 구는 구 단위)·`buildDongClusters`(동네별 활동 선생님 수·3일 내 바로 가능 수·대표 전문분야 3개, 활동 수 내림차순). 카드에는 이름·시·군·구·활동 선생님·바로 가능(3일 내)·전문분야 태그만 있고 **개인 주소·좌표·번지 필드는 없다**(SCALING §12-3). 카드를 누르면 `dongFilter`로 그 동네 선생님만 목록에 남고 `#teacherQueryBar`에 동네 칩(해제 가능)이 뜬다. 디자인은 기존 클래스(`segmented`·`chips`·`card`·`card-head`·`sum-row`·`tag`·`q-chip`·`fine`·`btn btn-outline btn-sm`)만 재사용 — `<style>` 144,471자 바이트 동일. ② **방문 일지 사진 1장(선택)** — 파트너 `#tpQuickCard`에 `#qlPhoto`(file, `hidden`) + `#qlPhotoPick` 버튼 + `#qlPhotoPreview`(미리보기·`사진 빼기`·`#qlPhotoNote` 안내 1줄). 화면에서 캔버스로 긴 변 720px·JPEG로 줄이고(용량 넘으면 품질을 낮춰 재시도·상한 160,000자) `TtModel.normalizePhoto`가 `data:image/(png·jpeg·webp);base64`만 받는다(HTML·SVG 거부). 저장 레코드 `JournalEntry.photo` = `{ thumb, mime, name, width, height, bytes, chars, privacy:'guidance_shown', at }`. 사진이 형식·용량에 안 맞으면 **일지는 저장하고 사진만 빼고** `photoWarning`을 돌려준다. 표시는 보호자 `#journalLatestCard`(최근 방문 일지 상세: 사진·캡션·일지 요약), `#weeklySheet` 회차 카드, 파트너 최근 기록 썸네일. 기기 저장 보호는 `TtModel.pruneJournalPhotos`(최신 3장 유지·전체 1,200,000자 상한, `savePartner`가 자동 적용). 가격·정산·기존 화면 문구는 그대로 |
| 운영 데이터 백업·복원·저장소 어댑터(v23) | ① **워크스페이스 스냅샷** — `TtModel.exportWorkspaceSnapshot(ctx)`가 예약(`account.bookings`)·방문일지(`partner.journals`)·정산원장(`partner.ledger`)·알림(`notifStore`)·선생님 프로필 오버라이드(`ttokttok_teacher_profile_v1`)를 `{ kind:'workspace-backup', schemaVersion:'ttokttok.v23', appVersion:'v23', exportedAt, counts, data }`로 묶는다. **빠른일지 초안(`ttokttok_quicklog_v1`)은 포함하지 않는다**(임시 입력). ② **검증** — `TtModel.validateWorkspaceSnapshot(raw)`가 JSON 파싱 실패·8MB 초과·`__proto__`/`constructor`/`prototype` 키·`schemaVersion` 누락/불일치·필수 배열 4종 타입·예약 `id`/`no` 중복·예약·정산·알림·일지 상태 enum 밖·일지 사진이 `data:image/(png|jpeg|webp)` 아님·160,000자 초과·프로필 배열 필드 타입을 `{ code, message, path }`로 돌려주며 거부하고, `counts` 불일치는 경고만 한다. ③ **복원** — `TtModel.importWorkspaceSnapshot(raw)`는 검증 통과분만 `normalizeReservation`·`normalizeLedgerRow`·`normalizeNotification`·`normalizePhoto`로 정규화해 돌려주고 **저장소를 건드리지 않는다(순수 함수)**. 화면(`#adminBackupSec`)은 파일 확인 → 확인 단계 → `applyWorkspaceSnapshot`(계정·파트너·알림 저장 후 재렌더) 순서로 한 번에 반영한다. ④ **저장소 어댑터** — `TtStorage`(`{ kind, available, get, set, getRaw, setRaw, remove, keys }`)를 두고 `saveAccount`·`loadAccount`·`savePartner`·`loadPartner`·`saveAdmin`·`loadAdmin`·`readJson`/`saveJson`·선생님 프로필 저장이 어댑터를 지나게 정리했다(기존 동작·저장 키·저장 차단 폴백 모두 동일). remote는 `TtStorage.use()` 교체 지점만 두었다. 계약·엔드포인트·마이그레이션 리허설은 **`API-CONTRACT.md`** |
| 보호자 홈 요약·온보딩·FAQ 검색(v25) | ① **요약 계산 순수 함수** — `TtModel.buildGuardianSummary({ bookings, passes, journals, todayIso })`가 `{ nextVisit, passes, report }`를 돌려준다. `nextVisit`은 취소·노쇼·완료·오늘 이전 예약을 빼고 가장 가까운 1건(`bookingNo`·`dateIso`·`dateLabel`·`weekday`·`time`·`teacher`·`status`·`statusLabel`·`dday`·`ddayLabel`·`passName`·`upcomingCount`), `passes`는 잔여가 남은 회차권만 만료 임박 순(`total`·`count`·`items[].remaining/total/percent/expire`·`nearestExpire`), `report`는 최근 28일 방문 일지 기준(`rounds`·`visitedDays`·`condition`·`pain`·`activities`·`lastDateIso`·`lastLine`·`nextFocus`·`reeval`[첫 방문 기준 4주 재평가]). 저장·발송·DOM 접근 없음(테스트로 고정). ② **첫 방문 준비 체크리스트 저장 키** — `ttokttok_onboarding_v1`(JSON `{dress,space,docs}: boolean`, 기기 저장만, 서버 전송 없음). `TtModel.normalizeOnboarding`이 알려진 3개 코드만 남기고 나머지는 버린다. ③ **FAQ 데이터 구조** — `FAQ_ITEMS[]`에 `cat`(`reserve`·`refund`·`safety`)·`keys`(검색 동의어)·`q`·`a`. 검색은 질문+본문 텍스트+keys를 공백 제거·소문자로 비교하고, 결과 0건이면 빈 상태와 상담 폼 링크를 보여준다. ④ 화면은 기존 클래스(`card`·`card-head`·`sum-row`·`status`·`tag`·`chips`·`chip`·`input`·`sec-link`·`check`)만 사용해 `<style>` 144,471자 불변 |
| 선생님 정산 명세서·월별 리포트(v26) | **정산 계산 순수 함수** — `TtModel.buildTeacherSettlementStatement(ctx, monthKey)`가 특정 월(`YYYY-MM`, 기본 이번 달)의 회차별 명세서 행을 돌려준다. 입력 `ctx = { todayIso, teacherId, teacherName, ledger, journals, reservations, canceled }`. 행 필드: `id`·`reservationId`·`reservationNo`·`patient`·`visitDate`/`visitDateLabel`·`visitTime`·`type`(`regular`/`free_eval`/`canceled`/`no_show`/`adjusted`)·`typeLabel`·`confirmDate`(방문일+3)·`payoutDueDate`(확정일 이후 첫 15일/말일, v21 `nextPayoutDue` 그대로)·`status`(`paid`/`scheduled`/`pending`/`held`/`excluded`)·`statusLabel`·`consumerAmount`(보호자 결제)·`platformFee`·`payoutAmount`(세전 지급)·`withholdingRate`(0.033)·`withholdingAmount`·`netExpected`. 합계는 `counts`·`byStatus{paid,scheduled,pending,held,excluded}`·`totals{consumer,fee,payout,withholding,netExpected}`, 월 목록은 `months`(데이터가 있는 달 + 이번 달, 최근 6개), 복사·붙여넣기용 `text`. **지급완료는 저장된 `status:'paid'`가 있을 때만** 표기하고(날짜만으로 지급완료를 단정하지 않는다), 취소·노쇼는 금액 0의 `excluded` 행으로 남긴다. 계산만 하며 저장·발송·DOM 접근 없음(테스트로 고정). ② **시드 원장** — `seedPartnerLedger()`가 11월 14회(정규 70,000원 ×14 = 980,000원, 보호자 결제 1,260,000원)와 10월 12회(무료 평가 1회 포함 770,000원)를 만든다. 모든 행에 `reservationId`(원장 보존)와 일지 2건은 `journalId`가 붙어 `rebuildLedger`에서 중복 생성되지 않는다. 파트너 홈 카드(`partner.settlement` 14회·980,000원)와 명세서 합계가 일치한다. ③ **화면** — 선생님 탭 `정산`(`#screen-tp-settle`, 선생님 탭바 5번째, 인라인 `grid-template-columns:repeat(5,1fr)`)에 월 선택 칩·월 요약·회차별 카드·정산서 미리보기 시트(`#settlementPrintSheet`, `DIALOG_ORDER` 등록)·텍스트 복사·JSON 내보내기(`ttokttok-statement-YYYY-MM.json`, `schemaVersion:'ttoktok.statement.v26'`)·인쇄/PDF용 새 창 문서(자체 스타일, 방문일·예약번호·유형/상태·지급일·세전·원천징수·실수령 7열). 월 선택은 기기 저장(`ttokttok_statement_month_v1`)이고, 화면은 기존 클래스(`settle`·`settle-grid`·`settle-cell`·`sum-row`·`admin-card`·`status-badge`·`chips`·`chip`·`btn`)만 써서 `<style>` 144,471자 불변 |
| 관리자 운영 지표 대시보드(v28) | ① **계산 순수 함수** — `TtModel.buildAdminMetrics(ctx, todayIso)`가 `ctx = { bookings, teachers, journals, ledger, period, nowIso }`를 읽어 운영 지표를 계산만 한다(저장·발송·DOM 접근 없음, 테스트로 고정). 기간은 `all`/`7d`/`30d`(`METRICS_PERIODS`). ② **퍼널** — `metricsStageOf(b)`가 `statusHistory`까지 보고 도달 단계(신청1·배정2·확정3·완료4)를 구해 누적 집계한다. 취소·노쇼는 **도달한 단계까지만** 세고 완료에서는 빠지며, `steps[]`·`closed[]`에 건수와 비율(소수 1자리)이 담긴다. ③ **매출·마진** — 완료 회차는 **정산 원장**(`status`가 `held`/`canceled`가 아니고 `grossAmount>0`)의 실제 금액, 확정 회차는 **단가**(`PRICING.consumerPrice` 90,000 / `teacherPayout` 70,000) 예상치로 `guardianTotal`·`teacherTotal`·`platformMargin`·`marginRate`(22.2%)·`avgPerSession`을 만든다. 무료 평가(0원)는 `freeSessions`로만 센다. ④ **지역 갭** — 시·군·구 단위(`metricsDistrictOf`: `regionId` → `regionPath`, 없으면 지역 문자열 앞 두 토큰)로 수요(취소 제외 접수 건)·진행 중·완료를 세고, 공급은 `teacherRegionIds(t)`로 센다. `need = ceil(수요 / 3)`(가정치 `METRICS_VISITS_PER_TEACHER`)·`gap = supply - need`로 **모집 필요/균형/여유** 3분류, 모집 필요 우선 정렬, 선생님 0명 지역은 `summary.noSupply`로 따로 표시한다. ⑤ **매칭 SLA** — 기간과 무관하게 **지금 대기 중**(`received`/`assigned`/`confirmed`/`rescheduled`) 건을 세고, 접수 시각(`createdAt` → `statusHistory[0].at`)에서 24·48시간을 넘긴 미배정 건을 지연으로 뽑는다(`items[]`에 시간·지역·배지). ⑥ **기간 기준** — 퍼널·지역은 **접수일**, 매출·일지 기록률은 **방문일**, SLA는 **지금 대기** 기준이며 `basis{}`에 문구로 담는다(화면 배지에 그대로 표시). ⑦ **복사용** — `adminMetricsText(m)`(퍼널·매출·지역·SLA 요약)과 `adminMetricsCsv(m)`(지표 요약 + 지역 표 CSV). ⑧ **화면** — 관리자 콘솔 상단 `#adminMetricsSec`: 기간 칩 `#adminMetricsPeriods` · KPI 6장(`settle-grid`/`settle-cell`: 완료 전환율·취소·노쇼율·24시간 초과 미배정·예상 플랫폼 마진·모집 필요 지역·일지 기록률) · 퍼널 카드 · 매출/마진 카드 · 지역 카드(`모집 필요` 강조) · SLA 카드 · 「지표 요약 텍스트 복사」/「지역 표 CSV 복사」. 기존 클래스만 사용해 `<style>` 144,471자 불변 |
| 알림·리마인드 센터(v27) | ① **리마인드 큐 순수 함수** — `TtModel.buildReminderQueue(ctx, todayIso)`가 `{ bookings, ledger }`에서 오늘 보낼 리마인드를 만든다. 항목 kind 7종: `visit_d1`(내일 확정·배정·재확정 예약 — 날짜·시각·선생님·준비물 3가지) · `visit_change`(`statusHistory`의 `rescheduled`) · `visit_cancel`(`canceled`) · `visit_substitute`(`assigned→received` = 배정 해제·대체) · `reeval`(v20 `buildReevalAlerts` 재사용) · `settle_confirm`(방문일 +3일 확정, 0~3일 내) · `settle_payout`(확정 후 첫 15일/말일, 7일 내). 카테고리는 `visit`/`report`/`ops` 3종 + `all`, 항목은 `id·kind·category·audiences(customer/teacher)·title·summary·badge·dueIso·dueLabel·bookingNo·prep·target·customer{title,body}·teacher{title,body}`. 0원(무료 평가)·`paid`·`held` 원장 행은 알림에서 제외하고, 변경·취소는 최근 7일(`REMINDER_LOOKBACK_DAYS`)만 모은다. 같은 입력이면 같은 순서(우선순위 → 날짜 → id)를 돌려주며 저장·발송·DOM 접근 없음(테스트로 고정). ② **알림 분류** — `TtModel.notificationCategoryOf(n)`(kind→category: visit·remind·schedule_change·cancel·substitute→visit, report·reeval→report, coupon·system·settle·settlement→ops)와 `summarizeNotifCategories(list, audience)`(카테고리별 전체·안 읽음 수). `notificationPreview(n)`·`reminderPreviewText(item, audience)`는 **발송 전 문구**와 "실제 문자·알림톡 발송 전 로컬 미리보기" 고지를 만든다. ③ **화면** — 보호자 `#notifSheet`·선생님 `#tpNotifSec`/`#tpNotiSheet`에 카테고리 칩·안 읽음 수·필터, 알림 클릭 시 해당 화면 이동 + `#notifPreviewSheet`(문구 미리보기, `DIALOG_ORDER` 등록), 운영자 `#adminReminderSec`(건수·보호자/선생님 문구·복사·전체 복사, 발송 없음). CSS는 v26과 바이트 동일(144,471자) — 기존 클래스(`chips`·`chip`·`notif`·`admin-card`·`admin-fact`·`btn`)만 사용 |
| 고객 후기 신뢰 배지·원클릭 재예약(v29) | ① **후기 태그 마스터** — `TtModel.REVIEW_TAG_MASTER` 5종(`kind` 친절한 설명·`time` 시간 엄수·`assess` 체계적 평가·`pain` 통증 완화·`comm` 보호자 소통). 예전 화면 문구(`친절해요`·`꼼꼼해요`·`설명이 쉬워요`·`시간 약속...`)는 `REVIEW_TAG_ALIASES`로 마스터에 매핑해 센다(마이그레이션 호환). ② **1방문 1후기 규칙** — `TtModel.canReviewReservation(ctx, 예약)`가 `status === 'completed'` + `teacherId` 있음 + 그 예약번호로 쓴 후기 없음(`reviews[].reservationId === no` 또는 예약의 `reviewed`/`reviewId`)을 확인해 `{ok, code(not_found·not_completed·no_teacher·already_reviewed·ok), reason}`을 돌려준다. `reviewableReservations(ctx)`는 작성 가능한 방문만 최근 순으로 나열한다. 후기 저장 시 `account.myReviews[]`(=`Review`: `reservationId`·`teacherId`·`rating`·`body`·`tags[]`)에 남기고 예약에 `reviewed`·`reviewId`·`reviewedAt`을 표시한다. ③ **선생님 신뢰 요약** — `TtModel.buildTeacherTrustSummary(ctx, teacherId)`가 완료 예약(+teacherId 있는 정산 원장, 중복 예약번호 제외)으로 **완료 방문 수·환자 수·재방문 환자/재방문 건수·재방문율**, `teachers` 집계(`rating`·`reviews`)로 **평균 별점·후기 수**(없으면 후기 레코드에서 계산), 상세 시트 후기 태그로 **대표 태그 TOP 3**(많은 순, 동률은 마스터 순서), `verification`으로 **검증 배지**(통과 단계만)를 만든다. 저장·발송·DOM 접근 없음(테스트로 고정). ④ **원클릭 재예약** — `TtModel.buildRebookDraft(ctx, 예약, opts)`가 같은 선생님·시·도/시·군·구(regionId 분해)·증상(`symptomCodes`→라벨)·이용권(`p1` 1회 90,000원 기본, `opts.passId`로 회차권 지정)을 채운 초안을 돌려준다. **무료 평가(`eval`)는 절대 기본값이 아니다**(`freeEval:false`). 취소·노쇼·담당 선생님 없는 예약은 `not_rebookable`/`no_teacher`로 거부한다. 화면은 `startBooking({teacherId, syms, province, district, passId, rebook})`으로 1~4단계에 미리 채우고 `#rebookBanner`에 같은 조건을 안내한다(주소는 개인정보라 채우지 않고 보호자가 확인). ⑤ **화면** — 후기 시트(`#reviewSheet`) 태그 칩 5종·`#reviewRuleNote`(방문 1회당 후기 1개), 후기 목록(`#reviewList`)에 방문 완료 예약과 등록됨 표시, 선생님 카드 대표 태그·상세 시트 `#teacherTrustBlock`(평균 별점·후기·완료 방문·재방문·대표 태그·검증), 홈 요약 `#homeSummaryRebook`·내 예약 목록/완료 상세의 `같은 선생님으로 다시 예약`. 기존 클래스만 사용해 `<style>` 144,471자 불변 |

| 빈 상태·로딩·오류·입력값 보존(v32) | ① **빈 상태 한 곳** — `TtUI.PRESETS` 28종(booking-list·wallet-passes·receipts·journal-timeline·teachers-filter·teachers-fav·near-empty·search-teacher·notif-list·notif-filter·tp-notif·tp-requests·tp-schedule·tp-journals·tp-settle·coupons·cards·reviews·faq-empty·chat-log·admin-queue·admin-recent·admin-resv·admin-ops-queue·admin-reminders·admin-metrics-regions)이 「짧은 제목 + 한 줄 설명 + 다음 행동 CTA」를 같은 구조(`.empty.empty-v7` + `data-empty`)로 그린다. CTA는 기존 위임 동작(`data-go`·`data-book`·`data-admin-resv-filter` 등)을 그대로 쓴다. ② **로딩** — `TtUI.loadingHtml`/`showLoading`(`role=status`·`aria-busy`·`data-loading`, 점 애니메이션)과 `TtUI.busy`/`idle`(버튼 `disabled`+`data-busy`+문구 교체, 이중 클릭 차단). 실제로 기다리는 구간에만 쓴다: 결제 접수(900ms)·2분 일지 저장·사진 축소(720px)·백업 파일 읽기/복원·목록 다시 불러오기(`TtUI.reload`). ③ **오류+재시도** — `TtUI.showError`({key,title,message,retry}) + `TtUI.onRetry(key, fn)`. 사이트: 계정 읽기(손상 JSON → 예시 데이터로 열고 「다시 읽기」)·저장 실패(계정·파트너·관리자·JSON 저장 → 상단 띠 `#ttAlertHost` + 「다시 저장」)·결제 접수 실패(`#bookError`)·일지 저장 실패(`#qlError`)·백업 파일 거부/읽기 실패/복원 실패(`#adminBackupError`). ④ **입력값 보존** — 예약 4단계 입력은 `TtUI.saveDraft`(저장소 어댑터 키 `ttokttok_draft_v32_booking`)로 남기고, `startBooking()`은 **미리 채울 조건이 없으면 작성 중인 위저드를 초기화하지 않는다**. 새로 열면 `#bookResume` 「이어서 작성」 카드로 복원(24시간 이내 초안), 접수 완료·「새로 예약」에서 초안을 지운다. 실패한 결제·일지는 입력을 그대로 둔 채 「다시 시도」가 같은 값으로 다시 실행한다. ⑤ `<style>`은 144,471자 그대로(디자인 토큰은 v35) — 기존 클래스와 인라인 스타일만 사용 |
| 첫 방문 전 홈 마감(v33) | **계산(순수 함수)** — `TtModel.guardianStageCounts(ctx)`가 예약(진행·완료·취소·노쇼)·회차권 잔여·**이 보호자와 연결된 일지**를 센다. 일지는 `reservationId`/`bookingNo`가 이 계정 예약의 `no`·`id`와 일치하거나 `patient`가 보호자 이름으로 시작할 때만 포함한다(기본 시드 파트너 일지는 다른 어르신 기록이라 제외). `TtModel.buildGuardianHomePlan(ctx)`는 `stage: 'pre_first' \| 'active'`(**진행·완료 예약 0 && 잔여 회차 0 && 연결 일지 0 → pre_first**, 취소·노쇼만 있으면 첫 방문 전), `actualStage`, `preview`(`stageOverride`로 화면만 바꾼 경우), `firstCard`, `summaryHidden`, `counts`, `firstVisit`(안내 문구·가치 3·순서 3·CTA 2), v25 `summary`를 돌려준다. 저장·발송·DOM 접근 없음. **화면** — `#homeFirstVisitCard`가 첫 방문 전에는 `#homeSummaryCard` 앞으로 가고 요약 카드는 `hidden`, 이용 중에는 반대로 돌아간다(`renderHomeStage`가 DOM 순서만 바꾼다 — 정적 마크업은 v25 그대로). 첫 방문 전에는 같은 말을 하는 `#homeNotice`도 접는다. **미리보기** — 관리자 콘솔 `#adminHomeStageSec`(지금 상태·첫 카드·건수 + 첫 방문 전/실제 상태 버튼)와 `?stage=first`는 `homeStagePreview` 변수만 바꾸고 localStorage·계정 데이터는 쓰지 않는다. |


## 17. 아직 남은 일 (다음 단계)

- **화면 문구의 기준은 `GLOSSARY.md`다(v38)**: 역할·상품·기록 이름(보호자·선생님·회차권·회차·방문 일지)과 말투(화면=해요체, 약관·결제·안전·인쇄 문서=합니다체)를 한 문서에 고정했고, `TtModel.COPY_TERMS`·`COPY_BANNED`·`auditCopy()`가 같은 표를 코드로 들고 있다. 새 화면·새 문구를 넣을 때 이 표를 먼저 보고, `tests/app.v38.test.js`의 금지어 0 검사를 통과시킨다. FAQ 검색 키워드에만 옛 표현(`이용권`·`패키지`·`회기`)을 남긴다(`COPY_SEARCH_ALIASES`).
- **첫 방문 전 판정과 '내 일지'(v33)**: `guardianStageCounts`는 일지를 **이 보호자와 연결된 것만** 센다(예약번호·예약 id 일치, 또는 `patient`가 보호자 이름으로 시작). 반면 v25 요약 카드의 4주 리포트(`buildGuardianSummary`)는 여전히 `partner.journals` 전체를 읽으므로 기본 시드에서는 '최근 4주 방문 2회'로 보이면서 '내 일지 0건'일 수 있다(관리자 미리보기 카드). 서버(L1)에서 일지에 `memberId`/`reservationNo`를 필수로 저장하고 조회를 보호자 기준으로 바꾸면 두 숫자가 같아진다.
- **신규 보호자 진입 경로 없음(데모)**: 게이트(`data-login`)는 역할만 바꾸고 계정은 기본 시드로 고정이다. 그래서 '첫 방문 전' 화면은 빈 저장·`?stage=first`·관리자 미리보기로만 보이고, 실제 신규 가입(빈 계정 생성)은 서버·인증 단계의 일이다.
- **후기·신뢰 배지는 이 기기 기록 기준이다(v29)**: `buildTeacherTrustSummary`는 화면에 보이는 예약·후기(상세 시트 후기 태그)와 `teachers`의 집계 별점·후기 수를 읽는다. 그래서 ① 기본 시드는 완료 방문이 1회(박서준, 36일 전 무료 평가)라 재방문은 `재방문 기록 없음`으로 나온다(선생님 데이터의 `revisit` 96% 같은 표시값과 다른, 계산된 값이다). ② 후기 수는 `teachers[].reviews`(시드 집계)에서 시작해 내가 쓴 후기마다 +1 된다(서버 집계 아님). ③ 후기 태그는 상세 시트 후기(시드 2건 + 내 후기)의 `tags[]`로 세므로, 시드 후기에 태그가 없는 선생님은 대표 태그가 비어 있다. 서버(L1) 단계에서 `reviews` 테이블 집계·정식 재방문 정의(같은 보호자 2회 이상)로 교체한다.
- **원클릭 재예약은 초안까지다(v29)**: 같은 선생님·지역·증상·1회권(90,000원)을 1단계에 채우고, **방문 주소는 채우지 않는다**(개인정보 최소화 — 보호자가 확인·입력). 날짜·시간·결제수단·동의는 그대로 보호자가 고른다. 실제 재예약 저장은 기존 예약 생성 경로(중복 시간 차단·상태기계)를 그대로 지난다.
- **서버(L1) 미착수** — v23은 프론트엔드 선행 준비(백업·복원 + `TtStorage` 어댑터 + `API-CONTRACT.md`)까지다. 실제 저장은 여전히 브라우저 `localStorage`다. 서버 선택·테이블 생성·인증·remote 어댑터 구현이 다음 단계이고, 계약과 리허설 체크리스트는 `API-CONTRACT.md` §4~§8에 있다.
- **사업자등록번호는 발급 전**: 앱 하단·약관 시트 표기는 `사업자등록번호 발급 진행 중`이다. 신규 개인사업자 '똑똑쌤' 등록이 끝나면 `#gateBizInfo`·`#faqBizInfo`와 파트너 랜딩(`partner-landing.html`) 푸터 `{{사업자등록번호}}`를 실제 번호로 바꾼다(설반 702-31-00546은 쓰지 않는다 — `projects/ttokttok-business/naver-setup/place-setup.md`).
- **파트너 랜딩 푸터 자리표시자**: `projects/ttokttok-recruit/partner-landing.html`은 아직 `{{상호}}`·`{{대표명}}`·`{{사업자등록번호}}`·`{{연락처}}`·`{{이메일}}` 자리표시자다(초안·noindex).
- **검증 3단계 자동 조회**: 면허 진위 자동 조회(보건복지부/심평원)를 `verification.license`에 연결. 지금은 관리자 수동 확인(`verificationFromDocs`). 실패(`failed`) 사유 코드와 재확인 요청 흐름은 `TEACHER-VERIFICATION.md` §8.
- **동 단위 지역 마스터(부분 완료)**: v18에서 동 42개를 등록했고 v22에서 **선생님 찾기 '내 주변' 클러스터**(동/시·군·구 요약 카드)를 붙였다. 전국 동(약 3,500)은 여전히 `SCALING-ARCHITECTURE.md` §14 L1/L2 과제다(마스터에 없는 구는 '구 단위' 카드로 묶인다).
- **내 주변 탭은 지도 타일이 아니다**: 개인 주소·좌표를 다루지 않으려고 지도 이미지 없이 시·도/시·군·구/동 클러스터 카드만 보여준다. 지도가 필요하면 동 중심점(좌표) 데이터와 타일 API를 서버 단계에서 붙이고, 지금 구조(클러스터 계산 = `buildDongClusters`)를 그대로 마커로 쓰면 된다.
- **일지 사진 보관 정책**: 지금은 기기(localStorage)에만, 최신 3장·약 880KB 상한으로 남긴다(`pruneJournalPhotos`). 서버 이전 시 파일 저장소(S3 등)·접근 권한(보호자·담당 선생님만)·보관 기간(재활 목적 종료 시 파기, §12)과 썸네일 파이프라인을 정해야 한다. 의료 사진에 준하는 민감도로 다룬다.
- **알림은 아직 '문구'까지다(v27)**: `buildReminderQueue`가 만든 리마인드와 알림함은 **기기 안 문구 미리보기·복사**까지만 한다. 실제 문자·카카오 알림톡 발송기, 발송 이력 테이블(`notification_deliveries`), 수신 동의·야간 발송 제한, 실패 재시도는 서버(L1) 단계에서 붙인다. `notifications` 테이블은 지금도 앱 안 알림만 담는다.
- **기본 시드에는 방문 D-1 카드가 안 보인다**: 시드 확정 예약 `TT-261021-7302`의 `dateIso`가 오늘+2일이라, D-1 리마인드는 내일 예약이 생겨야 뜬다(시드 날짜는 v12부터의 불일치 건이라 손대지 않았다). 재평가·정산 확정/지급 예정 카드는 기본 시드로도 보인다.
- **운영 지표는 이 기기 데이터 계산이다(v28)**: `buildAdminMetrics`는 화면에 보이는 예약·선생님·일지·정산 원장만 읽는다. 그래서 ① 기본 시드는 예약이 2건(확정 1·완료 1)이라 퍼널 숫자가 작고, **모든 시드 예약의 `createdAt`이 처음 저장한 시각**이라 기간 칩(7일/30일)을 바꿔도 퍼널·지역은 그대로다(매출·일지만 방문일 기준이라 기간별로 달라진다). ② 매출의 완료 회차는 **박서준 선생님 정산 원장** 기준이므로 플랫폼 전체 매출이 아니라 이 계정의 데모 수치다. ③ 선생님 1명당 3건(`METRICS_VISITS_PER_TEACHER`)은 모집 필요 판정용 가정치이고, 선생님 활동 지역이 마스터에 매핑되지 않으면 공급 0명으로 계산된다. 서버(L1) 단계에서 기간별 집계 API로 교체한다.

- **시드 예약 1건의 날짜 불일치 → v40에서 해결**: `TT-261021-7302`은 `date: '11.27'(금)`인데 `dateIso`는 `2026-11-28`(토)이었다. v40에서 **라벨·요일을 `dateIso`에서 계산**(`dateLabelOf`/`weekdayOf`)하도록 바꾸고, `normalizeAccount`가 기기에 저장된 옛 라벨도 로드 때 교정한다. 앱 안 날짜는 이제 화면·캘린더·D-day 모두 `2026-11-28 (토)`로 같다(시드 라벨은 `nextIso(2)` 기준 계산).
- **동 단위 지역 마스터 비어 있음**: 선생님 활동 지역 중 `파주`(이하늘), `서대문`(정민아)은 마스터에 없어 `regionId=null` + `rawName`으로 남겼다. 마스터를 늘리면 자동으로 연결된다.
- 동 단위 지역 마스터 채우기(수도권 우선) + 선생님 활동 동 등록 UI.
- **운영자 예약 큐의 서버화**: 지금은 localStorage 목록을 한 화면에 다 그린다. 서버 전환 시 `GET /admin/reservations`(상태·기간·페이지네이션)·전이 API의 서버 검증·`audit_log`·낙관적 락(`updatedAt`/`version`)이 필요하다(`ADMIN-OPERATIONS.md` §7).
- **운영자 취소 사유 선택**(센터·선생님 사정 100% 환불): 지금은 시간 기준 견적만 적용.
- **예약 `teacherId` 기본값 `park` 제거**: 옛 데이터 호환용 폴백(`teacherIdOfName('')`) 때문에 배정 전 예약도 `teacherId='park'`을 갖는다. 화면은 `received`+표시명 없음을 "미배정"으로 처리하지만, 서버에서는 `teacher_id`를 `null`로 둬야 한다.
- 매칭 대기열(후보 교집합)은 v18 엔진(`buildMatchingQueue`)으로 계산된다. **화면**(대기열 목록·예외 보드)은 아직 없다(`SCALING-ARCHITECTURE.md` §17-6). 자동 안내 문구 템플릿은 `buildReminderNotice`(D-1/30분 전)로 완료, 발송기는 서버 단계.
- **파트너 알림함 화면**(선생님 알림은 지금 저장만) · `rescheduled → confirmed` 재확정 UI.
- 서버 연결: Supabase 테이블 생성 SQL은 이 문서의 §1~§11을 그대로 옮기면 된다(별도 `schema.sql`은 서버 단계에서).
- 결제·정산은 실제 PG 연동 전까지 데모 표시를 유지하고, 원장에는 `paid`를 쓰지 않는다.
