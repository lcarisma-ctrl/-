/*
 * 똑똑쌤 v33 — 첫 방문 전 홈 마감 검증 (jsdom)
 * 실행: cd projects/ttokttok-app/tests && node --max-old-space-size=4096 app.v33.test.js
 * ─ app.test.js(전체 회귀)·app.v32.test.js(빈 상태·로딩)와 별도 프로세스로 돌린다.
 *   jsdom은 1.3MB 문서를 통째로 들고 있어 한 프로세스에 다 넣으면 힙 한도를 넘는다.
 */
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');

/* v32와 같은 방식으로 '오늘'을 고정한다(2026-11-26 22:00 KST). */
const FIXED_NOW = new Date('2026-11-26T13:00:00.000Z').getTime();
{
  const RealDate = Date;
  function FixedDate(...args) { return args.length ? new RealDate(...args) : new RealDate(FIXED_NOW); }
  FixedDate.prototype = RealDate.prototype;
  FixedDate.now = () => FIXED_NOW;
  FixedDate.parse = RealDate.parse;
  FixedDate.UTC = RealDate.UTC;
  global.Date = FixedDate;
}

let pass = 0;
const fails = [];
function ok(name, cond, extra) {
  if (cond) { pass++; } else { fails.push(name + (extra ? ' :: ' + extra : '')); }
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function makeDom(seedStorage) {
  const errors = [];
  const vc = new VirtualConsole();
  vc.on('jsdomError', (e) => { if (!/Not implemented/.test(e.message)) errors.push(e.message); });
  vc.on('error', (...a) => errors.push(a.join(' ')));
  const dom = new JSDOM(HTML, {
    runScripts: 'dangerously',
    url: 'https://ttokttok.test/',
    virtualConsole: vc,
    pretendToBeVisual: true,
    beforeParse(window) {
      if (seedStorage) Object.keys(seedStorage).forEach((k) => window.localStorage.setItem(k, seedStorage[k]));
    }
  });
  return { dom, window: dom.window, doc: dom.window.document, errors };
}

const EMPTY_ACCOUNT = JSON.stringify({ passes: [], bookings: [], receipts: [], sessions: [], myReviews: [], profile: { name: '현수' } });

async function run() {
  /* ============================================================
     AF. v33 — 첫 방문 전 홈 분기
     ============================================================ */

  /* ── 1) 모델: 순수 함수 ───────────────────────────────────── */
  const A = makeDom({ 'ttokttok_account_v3': EMPTY_ACCOUNT });
  await sleep(400);
  const d = A.doc, w = A.window;
  const M = w.__ttokttokModel;
  const $ = (s, r) => (r || d).querySelector(s);
  const $$ = (s, r) => Array.from((r || d).querySelectorAll(s));
  const click = (el) => el && el.dispatchEvent(new w.MouseEvent('click', { bubbles: true, cancelable: true }));
  const text = (s) => { const el = $(s); return el ? String(el.textContent || '').replace(/\s+/g, ' ').trim() : ''; };

  ok('AF0 JS 오류 없음(빈 계정 부팅)', A.errors.length === 0 && d.documentElement.getAttribute('data-js-error') === null,
    A.errors.slice(0, 3).join(' | '));
  ok('AF1 v33 메타·홈 분기 모델 노출', d.querySelector('meta[name="app-version"]').content === 'v51' &&
    M.qaVersion === 'v34' && M.guardianHomeVersion === 'v33' &&
    typeof M.buildGuardianHomePlan === 'function' && typeof M.guardianStageCounts === 'function' &&
    M.firstVisitPoints.length === 3, M.guardianHomeVersion);

  const plan = (c) => M.buildGuardianHomePlan(c);

  ok('AF2 예약·회차권·일지가 없으면 첫 방문 전(pre_first)', (function () {
    const p = plan({ todayIso: '2026-11-26' });
    return p.stage === 'pre_first' && p.actualStage === 'pre_first' && p.firstCard === 'firstVisit' && p.summaryHidden === true &&
      p.counts.bookings === 0 && p.counts.passRemaining === 0 && p.counts.journals === 0;
  })(), JSON.stringify(plan({ todayIso: '2026-11-26' }).counts));
  ok('AF3 예약이 있으면 이용 중(active) — 첫 카드는 요약', (function () {
    const p = plan({ todayIso: '2026-11-26', bookings: [{ no: 'A1', status: 'confirmed', dateIso: '2026-11-30' }] });
    return p.stage === 'active' && p.firstCard === 'summary' && p.summaryHidden === false && p.counts.liveBookings === 1;
  })());
  ok('AF4 취소·노쇼만 있으면 아직 첫 방문 전', (function () {
    const p = plan({ todayIso: '2026-11-26', bookings: [{ no: 'C1', status: 'canceled' }, { no: 'C2', status: 'no_show' }] });
    return p.stage === 'pre_first' && p.counts.canceledBookings === 2 && p.counts.liveBookings === 0 &&
      p.counts.completedBookings === 0;
  })());
  ok('AF5 방문 완료가 있으면 이용 중', plan({ todayIso: '2026-11-26', bookings: [{ no: 'D1', status: 'completed' }] }).stage === 'active');
  ok('AF6 회차권 잔여가 남아 있으면 이용 중 / 0회면 첫 방문 전', (function () {
    const a = plan({ todayIso: '2026-11-26', passes: [{ name: '4회 방문권', total: 4, remaining: 0 }] });
    const b = plan({ todayIso: '2026-11-26', passes: [{ name: '4회 방문권', total: 4, remaining: 2 }] });
    return a.stage === 'pre_first' && a.counts.passRemaining === 0 && b.stage === 'active' && b.counts.passRemaining === 2;
  })());
  ok('AF7 예약과 연결된 일지만 이 보호자 일지로 센다', (function () {
    const linked = plan({
      todayIso: '2026-11-26',
      bookings: [{ no: 'TT-1', id: 'res-1', status: 'completed' }],
      journals: [{ id: 'j1', reservationId: 'TT-1', visitDate: '2026-11-20', pain5: 3 }]
    });
    const stray = plan({
      todayIso: '2026-11-26',
      journals: [{ id: 'j2', patient: '김순자 어르신', visitDate: '2026-11-25', pain5: 3 }]
    });
    return linked.counts.journals === 1 && stray.counts.journals === 0 && stray.stage === 'pre_first';
  })(), JSON.stringify(plan({ todayIso: '2026-11-26', journals: [{ id: 'j', patient: '김순자' }] }).counts));
  ok('AF8 보호자 이름으로 연결된 일지는 내 일지(이용 중)', (function () {
    const p = plan({ todayIso: '2026-11-26', memberName: '현수', journals: [{ id: 'j3', patient: '현수 어르신', visitDate: '2026-11-25' }] });
    return p.counts.journals === 1 && p.stage === 'active';
  })());
  ok('AF9 미리보기(first)는 화면만 바꾸고 실제 상태는 남긴다', (function () {
    const p = plan({ todayIso: '2026-11-26', stageOverride: 'first', bookings: [{ no: 'A', status: 'confirmed', dateIso: '2026-12-01' }] });
    return p.stage === 'pre_first' && p.actualStage === 'active' && p.preview === 'first' && p.firstCard === 'firstVisit';
  })());
  ok('AF10 미리보기(active)는 빈 계정에서도 요약을 보여 준다', (function () {
    const p = plan({ todayIso: '2026-11-26', stageOverride: 'active' });
    return p.stage === 'active' && p.actualStage === 'pre_first' && p.preview === 'active' && p.summaryHidden === false;
  })());
  ok('AF11 요약은 v25 계산을 그대로 쓴다(다음 방문·회차권·리포트)', (function () {
    const ctx = { todayIso: '2026-11-26', bookings: [{ no: 'TT-9', status: 'confirmed', dateIso: '2026-11-28', time: '10:00', teacher: '박' }], passes: [], journals: [] };
    const p = plan(ctx);
    const s = M.buildGuardianSummary(ctx);
    return p.summary.nextVisit.bookingNo === 'TT-9' && p.summary.nextVisit.dday === 2 &&
      p.summary.passes.total === 0 && p.summary.report.rounds === 0;
  })());
  ok('AF12 첫 방문 안내 내용(가치 3 · 순서 3 · CTA 2 · 무료 평가)', (function () {
    const fv = plan({ todayIso: '2026-11-26' }).firstVisit;
    return fv.title === '처음이신가요?' && fv.points.length === 3 &&
      /면허/.test(fv.points[0].v) && /60분/.test(fv.points[1].v) && /일지/.test(fv.points[2].v) &&
      fv.steps.length === 3 && /15분 평가/.test(fv.stepLine) && /맞춤 계획/.test(fv.stepLine) && /60분/.test(fv.stepLine) &&
      fv.ctas.length === 2 && fv.ctas[0].attrs === 'data-book="eval"' && fv.ctas[1].attrs === 'data-go="teachers"' &&
      /이동비 없음/.test(fv.note) && !/\d+,\d{3}원/.test(fv.lead + fv.note);
  })(), JSON.stringify(plan({ todayIso: '2026-11-26' }).firstVisit.steps));
  ok('AF13 계산은 저장소·알림·화면을 건드리지 않는다(순수)', (function () {
    const before = JSON.stringify(Object.keys(w.localStorage).sort().map((k) => [k, w.localStorage.getItem(k)]));
    const alerts = w.__ttokttokV32.alerts().slice();
    plan({ todayIso: '2026-11-26', bookings: [{ no: 'X', status: 'confirmed', dateIso: '2026-12-02' }] });
    const after = JSON.stringify(Object.keys(w.localStorage).sort().map((k) => [k, w.localStorage.getItem(k)]));
    return before === after && JSON.stringify(alerts) === JSON.stringify(w.__ttokttokV32.alerts());
  })());
  ok('AF14 같은 입력이면 같은 결과(결정적)', (function () {
    const c = { todayIso: '2026-11-26', bookings: [{ no: 'Q', status: 'assigned', dateIso: '2026-12-03' }], passes: [], journals: [] };
    return JSON.stringify(plan(c)) === JSON.stringify(plan(c));
  })());

  /* ── 2) 화면: 첫 방문 전(빈 계정) ─────────────────────────── */
  const fv = $('#homeFirstVisitCard');
  ok('AF15 첫 방문 전 — 첫 카드는 첫 방문 안내, 빈 요약 카드는 접힘', !!fv && fv.hidden === false &&
    $('#homeSummaryCard').hidden === true &&
    $('#screen-home .home-body').firstElementChild.id === 'homeFirstVisitCard',
    $('#screen-home .home-body').firstElementChild.id);
  ok('AF16 안내 카드 내용(제목·가치 3줄·순서·CTA 2개)', /처음이신가요/.test(text('#homeFirstVisitTitle')) &&
    $$('#homeFirstVisitPoints .sum-row').length === 3 &&
    /15분 평가/.test(text('#homeFirstVisitSteps')) &&
    /무료 평가 신청/.test(text('#homeFirstVisitCard')) && /선생님 둘러보기/.test(text('#homeFirstVisitCard')) &&
    $$('#homeFirstVisitCard .btn').length === 2, text('#homeFirstVisitCard').slice(0, 120));
  ok('AF17 첫 방문 전에는 위 파란 공지(중복 문구)를 접는다', $('#homeNotice').hidden === true);
  ok('AF18 첫 방문 안내에 금액·수수료 없음', !/\d+,\d{3}원/.test(text('#homeFirstVisitCard')) && !/수수료/.test(text('#homeFirstVisitCard')),
    text('#homeFirstVisitCard').slice(0, 100));
  ok('AF19 무료 평가 신청 → 예약 1단계(무료 평가 선택)', (function () {
    click($('#homeFirstVisitCard [data-book="eval"]'));
    return $('#screen-booking').classList.contains('is-active') &&
      w.__ttokttokModel.bookingFormState().passId === 'eval' &&
      $('#wstep-1').classList.contains('is-active');
  })(), w.__ttokttokModel.bookingFormState().passId);
  ok('AF20 선생님 둘러보기 → 선생님 찾기 화면', (function () {
    click($('#homeFirstVisitCard [data-go="teachers"]'));
    return $('#screen-teachers').classList.contains('is-active');
  })());
  ok('AF21 이용안내 · 준비물 보기 → 이용안내 시트', (function () {
    click($('.tabbar[data-mode="customer"] .tabbtn[data-tab="home"]'));
    click($('#homeFirstVisitGuide'));
    return $('#guideSheet').classList.contains('is-open');
  })());
  ok('AF22 빈 상태 감사 위반 0(첫 방문 전 화면)', w.__ttokttokV32.audit(d).length === 0,
    JSON.stringify(w.__ttokttokV32.audit(d).slice(0, 3)));
  ok('AF23 터치 44px·간격 8px 위반 0(첫 방문 안내 카드 포함)', (function () {
    const v = w.__ttokttokTouch ? w.__ttokttokTouch.violations() : [];
    const g = w.__ttokttokTouch ? w.__ttokttokTouch.gapViolations() : [];
    return v.length === 0 && g.length === 0;
  })(), JSON.stringify((w.__ttokttokTouch ? w.__ttokttokTouch.violations() : []).slice(0, 3)));
  ok('AF24 미리보기 상태는 기본값이 아니다(빈 계정 = 실제 첫 방문 전)', w.__ttokttokModel.homeStageState().preview === '' &&
    w.__ttokttokModel.homeStageState().noteVisible === false);
  try { d.documentElement.innerHTML = ''; w.close(); } catch (e) {}

  /* ── 3) 화면: 이용 중(기본 시드) + 미리보기 + 관리자 ───────── */
  const B = makeDom();
  await sleep(400);
  const d2 = B.doc, w2 = B.window;
  const $2 = (s, r) => (r || d2).querySelector(s);
  const $$2 = (s, r) => Array.from((r || d2).querySelectorAll(s));
  const click2 = (el) => el && el.dispatchEvent(new w2.MouseEvent('click', { bubbles: true, cancelable: true }));
  const text2 = (s) => { const el = $2(s); return el ? String(el.textContent || '').replace(/\s+/g, ' ').trim() : ''; };
  const M2 = w2.__ttokttokModel;

  ok('AF25 이용 중 — 요약 카드가 첫 카드, 안내 카드는 접힘', $2('#homeSummaryCard').hidden === false &&
    $2('#homeFirstVisitCard').hidden === true &&
    $2('#screen-home .home-body').firstElementChild.id === 'homeSummaryCard');
  ok('AF26 요약 카드는 v25 그대로(시드 예약·회차권·리포트)', /TT-261021-7302/.test(text2('#homeSummaryNext')) &&
    /잔여 5회/.test(text2('#homeSummaryPass')) && /최근 4주 방문/.test(text2('#homeSummaryReport')));
  ok('AF27 이용 중에는 위 공지가 보인다', $2('#homeNotice').hidden === false && /첫 1:1 방문 평가 무료/.test(text2('#homeNotice')));
  ok('AF28 관리자 「홈 화면 미리보기」 카드가 지금 상태를 보여 준다', !!$2('#adminHomeStageSec') &&
    /이용 중/.test(text2('#adminHomeStageNow')) && /요약/.test(text2('#adminHomeStageFirst')) &&
    /예약 2건/.test(text2('#adminHomeStageCounts')), text2('#adminHomeStageNow') + ' | ' + text2('#adminHomeStageCounts'));
  ok('AF29 미리보기(first) — 첫 방문 안내가 앞으로, 데이터는 그대로', (function () {
    const before = JSON.stringify(M2.guardianHome().counts);
    const p = M2.setStagePreview('first');
    const st = M2.homeStageState();
    return p.stage === 'pre_first' && p.preview === 'first' && st.firstCardVisible && !st.summaryVisible &&
      st.firstElement === 'homeFirstVisitCard' && st.noteVisible &&
      JSON.stringify(M2.guardianHome().counts) === before && M2.guardianHome().counts.bookings === 2;
  })(), JSON.stringify(M2.homeStageState()));
  ok('AF30 미리보기 끄기 버튼 → 실제 상태로 복귀', (function () {
    click2($2('#homeStagePreviewNote'));
    const st = M2.homeStageState();
    return M2.guardianHome().stage === 'active' && M2.homeStageState().preview === '' &&
      st.summaryVisible && !st.firstCardVisible && st.firstElement === 'homeSummaryCard' && !st.noteVisible;
  })());
  ok('AF31 관리자 「첫 방문 전 화면 보기」 → 홈으로 이동하며 첫 방문 안내 표시', (function () {
    click2($2('#adminStageFirst'));
    return $2('#screen-home').classList.contains('is-active') && M2.homeStageState().firstCardVisible &&
      M2.homeStageState().preview === 'first';
  })(), M2.homeStageState().preview);
  ok('AF32 관리자 「실제 상태로 보기」 → 원래 홈', (function () {
    w2.__ttokttokModel && click2($2('#adminStageReset'));
    return M2.guardianHome().stage === 'active' && $2('#homeSummaryCard').hidden === false &&
      $2('#homeFirstVisitCard').hidden === true;
  })());
  ok('AF33 미리보기를 끈 뒤에도 예약·회차권 데이터는 그대로(파괴 없음)', (function () {
    const c = M2.guardianHome().counts;
    const bookings = (M2.guardianSummary().nextVisit || {}).bookingNo;
    return c.bookings === 2 && c.passRemaining === 5 && bookings === 'TT-261021-7302';
  })());
  ok('AF34 대화상자 이름 22/22 유지(새 카드가 접근성을 깨지 않음)', (function () {
    const a = M2.a11y;
    const n = a.dialogCount();
    return n >= 22 && a.labelledDialogs() === n;
  })(), M2.a11y.dialogCount() + '/' + M2.a11y.labelledDialogs());
  ok('AF35 빈 상태 감사 위반 0(이용 중 화면)', w2.__ttokttokV32.audit(d2).length === 0,
    JSON.stringify(w2.__ttokttokV32.audit(d2).slice(0, 3)));

  /* ── 4) 지켜야 할 것 ─────────────────────────────────────── */
  const styleM = HTML.match(/<style>([\s\S]*?)<\/style>/);
  ok('AF36 <style> 블록 토큰 정합성(v35부터 CSS 수정 허용)', (function () {
    if (!styleM) return false;
    const css = styleM[1];
    const defs = new Set((css.match(/--[a-zA-Z0-9-]+\s*:/g) || []).map((x) => x.replace(/\s*:$/, '')));
    const uses = (css.match(/var\((--[a-zA-Z0-9-]+)\)/g) || []).map((x) => x.slice(4, -1));
    return (css.match(/:root\{/g) || []).length === 1 && uses.every((u) => defs.has(u)) &&
      /--text-caption\s*:/.test(css);
  })(), String(styleM && styleM[1].length));
  ok('AF37 단가·수수료·정산 규칙·시드 예약 불변', (function () {
    const P = M2.pricing, S = M2.settlementRule;
    return P.consumerPrice === 90000 && P.teacherPayout === 70000 && P.platformFeeRate === 0.2222 &&
      S.confirmDays === 3 && JSON.stringify(S.payDays) === '[15,"end"]' &&
      M2.reservations().some((r) => r.no === 'TT-261021-7302');
  })());
  ok('AF38 앱 버전 훅·QA 훅이 v33으로 맞물린다', M2.qaVersion === 'v34' && M2.a11y.version === 'v34' &&
    M2.guardianHomeVersion === 'v33' && w2.__ttokttokV32.version === 'v32');
  ok('AF39 조작 뒤에도 JS 오류 0', B.errors.length === 0 && d2.documentElement.getAttribute('data-js-error') === null,
    B.errors.slice(0, 3).join(' | '));
  try { d2.documentElement.innerHTML = ''; w2.close(); } catch (e) {}

  console.log('\nV33 RESULT: ' + pass + ' passed, ' + fails.length + ' failed');
  if (fails.length) {
    console.log('FAILURES:');
    fails.forEach((f) => console.log(' - ' + f));
  }
  /* 통과해도 이 프로세스에는 jsdom 타이머가 남는다 — 다른 검증 파일처럼 명시적으로 끝낸다. */
  process.exit(fails.length ? 1 : 0);
}

run().catch((e) => { console.log('FATAL', (e && e.stack) || e); process.exit(1); });
