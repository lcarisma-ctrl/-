/*
 * 똑똑쌤 v39 — 성능·첫 화면 마감 검증 (jsdom)
 * 실행: cd projects/ttokttok-app/tests && node --max-old-space-size=2600 app.v39.test.js
 */
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const STYLE = (HTML.match(/<style>([\s\S]*?)<\/style>/) || ['', ''])[1];
const FIXED_NOW = new Date('2026-11-26T13:00:00.000Z').getTime();

let pass = 0;
const fails = [];
function ok(name, cond, extra) {
  if (cond) { pass++; } else { fails.push(name + (extra ? ' :: ' + extra : '')); }
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function makeDom(opts) {
  const o = opts || {};
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
      const RealDate = window.Date;
      function FixedDate(...args) { return args.length ? new RealDate(...args) : new RealDate(FIXED_NOW); }
      FixedDate.prototype = RealDate.prototype;
      FixedDate.now = () => FIXED_NOW;
      FixedDate.parse = RealDate.parse;
      FixedDate.UTC = RealDate.UTC;
      window.Date = FixedDate;
      if (o.blockStorage) {
        Object.defineProperty(window, 'localStorage', {
          configurable: true,
          get() { throw new window.DOMException('SecurityError', 'SecurityError'); }
        });
      }
    }
  });
  return { dom, window: dom.window, doc: dom.window.document, errors };
}
const cleanText = (doc) => {
  const clone = doc.body.cloneNode(true);
  [].forEach.call(clone.querySelectorAll('script,style,noscript,svg'), (el) => el.remove());
  return String(clone.textContent || '').replace(/\s+/g, ' ');
};
const textOf = (doc, sel) => {
  const el = doc.querySelector(sel);
  return el ? String(el.textContent || '').replace(/\s+/g, ' ') : '';
};

async function waitBooted(w, ms) {
  const until = Date.now() + (ms || 40000);
  while (!w.__ttokttokBooted && Date.now() < until) await sleep(20);
  return !!w.__ttokttokBooted;
}

