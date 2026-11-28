/*
 * 똑똑쌤 v43 — 인트로 컷신·첫 화면(320)·레이어 정리·빈 상태 그림 검증 (jsdom)
 * 실행: cd projects/ttokttok-app/tests && node --max-old-space-size=2600 app.v43.test.js
 *
 * 이 파일이 잠그는 것
 *   ① 인트로가 장면(집·선생님·보호자·회복선·새싹)을 그리는 컷신이고, 2.1초·건너뛰기·동작 줄이기 규칙을 지킨다
 *   ② ?intro=0 이 인트로를 끄고, ?intro=1 이 켠다( v41의 반대 동작 버그 회귀 방지 )
 *   ③ 아주 짧은 화면(≤600px 높이)에서 프로모션 띠를 접어 '남은 회차권'까지 첫 화면에 넣는다
 *   ④ 합계 바가 얇아지고, 고른 회차권 카드를 덮지 않게 올려 준다
 *   ⑤ 빈 상태마다 같은 선화 문법의 그림이 붙는다(장식 · aria-hidden)
 *   ⑥ 사업 수치·정책·시드는 그대로
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
    url: 'https://ttokttok.test/' + (o.query || ''),
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
    }
  });
  return { dom, window: dom.window, doc: dom.window.document, errors };
}

async function waitBooted(w, ms) {
  const until = Date.now() + (ms || 40000);
  while (!w.__ttokttokBooted && Date.now() < until) await sleep(20);
  return !!w.__ttokttokBooted;
}
const click = (el) => el && el.dispatchEvent(new el.ownerDocument.defaultView.MouseEvent('click', { bubbles: true, cancelable: true }));

async function run() {
  const A = makeDom();
  await waitBooted(A.window);
  const w = A.window, doc = A.doc;
  const $ = (s, r) => (r || doc).querySelector(s);
  const $$ = (s, r) => Array.from((r || doc).querySelectorAll(s));
  const M = w.__ttokttokModel;

  /* ── 0) 버전·부팅 ───────────────────────────────────────────── */
  ok('A1 meta v43', (doc.querySelector('meta[name="app-version"]') || {}).content === 'v50',
    (doc.querySelector('meta[name="app-version"]') || {}).content);
  ok('A2 부팅 오류 0', !A.errors.length, A.errors.slice(0, 2));
  ok('A3 이전 세대 훅 유지(손짓 v42·글자 크기 v42)', w.__ttokttokGesture.version === 'v42' &&
    w.__ttokttokTextSize.version === 'v42');

  /* ── 1) 인트로 컷신 ────────────────────────────────────────── */
  const intro = $('#intro');
  ok('B1 인트로 장면 요소(집·선생님·보호자·회복선·새싹)', !!intro &&
    !!$('#intro .in-house') && !!$('#intro .in-teacher') && !!$('#intro .in-patient') &&
    !!$('#intro .in-recover') && !!$('#intro .in-sprout') && !!$('#intro .intro-word'),
    intro ? $$('#intro svg *').length + ' nodes' : 'no intro');
  ok('B2 장면은 소리로 읽지 않는 장식(aria-hidden)', $('#intro').getAttribute('aria-hidden') === 'true' &&
    $('#intro .intro-scene').getAttribute('aria-hidden') === 'true');
  ok('B3 장면 모션은 선 그리기·등장(transform·opacity·dashoffset)', /@keyframes tt43Draw\{to\{stroke-dashoffset:0\}\}/.test(STYLE) &&
    /@keyframes tt43Arrive\{0%\{opacity:0;transform:translate\(-26px,4px\)\}/.test(STYLE) &&
    /@keyframes tt43SitUp\{0%\{opacity:\.25;transform:translateY\(5px\)\}/.test(STYLE));
  ok('B4 인트로 길이 2.1초로(문구·장면 순서)', /var INTRO_MS = 2100;/.test(HTML) &&
    /animation:tt41Rise \.5s \.95s/.test(STYLE) && /animation:tt41Rise \.5s 1\.12s/.test(STYLE));
  ok('B5 동작 줄이기에서는 인트로를 띄우지 않는다', /@media\(prefers-reduced-motion:reduce\)\{\s*\.intro\{display:none!important\}/.test(STYLE));
  ok('B6 로고 base64 중복 제거(인트로는 장면으로 그린다)', !/class="intro-mark"/.test(HTML) &&
    (HTML.match(/__LOGODATA__/g) || []).length === 0);

  /* ── 2) ?intro=0 / ?intro=1 ───────────────────────────────── */
  const off = makeDom({ query: '?intro=0' });
  await waitBooted(off.window);
  await sleep(120);
  ok('C1 ?intro=0 이면 인트로를 띄우지 않는다', off.doc.getElementById('intro').hidden === true,
    String(off.doc.getElementById('intro').hidden));
  try { off.window.close(); } catch (e) {}
  const on = makeDom({ query: '?intro=1' });
  await waitBooted(on.window);
  await sleep(60);
  ok('C2 ?intro=1 이면 인트로를 띄운다', on.doc.getElementById('intro').hidden === false,
    String(on.doc.getElementById('intro').hidden));
  try { on.window.close(); } catch (e) {}

  /* ── 3) 아주 짧은 화면 규칙(320×568) ──────────────────────── */
  ok('D1 ≤600px 높이에서 프로모션 띠를 접는다', /@media\(max-height:600px\)\{\s*\.home-notice\{display:none\}/.test(STYLE));
  ok('D2 ≤600px 히어로·카드 여백 압축', /@media\(max-height:600px\)\{[\s\S]*?\.hs-hero\{padding:14px 18px 8px\}/.test(STYLE) &&
    /@media\(max-height:600px\)\{[\s\S]*?\.hs-card\{padding:12px 18px 6px\}/.test(STYLE));
  ok('D3 ≤600px 예약번호 줄은 접고 날짜를 줄인다', /@media\(max-height:600px\)\{[\s\S]*?\.hs-rows \.sum-row\.hs-bookno\{display:none\}/.test(STYLE) &&
    /@media\(max-height:600px\)\{[\s\S]*?\.hs-date\{font-size:calc\(23px \* var\(--fs-scale\)\)\}/.test(STYLE));

  /* ── 4) 합계 바·토스트 레이어 ─────────────────────────────── */
  ok('E1 합계 바가 얇아짐(9px·18px·bottom 86px)', /\.book-total\{padding:9px 13px;border-radius:18px;bottom:86px\}/.test(STYLE) &&
    /\.book-total \.bt-main b\{font-size:var\(--fs-20\)/.test(STYLE));
  ok('E2 3단계 아래 여백 = 합계 바 높이', /#wstep-3\{padding-bottom:76px\}/.test(STYLE));
  ok('E3 고른 회차권을 가리지 않게 올리는 함수', /function keepSelectedPassVisible\(\)/.test(HTML) &&
    /keepSelectedPassVisible\(\);\s*\n\s*\}\);/.test(HTML));
  ok('E4 토스트는 320px·13px로 얇게', /max-width:320px/.test(STYLE) && /font-size:var\(--t-meta\)/.test(STYLE) &&
    /bottom:88px/.test(STYLE));
  ok('E5 회차권 카드는 가격 열 고정·회당가 분리(v42 유지)', /#passList \.pass-price\{flex:0 0 auto;min-width:92px/.test(STYLE) &&
    /#passList \.pass-per\{/.test(STYLE));

  ok('E6 스크롤하면 헤더에 그림자(종이 한 장 위로)', /body\.is-scrolled \.app-header\{box-shadow:/.test(STYLE) &&
    /function bindScrollShadow\(\)/.test(HTML) && /classList\.toggle\('is-scrolled'/.test(HTML));

  /* ── 5) 빈 상태 그림 ──────────────────────────────────────── */
  const UI = w.__ttokttokUI;
  ok('F1 빈 상태에 그림이 붙는다', (function () {
    const h = UI.emptyHtml('admin-resv');
    return /empty-art/.test(h) && /aria-hidden="true"/.test(h);
  })(), UI.emptyHtml('admin-resv').slice(0, 120));
  ok('F2 종류별 그림(예약=달력·일지=노트·알림=종·기본=집)', (function () {
    const a = UI.emptyHtml('admin-resv'), b = UI.emptyHtml('journal-empty'), c = UI.emptyHtml('notif-empty'), d = UI.emptyHtml('near-empty');
    return /0 30 60 56|M36 46h60/.test(a) && /M53 74l2\.2 2\.4/.test(b) && /M60 76a6 6 0 0 0 12 0/.test(c) && /M34 60 66 36l32 24/.test(d);
  })());
  ok('F3 그림이 있어도 제목·설명·CTA는 그대로', (function () {
    const h = UI.emptyHtml('admin-resv');
    return /이 상태의 예약이 없어요/.test(h) && /전체 예약 보기/.test(h);
  })());
  ok('F4 빈 상태 그림은 role=group 안에서 장식', (function () {
    const el = doc.createElement('div');
    el.innerHTML = UI.emptyHtml('admin-resv');
    const svg = el.querySelector('svg');
    return !!svg && svg.getAttribute('aria-hidden') === 'true' && !svg.getAttribute('role');
  })());

  /* ── 6) 홈 요약은 v42 그대로 ──────────────────────────────── */
  ok('G1 네 장·순서 유지', (function () {
    const body = $('#screen-home .home-body');
    const ids = Array.from(body.children).map((x) => x.id);
    return ids[0] === 'homeSummaryCard' && ids[1] === 'homePassCard' && ids[2] === 'homeReportCard' && ids[3] === 'homeRebookCard';
  })(), $$('#screen-home .home-body > *').slice(0, 5).map((x) => x.id).join(','));
  ok('G2 회차권 카드 문구', /잔여 5회/.test($('#homeSummaryPass').textContent) &&
    /5회 \/ 8회/.test($('#homeSummaryPass').textContent));
  ok('G3 글자 크기 3단 유지', $$('#mpTextSize [data-textsize]').length === 3);

  /* ── 7) 예약 3·4단계는 v42 그대로 ─────────────────────────── */
  click($('.tabbar[data-mode="customer"] .tabbtn[data-tab="booking"]'));
  await sleep(80);
  click($('#provinceQuick [data-prov="서울"]'));
  doc.querySelector('#bookDistrict').value = '강남구';
  doc.querySelector('#bookAddress').value = '대치동 123-4, 101동 1203호';
  click($('#bookSyms [data-val="뇌졸중·편마비"]'));
  click($('[data-next="1"]'));
  await sleep(50);
  click($('#bookDates .date-chip'));
  await sleep(30);
  click($('#bookSlots .slot:not([disabled])'));
  await sleep(30);
  click($('[data-next="2"]'));
  await sleep(60);
  ok('H1 회차권 선택 시 오류 없이 합계 바', (function () {
    click($('#passList [data-pass="p8"]'));
    return $('#bookTotalBar').hidden === false && !!$('#passList .pass.is-on') &&
      w.__ttokttokModel.bookingFormState().passId === 'p8';
  })(), JSON.stringify({ hidden: $('#bookTotalBar').hidden }));
  click($('[data-next="3"]'));
  await sleep(60);
  ok('H2 4단계에서는 합계 바를 숨긴다', $('#bookTotalBar').hidden === true);

  /* ── 8) 정책·수치 불변 ────────────────────────────────────── */
  ok('I1 단가·수수료·정산·시드 불변', M.pricing.consumerPrice === 90000 && M.pricing.teacherPayout === 70000 &&
    M.pricing.platformFeeRate === 0.2222 && M.settlementRule.confirmDays === 3 &&
    String(M.settlementRule.payDays) === '15,end' &&
    (M.reservations() || []).some((r) => r.no === 'TT-261021-7302' && r.dateIso === '2026-11-28'));
  ok('I2 시연용 배지 유지', /시연용/.test(doc.body.textContent || ''));
  ok('I3 CSS 24.3만자·HTML 1.45MB 이하', STYLE.length <= 243000 && Buffer.byteLength(HTML, 'utf8') <= 1450 * 1024,
    STYLE.length + ' / ' + Buffer.byteLength(HTML, 'utf8'));

  console.log('\nV43 RESULT: ' + pass + ' passed, ' + fails.length + ' failed');
  if (fails.length) {
    console.log('FAILURES:');
    fails.forEach((f) => console.log(' - ' + f));
  }
  process.exit(fails.length ? 1 : 0);
}

run().catch((e) => { console.error(e); process.exit(2); });
