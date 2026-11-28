/*
 * 똑똑쌤 v32 — 빈 상태 · 로딩 · 오류 · 입력값 보존 검증 (jsdom)
 * 실행: cd projects/ttokttok-app/tests && node app.v32.test.js
 * ─ app.test.js(전체 회귀)와 별도 프로세스로 돌린다.
 *   jsdom은 1.3MB 문서를 통째로 들고 있어 한 프로세스에 다 넣으면 힙 한도(약 1.9GB)를 넘는다.
 *   그래서 v32 검증만 이 파일로 분리했고, 두 파일을 이어서 실행하면 전체가 검증된다.
 */
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');

/* v32 · 실행 시각과 무관하게 같은 결과가 나오도록 '오늘'을 고정한다(2026-11-26 22:00 KST). */
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

function closeDom(x) {
  try { x.doc.documentElement.innerHTML = ''; } catch (e) {}
  try { x.window.close(); } catch (e) {}
}

async function run() {
  /* ============================================================
     AD. v32 — 빈 상태·로딩·오류·입력값 보존 마감
     (jsdom은 1.3MB 문서를 통째로 들고 있어, 앞 섹션 창을 닫고
      새 창은 하나씩만 살려 두어 메모리 한도를 넘지 않게 한다.)
     ============================================================ */
  const ADE = makeDom({ 'ttokttok_account_v3': JSON.stringify({ passes: [], bookings: [], receipts: [], sessions: [], myReviews: [], profile: { name: '현수' } }) });
  await sleep(360);
  const de = ADE.doc, we = ADE.window;
  const e$ = (s, r) => (r || de).querySelector(s);
  const eClick = (el) => el.dispatchEvent(new we.MouseEvent('click', { bubbles: true, cancelable: true }));
  ok('AD0 v32 JS 오류 없음(빈 계정 부팅)', ADE.errors.length === 0 && de.documentElement.getAttribute('data-js-error') === null,
    ADE.errors.slice(0, 3).join(' | '));
  ok('AD1 v32 메타·공통 UI 훅 노출', de.querySelector('meta[name="app-version"]').getAttribute('content') === 'v49' &&
    !!we.__ttokttokV32 && we.__ttokttokV32.version === 'v32' && we.__ttokttokModel.qaVersion === 'v34',
    we.__ttokttokV32 && we.__ttokttokV32.version);
  ok('AD2 빈 계정 — 이용권·예약·결제 내역·타임라인 4곳 모두 통일 빈 상태', (function () {
    const keys = ['wallet-passes', 'booking-list', 'receipts', 'journal-timeline'];
    return keys.every((k) => {
      const el = e$('[data-empty="' + k + '"]');
      return !!el && !!el.querySelector('p') && !!el.querySelector('.btn');
    });
  })(), ['wallet-passes', 'booking-list', 'receipts', 'journal-timeline'].filter((k) => !e$('[data-empty="' + k + '"]')).join(','));
  ok('AD3 빈 계정 감사 위반 0(숨김 제외 전수)', we.__ttokttokV32.audit(de).length === 0,
    JSON.stringify(we.__ttokttokV32.audit(de).slice(0, 3)));
  ok('AD4 빈 상태 CTA로 다음 행동이 이어진다(예약하기 → 예약 화면)', (function () {
    eClick(e$('[data-empty="booking-list"] [data-go="booking"]'));
    return e$('#screen-booking').classList.contains('is-active');
  })());
  ok('AD5 빈 상태 설명은 한 줄(줄바꿈 태그 없음)', (function () {
    return Array.from(de.querySelectorAll('.empty[data-empty]')).every((el) => !/<br\s*\/?>/i.test(el.innerHTML));
  })());
  try { de.documentElement.innerHTML = ''; we.close(); } catch (e) {}

  const ADC = makeDom({ 'ttokttok_account_v3': '{broken json' });
  await sleep(360);
  ok('AD6 손상된 저장 데이터 — 예시 데이터로 열고 원인 + 「다시 읽기」 표시', (function () {
    const host = ADC.doc.querySelector('#ttAlertHost');
    return ADC.errors.length === 0 && ADC.doc.documentElement.getAttribute('data-js-error') === null &&
      !!host && /읽지 못했어요/.test(host.textContent) && !!host.querySelector('[data-retry="account-read"]');
  })(), ADC.doc.querySelector('#ttAlertHost').textContent.replace(/\s+/g, ' ').trim().slice(0, 80));
  ok('AD7 읽을 수 있는 값으로 돌아오면 「다시 읽기」로 복구된다', (function () {
    const seed = { passes: [{ id: 'p1', passId: 'p1', name: '1회 방문권', total: 1, remaining: 1, purchased: '2026.11.20', expire: '2027.02.18', status: 'active' }], bookings: [], receipts: [], sessions: [], myReviews: [], profile: { name: '현수' } };
    ADC.window.localStorage.setItem('ttokttok_account_v3', JSON.stringify(seed));
    const btn = ADC.doc.querySelector('#ttAlertHost [data-retry="account-read"]');
    if (btn) btn.dispatchEvent(new ADC.window.MouseEvent('click', { bubbles: true, cancelable: true }));
    const host = ADC.doc.querySelector('#ttAlertHost');
    return host.innerHTML.trim() === '' && ADC.window.__ttokttokV32.alerts().length === 0 &&
      /1회 방문권/.test(ADC.doc.querySelector('#walletList').textContent);
  })(), ADC.doc.querySelector('#ttAlertHost').textContent.slice(0, 60));
  try { ADC.doc.documentElement.innerHTML = ''; ADC.window.close(); } catch (e) {}

  const AD = makeDom();
  await sleep(360);
  const d32 = AD.doc, w32 = AD.window;
  const a$ = (s, r) => (r || d32).querySelector(s);
  const a$$ = (s, r) => Array.from((r || d32).querySelectorAll(s));
  const aClick = (el) => el.dispatchEvent(new w32.MouseEvent('click', { bubbles: true, cancelable: true }));
  const aVal = (el, v) => { el.value = v; el.dispatchEvent(new w32.Event('input', { bubbles: true })); };
  const aSel = (el, v) => { el.value = v; el.dispatchEvent(new w32.Event('change', { bubbles: true })); };
  const V32 = w32.__ttokttokV32;
  const M32 = w32.__ttokttokModel;
  const aText = (s) => (a$(s) ? a$(s).textContent.replace(/\s+/g, ' ').trim() : '');

  /* ── 빈 상태 프리셋(전 화면 공통 문구) ───────────────────────── */
  ok('AD8 빈 상태 프리셋 24종 이상, 모두 제목·한 줄 설명·CTA 보유', (function () {
    const ks = V32.emptyKeys();
    return ks.length >= 24 && ks.every((k) => {
      const p = V32.emptyHtml(k);
      return /data-empty="/.test(p) && /<b>/.test(p) && /<p>/.test(p) && /class="btn /.test(p) && !/<br/.test(p);
    });
  })(), String(V32.emptyKeys().length));
  ok('AD9 빈 상태 구조 통일(empty empty-v7 + data-empty + role/aria-label)', (function () {
    const html = V32.emptyHtml('booking-list');
    return /class="empty empty-v7"/.test(html) && /data-empty="booking-list"/.test(html) &&
      /role="group"/.test(html) && /aria-label="/.test(html) && /<b>다가오는 방문이 없어요<\/b>/.test(html);
  })(), V32.emptyHtml('booking-list').slice(0, 100));
  ok('AD10 CTA는 기존 위임 동작 그대로(data-go·data-book)', (function () {
    return /data-go="booking"/.test(V32.emptyHtml('booking-list')) && /data-book="eval"/.test(V32.emptyHtml('wallet-passes'));
  })());
  ok('AD11 외부 상담 CTA는 새 창·noopener로만 연다', (function () {
    const h = V32.emptyHtml('faq-empty');
    return /href="https:\/\/naver\.me\/G3vCkS0S"/.test(h) && /target="_blank"/.test(h) && /rel="noopener noreferrer"/.test(h) &&
      (h.match(/class="btn /g) || []).length === 2;
  })());
  ok('AD12 기본 화면의 빈 상태 감사 위반 0', V32.audit(d32).length === 0, JSON.stringify(V32.audit(d32).slice(0, 3)));

  /* ── 입력값 보존 ① 이어서 작성(새로 열기) ────────────────────── */
  V32.saveDraftObject('booking', {
    step: 3, province: '서울', district: '강남구', address: '대치동 123-4, 101동 1203호', syms: ['뇌졸중·편마비'], teacherId: '',
    dateIso: '', dateLabel: '', dateDay: '', time: '', passId: 'p1', name: '김순자', phone: '010-1234-5678', pay: '신용/체크카드', couponId: '', agree: true
  });
  ok('AD13 저장된 초안이 있으면 「이어서 작성」 카드를 띄운다', (function () {
    V32.paintBookingDraft();
    const box = a$('#bookResume');
    return !!box && box.hidden === false && /작성 중이던 예약/.test(box.textContent) && V32.resumeVisible() === true;
  })(), aText('#bookResumeText'));
  ok('AD14 「이어서 작성」 → 입력값·단계가 그대로 복원된다', (function () {
    aClick(a$('[data-book-resume]'));
    const s = V32.bookingInputs();
    const pass = a$('#passList [data-pass="p1"]');
    return s.name === '김순자' && s.agree === true && s.step === 3 && /대치동 123-4/.test(s.address) &&
      a$('#wstep-3').classList.contains('is-active') && !!pass && pass.classList.contains('is-on') &&
      a$('#bookResume').hidden === true;
  })(), JSON.stringify(V32.bookingInputs()));

  /* 새 예약(증상 CTA)은 초안을 지우고 빈 화면에서 시작한다 */
  aClick(a$('#homeBookBtn'));
  ok('AD15 새 예약을 시작하면 초안이 비워진다(이전 입력이 새 예약에 새지 않음)', (function () {
    return V32.bookingDraft() === null && V32.bookingInputs().step === 1 && a$('#bookResume').hidden === true;
  })(), JSON.stringify(V32.bookingInputs()));

  /* ── 검색·필터 0건 · 찜 없음 · FAQ 0건 ────────────────────────── */
  ok('AD16 선생님 검색 0건 → 통일 빈 상태 + 검색어 지우기 CTA', (function () {
    aVal(a$('#homeSearch'), '없는이름zzz');
    const empty = a$('#searchResults [data-empty="search-teacher"]');
    return !!empty && /선생님이 없어요/.test(empty.textContent) && !!empty.querySelector('[data-teacher-reset]');
  })(), aText('#searchResults').slice(0, 80));
  ok('AD17 검색어 지우기 CTA → 필터 초기화·목록 8명 복귀', (function () {
    aClick(a$('#searchResults [data-teacher-reset]'));
    return a$$('#teacherList .teacher').length === 8 && !a$('#searchResults').classList.contains('is-open');
  })(), String(a$$('#teacherList .teacher').length));
  ok('AD18 찜 필터 0명 → 그림 유지 + 통일 구조(teachers-fav)', (function () {
    aClick(a$('#favFilter'));
    const el = a$('#teacherList [data-empty="teachers-fav"]');
    const okAll = !!el && !!el.querySelector('.empty-art') && !!el.querySelector('[data-fav-clear]') && !!el.querySelector('p');
    aClick(a$('#teacherList [data-fav-clear]'));
    return okAll && a$$('#teacherList .teacher').length === 8;
  })());
  ok('AD19 FAQ 0건 → 통일 빈 상태 + 검색 초기화 CTA', (function () {
    aVal(a$('#faqSearch'), '없는질문zzz');
    const empty = a$('#faqEmpty');
    const vis = !!empty && !empty.hidden && !!empty.querySelector('[data-faq-reset]');
    aClick(a$('#faqEmpty [data-faq-reset]'));
    return vis && a$('#faqEmpty').hidden === true && a$$('#faqList .faq-item').length === 10;
  })(), String(a$$('#faqList .faq-item').length));

  /* ── 로딩 표시·버튼 잠금 ─────────────────────────────────────── */
  ok('AD20 로딩 블록 구조(role=status·aria-busy·data-loading·문구)', (function () {
    const h = V32.loadingHtml('불러오는 중');
    return /data-loading="1"/.test(h) && /role="status"/.test(h) && /aria-busy="true"/.test(h) && /불러오는 중/.test(h);
  })());
  ok('AD21 로딩 블록을 목록 자리에 넣을 수 있다', (function () {
    V32.showLoading('#journalTimeline', '방문 기록 불러오는 중');
    const el = a$('#journalTimeline [data-loading="1"]');
    return !!el && /방문 기록 불러오는 중/.test(el.textContent);
  })(), aText('#journalTimeline').slice(0, 40));
  const dotsBefore = aText('#journalTimeline [data-loading-dots]');
  await sleep(520);
  ok('AD22 로딩 점 표시가 시간에 따라 바뀐다(정지 화면 아님)', aText('#journalTimeline [data-loading-dots]') !== dotsBefore,
    dotsBefore + ' → ' + aText('#journalTimeline [data-loading-dots]'));
  ok('AD23 버튼 잠금(busy) — 비활성·aria-busy·문구 교체·중복 잠금 차단', (function () {
    const b = a$('#payBtn');
    const original = b.textContent;
    const first = V32.busy('#payBtn', '결제 중…');
    const second = V32.busy('#payBtn', '또 결제 중…');
    const okNow = b.disabled === true && b.getAttribute('aria-busy') === 'true' &&
      b.getAttribute('data-busy') === '1' && b.textContent === '결제 중…' && first === true && second === false;
    const back = V32.idle('#payBtn');
    return okNow && back === true && b.disabled === false && b.getAttribute('data-busy') === null &&
      b.textContent === original;
  })(), aText('#payBtn'));

  /* ── 오류 + 재시도 ───────────────────────────────────────────── */
  ok('AD24 오류 블록 — 원인 문구 + 「다시 시도」가 실제로 다시 부른다', (function () {
    let called = 0;
    V32.onRetry('ad-retry', function () { called++; return true; });
    V32.showErrorTo('#bookError', 'ad-retry', '일시적인 오류', '연결이 끊겼어요');
    const box = a$('#bookError [data-error="ad-retry"]');
    const btn = a$('#bookError [data-retry="ad-retry"]');
    if (btn) aClick(btn);
    return !!box && !!btn && /연결이 끊겼어요/.test(box.textContent) && called === 1;
  })(), aText('#bookError').slice(0, 60));
  ok('AD25 오류 문구에 원인(메시지)이 빠지지 않고 지우기도 된다', (function () {
    V32.showErrorTo('#bookError', 'ad-retry2', '저장 실패', '용량이 가득 찼어요');
    const t = aText('#bookError');
    V32.clear('#bookError');
    return /저장 실패/.test(t) && /용량이 가득 찼어요/.test(t) && aText('#bookError') === '';
  })());

  /* ── 저장 실패 알림 띠 → 다시 저장 ───────────────────────────── */
  ok('AD26 저장 실패를 화면 위 띠로 알리고 「다시 저장」을 준다', (function () {
    V32.simulateStorageFailure(true);
    M32.transition('TT-261021-7302', 'completed', { actor: 'operator' });
    const host = a$('#ttAlertHost');
    return !!host && host.style.display !== 'none' && /기기에 저장하지 못했어요/.test(host.textContent) &&
      !!host.querySelector('[data-retry="account-save"]') && V32.alerts().indexOf('account-save') !== -1;
  })(), aText('#ttAlertHost').slice(0, 80));
  ok('AD27 저장이 다시 되면 알림 띠가 스스로 사라진다', (function () {
    V32.simulateStorageFailure(false);
    const had = V32.alerts().slice();
    /* 띠를 하나 지우면 나머지 버튼이 다시 그려지므로, 남은 버튼을 매번 다시 찾아 누른다. */
    for (let i = 0; i < 6; i++) {
      const btn = a$('#ttAlertHost [data-retry]');
      if (!btn) break;
      aClick(btn);
    }
    return had.length >= 1 && !!w32.localStorage.getItem('ttokttok_account_v3') &&
      a$('#ttAlertHost').innerHTML.trim() === '' && V32.alerts().length === 0;
  })(), V32.alerts().join(',') + ' | ' + aText('#ttAlertHost').slice(0, 60));

  /* ── 입력값 보존 ② 탭 이동·실패 후 재시도 ────────────────────── */
  aClick(a$('[data-login="customer"]'));
  aClick(a$('.tabbar .tabbtn[data-tab="booking"]'));
  aSel(a$('#bookProvince'), '서울');
  aSel(a$('#bookDistrict'), '강남구');
  aVal(a$('#bookAddress'), '대치동 123-4, 101동 1203호');
  aClick(a$('#bookSyms [data-val="뇌졸중·편마비"]'));
  aClick(a$('[data-next="1"]'));
  ok('AD28 2단계에서 입력값이 유지된다(주소·증상)', (function () {
    const s = V32.bookingInputs();
    return /대치동 123-4/.test(s.address) && s.step === 2 &&
      M32.bookingFormState().syms.indexOf('뇌졸중·편마비') !== -1;
  })(), JSON.stringify(V32.bookingInputs()));
  ok('AD29 다른 탭에 다녀와도 작성 중인 예약이 초기화되지 않는다', (function () {
    aClick(a$('.tabbar .tabbtn[data-tab="home"]'));
    aClick(a$('.tabbar .tabbtn[data-tab="booking"]'));
    const s = V32.bookingInputs();
    return s.step === 2 && /대치동 123-4/.test(s.address) && a$('#wstep-2').classList.contains('is-active');
  })(), JSON.stringify(V32.bookingInputs()));
  ok('AD30 입력값은 초안으로도 남는다(주소·단계)', (function () {
    const d = V32.bookingDraft();
    return !!d && /대치동 123-4/.test(d.address) && d.province === '서울' && d.step === 2;
  })(), JSON.stringify(V32.bookingDraft() && { p: V32.bookingDraft().province, s: V32.bookingDraft().step }));

  aClick(a$('#bookDates .date-chip'));
  aClick(a$$('#bookSlots .slot').filter((b) => !b.disabled)[0]);
  aClick(a$('[data-next="2"]'));
  ok('AD31 3단계 이동(입력값 그대로)', a$('#wstep-3').classList.contains('is-active'));
  aClick(a$('#passList [data-pass="p1"]'));
  aClick(a$('[data-next="3"]'));
  aVal(a$('#bookName'), '김순자');
  aVal(a$('#bookPhone'), '01012345678');
  aClick(a$('#payMethods [data-pay="신용/체크카드"]'));
  const ag = a$('#bookAgree');
  ag.checked = true;
  ag.dispatchEvent(new w32.Event('change', { bubbles: true }));
  V32.failNextBooking(true);
  aClick(a$('#payBtn'));
  await sleep(1250);
  ok('AD32 결제 실패 시 오류 블록 + 버튼 원복 + 폼 값 유지', (function () {
    const err = a$('#bookError [data-error="booking-submit"]');
    const btn = a$('#payBtn');
    const inputs = V32.bookingInputs();
    return !!err && /예약을 마무리하지 못했어요/.test(err.textContent) && !!err.querySelector('[data-retry="booking-submit"]') &&
      btn.disabled === false && btn.textContent === '결제하고 예약 완료' &&
      inputs.name === '김순자' && /대치동 123-4/.test(inputs.address) && inputs.agree === true;
  })(), aText('#bookError').slice(0, 80));
  const adRetryBtn = a$('#bookError [data-retry="booking-submit"]');
  if (adRetryBtn) aClick(adRetryBtn);
  await sleep(500);
  ok('AD33 「다시 시도」 → 같은 입력으로 접수가 끝난다', (function () {
    const done = a$('#bookingDone');
    return done.hidden === false && /예약 완료/.test(aText('#bookingDone')) && !!a$('#doneSummary');
  })(), aText('#doneSummary').slice(0, 60));
  ok('AD34 접수가 끝나면 초안이 비워진다(다음 예약은 빈 화면)', V32.bookingDraft() === null);

  /* ── 일지 저장 실패 → 오류 + 입력 유지 ───────────────────────── */
  ok('AD35 일지 저장 실패 — 원인 + 「다시 저장」 + 입력값 유지', (function () {
    const noteEl = a$('#qlNote');
    if (noteEl) aVal(noteEl, '오늘은 계단 연습 위주로 했어요');
    const btn = a$('#qlSave');
    if (btn) aClick(btn);
    const err = a$('#qlError [data-error="quicklog-save"]');
    const kept = a$('#qlNote') ? a$('#qlNote').value : '';
    return !!err && !!err.querySelector('[data-retry="quicklog-save"]') && kept === '오늘은 계단 연습 위주로 했어요' &&
      btn.getAttribute('data-busy') === null && btn.disabled === false;
  })(), aText('#qlError').slice(0, 80));

  /* ── 백업 복원 거부 → 오류 + 다른 파일 선택 ─────────────────── */
  ok('AD36 백업 파일이 잘못되면 원인 + 「다른 파일 선택」 재시도', (function () {
    const res = M32.restoreFromText('{"schemaVersion":"x"}', 'bad.json');
    const err = a$('#adminBackupError [data-error="backup-read"]');
    return res && res.ok === false && !!err && !!err.querySelector('[data-retry="backup-read"]') &&
      /복원할 수 없어요/.test(err.textContent);
  })(), aText('#adminBackupError').slice(0, 80));

  /* ── 지켜야 할 것: <style>·단가·수수료·정산·시드 예약 ─────────── */
  ok('AD37 <style> 블록 토큰 정합성(v35부터 CSS 수정 허용 — :root 하나·var 정의·중괄호)', (function () {
    const m = HTML.match(/<style>([\s\S]*?)<\/style>/);
    if (!m) return false;
    const css = m[1];
    const defs = new Set((css.match(/--[a-zA-Z0-9-]+\s*:/g) || []).map((x) => x.replace(/\s*:$/, '')));
    const uses = (css.match(/var\((--[a-zA-Z0-9-]+)\)/g) || []).map((x) => x.slice(4, -1));
    return (css.match(/:root\{/g) || []).length === 1 && uses.every((u) => defs.has(u)) &&
      (css.match(/\{/g) || []).length === (css.match(/\}/g) || []).length;
  })(), String((HTML.match(/<style>([\s\S]*?)<\/style>/) || ['', ''])[1].length));
  ok('AD38 단가·수수료·정산 규칙·시드 예약 불변', M32.pricing.consumerPrice === 90000 && M32.pricing.teacherPayout === 70000 &&
    M32.pricing.platformFeeRate === 0.2222 && M32.settlementRule.confirmDays === 3 &&
    JSON.stringify(M32.settlementRule.payDays) === '[15,"end"]' &&
    M32.reservations().some((r) => r.no === 'TT-261021-7302'));
  ok('AD39 v32 작업 뒤 전체 화면에서 감사 위반 0(최종 확인)', V32.audit(d32).length === 0,
    JSON.stringify(V32.audit(d32).slice(0, 3)));


  console.log('\nV32 RESULT: ' + pass + ' passed, ' + fails.length + ' failed');
  if (fails.length) {
    console.log('FAILURES:');
    fails.forEach((f) => console.log(' - ' + f));
  }
  /* 통과해도 이 프로세스에는 jsdom 타이머가 남는다 — 다른 검증 파일처럼 명시적으로 끝낸다. */
  process.exit(fails.length ? 1 : 0);
}

run().catch((e) => { console.log('FATAL', (e && e.stack) || e); process.exit(1); });