async function run() {
  /* 1) 부팅 두 단계 — DCL 시점(첫 화면) vs 유휴 렌더 완료 */
  const A = makeDom();
  let atDcl = null;
  let scrollCalls = 0;
  A.window.scrollTo = function () { scrollCalls++; };
  A.doc.addEventListener('DOMContentLoaded', function () {
    atDcl = {
      booted: A.window.__ttokttokBooted,
      perf: (A.window.__ttokttokPerf || {}).stats ? A.window.__ttokttokPerf.stats() : null,
      teachers: A.doc.querySelectorAll('#teacherList [data-teacher]').length,
      /* v42: 홈 요약이 히어로(다음 방문) + 회차권 카드로 나뉘었다 — 첫 화면 두 장을 함께 본다. */
      homeSummary: textOf(A.doc, '#homeSummaryCard') + ' ' + textOf(A.doc, '#homePassCard'),
      homeTeachers: A.doc.querySelectorAll('#homeTeacherList [data-teacher]').length,
      nodes: A.doc.getElementsByTagName('*').length
    };
  });
  ok('A0 v39 부트 JS 오류 0', A.errors.length === 0, A.errors.slice(0, 3).join(' | '));
  ok('A1 v39 부트 완료(유휴 렌더까지)', await waitBooted(A.window), String(A.window.__ttokttokBooted));
  const P = A.window.__ttokttokPerf;
  const M = A.window.__ttokttokModel;
  const doc = A.doc;

  ok('A2 meta v40 · perf 훅 v39(기능 세대 표기 유지)', doc.querySelector('meta[name="app-version"]').getAttribute('content') === 'v50' &&
    P && P.version === 'v39');
  ok('A3 stats 필드(dcl·fcp·marks·deferred)', (function () {
    const s = P.stats();
    return (s.dcl === null || typeof s.dcl === 'number') && typeof s.deferredTotal === 'number' &&
      typeof s.deferredRendered === 'number' && s.marks && typeof s.marks.boot === 'number' &&
      typeof s.marks.criticalDone === 'number' && typeof s.marks.booted === 'number';
  })(), JSON.stringify(P.stats().marks));
  ok('A4 유휴 렌더 개수·키 고정(22)', P.stats().deferredTotal === 22 && P.stats().deferredRendered === 22 &&
    P.stats().pending === 0, JSON.stringify(P.stats()));
  ok('A5 rIC 없는 환경(jsdom)은 단일 타이머 모드', P.stats().mode === 'timer-single', P.stats().mode);

  ok('B1 DCL 시점에 아직 booted 아님(유휴 렌더 전)', atDcl && atDcl.booted !== true, JSON.stringify(atDcl && atDcl.booted));
  ok('B2 DCL 시점에 첫 화면(홈 요약)은 이미 그려짐', atDcl && /다음 방문/.test(atDcl.homeSummary) &&
    /회차권/.test(atDcl.homeSummary), atDcl && atDcl.homeSummary.slice(0, 60));
  ok('B3 DCL 시점에 탭 뒤 화면(선생님 목록)은 아직 비어 있음', atDcl && atDcl.teachers === 0, atDcl && String(atDcl.teachers));
  ok('B4 DCL 시점에 유휴 렌더가 예약됨', atDcl && atDcl.perf && atDcl.perf.scheduled === true && atDcl.perf.finished === false,
    JSON.stringify(atDcl && atDcl.perf && { s: atDcl.perf.scheduled, f: atDcl.perf.finished }));
  ok('B5 DCL 시점 노드는 최종보다 적다(뒤 화면 미생성)', atDcl && atDcl.nodes < doc.getElementsByTagName('*').length,
    atDcl && atDcl.nodes + '/' + doc.getElementsByTagName('*').length);
  ok('B6 유휴 렌더 종료 시각이 첫 화면 렌더 이후', P.stats().marks.booted >= P.stats().marks.criticalDone,
    JSON.stringify(P.stats().marks));
  ok('B7 부팅 중 화면 스크롤 없음(v39 booting 플래그)', scrollCalls === 0, String(scrollCalls));

  /* 2) 유휴 렌더 결과 — 예전(동기 부팅)과 같은 화면이 나오는지 */
  ok('C0 선생님 목록 8명', doc.querySelectorAll('#teacherList [data-teacher]').length === 8,
    String(doc.querySelectorAll('#teacherList [data-teacher]').length));
  ok('C1 선생님 목록 첫 카드 이름(박서준)', /박서준/.test(textOf(doc, '#teacherList')), textOf(doc, '#teacherList').slice(0, 40));
  ok('C2 내 주변 탭 패널 렌더(동네 카드)', (function () {
    const near = doc.querySelector('#teacherViewTabs [data-view="near"]');
    if (near) near.click();
    const n = doc.querySelectorAll('#nearPanel [data-dong-cluster]').length;
    const list = doc.querySelector('#teacherViewTabs [data-view="list"]');
    if (list) list.click();
    return n > 0;
  })(), String(doc.querySelectorAll('#nearPanel [data-dong-cluster]').length));
  ok('C3 예약 1단계 날짜 7일·시간 안내 렌더', doc.querySelectorAll('#bookDates [data-date]').length === 7 &&
    textOf(doc, '#bookSlots').length > 0,
    doc.querySelectorAll('#bookDates [data-date]').length + '/' + textOf(doc, '#bookSlots').slice(0, 20));
  ok('C4 회차권 카드 렌더', doc.querySelectorAll('#passList [data-pass]').length >= 3,
    String(doc.querySelectorAll('#passList [data-pass]').length));
  ok('C5 내 정보(보호자) 렌더', textOf(doc, '#screen-mypage').length > 200, String(textOf(doc, '#screen-mypage').length));
  ok('C6 알림함 4건·배지 4', doc.querySelectorAll('#notifList .notif').length === 4 &&
    String((doc.querySelector('#notifDot') || {}).textContent) === '4',
    doc.querySelectorAll('#notifList .notif').length + '/' + String((doc.querySelector('#notifDot') || {}).textContent));
  ok('C7 FAQ 10문항', doc.querySelectorAll('#faqList .faq-item').length === 10,
    String(doc.querySelectorAll('#faqList .faq-item').length));
  ok('C8 약관 렌더', textOf(doc, '#termsBody').length > 200, String(textOf(doc, '#termsBody').length));
  ok('C9 운영자 큐(시드 예약) 렌더', /TT-261021-7302/.test(textOf(doc, '#screen-admin')),
    textOf(doc, '#screen-admin').slice(0, 60));
  ok('C10 선생님 모드 화면 렌더', /정산|일정|방문 일지/.test(textOf(doc, '#screen-tp-home')),
    textOf(doc, '#screen-tp-home').slice(0, 40));
  ok('C11 방문 일지 타임라인 렌더', /방문 일지|일지/.test(textOf(doc, '#screen-journal')),
    textOf(doc, '#screen-journal').slice(0, 40));
  ok('C12 쿠폰 목록 렌더', doc.querySelectorAll('#couponList > *').length >= 1,
    String(doc.querySelectorAll('#couponList > *').length));
  ok('C13 오류 없이 유휴 렌더 완료', A.errors.length === 0, A.errors.slice(0, 3).join(' | '));

  /* 3) 중복 렌더·효율 */
  /* v38 부팅 직후 4,071노드. 위 C2에서 내 주변 탭을 한 번 그려 40여 노드가 더 있다. */
  /* v42 홈 요약 4장(+31) · 글자 크기 카드 · v43 인트로 장면이 더해져 4,224 — 상한만 4,300으로 올린다.
     v47 키보드 안내·낭독 영역·빈 자리 안내·로딩 시연 절(+22)이 더해져 4,322 — 상한만 4,360으로. */
  ok('D1 DOM 노드 수가 v38 규모 그대로(4,071~4,360)', doc.getElementsByTagName('*').length >= 4071 &&
    doc.getElementsByTagName('*').length <= 4360, String(doc.getElementsByTagName('*').length));
  ok('D2 홈 요약 카드 한 번만 그려짐(중복 렌더 없음)', doc.querySelectorAll('#homeSummaryCard').length === 1 &&
    doc.querySelectorAll('#homePassCard').length === 1 &&
    doc.querySelectorAll('#homeSummaryCard .sum-row').length >= 2 &&
    doc.querySelectorAll('#homePassCard .sum-row').length >= 1,
    doc.querySelectorAll('#homeSummaryCard .sum-row').length + '/' + doc.querySelectorAll('#homePassCard .sum-row').length);
  ok('D3 금액 표기 그대로(90,000원·무료)', /90,000원/.test(cleanText(doc)) && /무료/.test(cleanText(doc)),
    String(cleanText(doc).slice(0, 40)));
  ok('D4 flush 재호출은 안전(중복 렌더 없음)', (function () {
    const before = doc.getElementsByTagName('*').length;
    P.flush();
    return doc.getElementsByTagName('*').length === before && P.stats().finished === true;
  })(), String(doc.getElementsByTagName('*').length));

  /* 4) 이미지·자산 */
  const lazyImgs = HTML.match(/alt="(?:방문 사진 미리보기|방문 일지 사진|선생님이 올린 방문 사진|방문 사진)"[^>]*>/g) || [];
  ok('E1 일지 사진 4곳 모두 loading="lazy"', lazyImgs.length === 4 && lazyImgs.every((t) => /loading="lazy"/.test(t)),
    lazyImgs.length + '/' + lazyImgs.filter((t) => /loading="lazy"/.test(t)).length);
  ok('E2 일지 사진 4곳 모두 decoding="async"', lazyImgs.length === 4 && lazyImgs.every((t) => /decoding="async"/.test(t)),
    String(lazyImgs.filter((t) => /decoding="async"/.test(t)).length));
  ok('E3 위쪽 로고(#brandMark)는 lazy 아님(첫 화면)', !/id="brandMark"[^>]*loading="lazy"/.test(HTML));
  const icons = HTML.match(/rel="apple-touch-icon"[^>]*href="data:image\/png;base64,([A-Za-z0-9+/=]+)"/);
  const brand = HTML.match(/id="brandMark" src="data:image\/png;base64,([A-Za-z0-9+/=]+)"/);
  ok('E4 홈 화면 아이콘 180px로 축소(45KB 이하)', !!icons && icons[1].length <= 45000, icons ? icons[1].length : 'none');
  ok('E5 본문 로고 data URI 45KB 이하', !!brand && brand[1].length <= 45000, brand ? brand[1].length : 'none');
  ok('E6 index.html 1.4MB 이하(v41 디자인 레이어 포함 1.36MB · v35 상한 1.45MB 이내)', Buffer.byteLength(HTML, 'utf8') <= 1450 * 1024, String(Buffer.byteLength(HTML, 'utf8')));
  ok('E7 CSS 길이 상한(v48 경계·가로모드·인쇄 절 추가, 24.3만자 이하)', STYLE.length >= 159697 && STYLE.length <= 243000, String(STYLE.length));

  /* 5) 지연 렌더 뒤에도 v24·v31·v34·v38 계약 유지 */
  ok('F1 dialog 전부 접근성 이름 보유(22개 이상)', M.a11y.dialogCount() === M.a11y.labelledDialogs() &&
    M.a11y.dialogCount() >= 22, String(M.a11y.dialogCount()) + '/' + String(M.a11y.labelledDialogs()));
  ok('F2 시작 화면(게이트)이 열려 있고 배경이 잠김', doc.querySelector('#entryGate').classList.contains('is-open') &&
    M.a11y.backgroundLocked() === true);
  ok('F3 포커스가 열린 게이트 안에 있음', M.a11y.focusInside('#entryGate'), M.a11y.topDialog());
  ok('F4 조작 요소 접근성 이름 누락 0', M.a11y.auditAll().blank.length === 0, JSON.stringify(M.a11y.auditAll().blank.slice(0, 3)));
  ok('F5 터치 영역 최소 44px 위반 0', A.window.__ttokttokTouch.violations().length === 0,
   JSON.stringify(A.window.__ttokttokTouch.violations().slice(0, 3)));
  ok('F6 터치 간격 8px 위반 0', A.window.__ttokttokTouch.gapViolations().length === 0,
   JSON.stringify(A.window.__ttokttokTouch.gapViolations().slice(0, 3)));
  ok('F7 Escape로 게이트 지역 시트 닫힘', (function () {
    const btn = doc.querySelector('#gateRegionBtn');
    if (btn) btn.click();
    const sheet = doc.querySelector('#regionSheet');
    const opened = sheet.classList.contains('is-open');
    doc.dispatchEvent(new A.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    return opened && !sheet.classList.contains('is-open');
  })(), String(doc.querySelector('#regionSheet').className));

  /* 6) 불변 */
  ok('G1 단가 90,000·70,000·수수료 22.2% 불변', M.pricing.consumerPrice === 90000 &&
    M.pricing.teacherPayout === 70000 && M.pricing.platformFeeRate === 0.2222, JSON.stringify(M.pricing));
  ok('G2 정산 D+3·15일/말일 불변', M.settlementRule.confirmDays === 3 &&
    JSON.stringify(M.settlementRule.payDays) === '[15,"end"]', JSON.stringify(M.settlementRule));
  ok('G3 시드 예약 TT-261021-7302 유지', M.reservations().some((r) => r.no === 'TT-261021-7302'));
  ok('G4 전 화면 문구 금지어 0(v38 계약)', M.auditCopy(cleanText(doc)).length === 0,
    JSON.stringify(M.auditCopy(cleanText(doc)).slice(0, 3)));
  ok('G5 용어 표준 불변(보호자·선생님·회차권)', M.copyTerms.guardian === '보호자' && M.copyTerms.teacher === '선생님' &&
    M.copyTerms.pass === '회차권' && M.copyTerms.round === '회차');

  A.dom.window.close();

  /* 7) 저장 차단(사생활 보호 모드) */
  const B = makeDom({ blockStorage: true });
  ok('H1 저장 차단에서도 부트 완료', await waitBooted(B.window), String(B.window.__ttokttokBooted));
  const BP = B.window.__ttokttokPerf.stats();
  ok('H2 저장 차단에서도 유휴 렌더 전부 완료', BP.deferredRendered === BP.deferredTotal && BP.pending === 0,
    BP.deferredRendered + '/' + BP.deferredTotal);
  ok('H3 저장 차단에서도 선생님 목록·알림함 렌더', B.doc.querySelectorAll('#teacherList [data-teacher]').length === 8 &&
    B.doc.querySelectorAll('#notifList .notif').length >= 1,
    B.doc.querySelectorAll('#teacherList [data-teacher]').length + '/' + B.doc.querySelectorAll('#notifList .notif').length);
  ok('H4 저장 차단에서도 오류 0', B.errors.length === 0, B.errors.slice(0, 3).join(' | '));
  ok('H5 저장 차단에서도 가격·시드 불변', B.window.__ttokttokModel.pricing.consumerPrice === 90000 &&
    B.window.__ttokttokModel.reservations().some((r) => r.no === 'TT-261021-7302'));
  B.dom.window.close();

  console.log('\nV39 RESULT: ' + pass + ' passed, ' + fails.length + ' failed');
  if (fails.length) {
    console.log('FAILURES:');
    fails.forEach((f) => console.log(' - ' + f));
  }
  process.exit(fails.length ? 1 : 0);
}

run().catch((e) => { console.log('FATAL', (e && e.stack) || e); process.exit(1); });
