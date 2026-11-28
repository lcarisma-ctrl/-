/*
 * 똑똑쌤 v48 — 경계 대비·로빙 탭인덱스·가로모드·인쇄 (jsdom)
 * 실행: cd projects/ttokttok-app/tests && node --max-old-space-size=2600 app.v48.test.js
 *
 * 이 스위트가 고정하는 것
 *   · 조작 요소의 테두리 토큰이 배경 대비 3:1 이상이다(라이트·다크) — WCAG 1.4.11
 *   · 카드·배지·표 셀은 낮은 대비 선을 남기지 않고 '선 없음'으로 정리했다
 *   · 선생님 목록은 Tab 정지점이 1개(로빙 탭인덱스)이고 방향키로 카드를 옮긴다
 *   · 가로모드(짧은 화면) 미디어 규칙과 인쇄 미디어 규칙이 있다
 *   · 인쇄는 '가장 위에 열린 시트' 하나만 대상으로 삼는다
 *   · 단가·수수료·정산·시드·백업 스키마·시연용 배지는 그대로
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
  if (cond) { pass++; } else { fails.push(name + (extra !== undefined ? ' :: ' + JSON.stringify(extra) : '')); }
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
      if (o.wide) {
        window.matchMedia = function (q) {
          return {
            media: q, matches: /min-width:1280px/.test(q),
            addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}
          };
        };
      }
      if (o.onWindow) o.onWindow(window);
    }
  });
  return { dom, window: dom.window, doc: dom.window.document, errors };
}
async function waitBooted(w) {
  const until = Date.now() + 40000;
  while (!w.__ttokttokBooted && Date.now() < until) await sleep(20);
  return !!w.__ttokttokBooted;
}
const click = (el) => el && el.dispatchEvent(new el.ownerDocument.defaultView.MouseEvent('click', { bubbles: true, cancelable: true }));
const key = (el, k, extra) => {
  const w = el.ownerDocument.defaultView;
  const ev = new w.KeyboardEvent('keydown', Object.assign({ key: k, bubbles: true, cancelable: true }, extra || {}));
  el.dispatchEvent(ev);
  return ev;
};

/* CSS 미디어 블록 하나의 본문 (중괄호 균형) */
function mediaBlock(header, from) {
  const i = STYLE.indexOf(header, from || 0);
  if (i < 0) return null;
  const start = STYLE.indexOf('{', i);
  let d = 0;
  for (let p = start; p < STYLE.length; p++) {
    if (STYLE[p] === '{') d++;
    else if (STYLE[p] === '}') { d--; if (!d) return STYLE.slice(start + 1, p); }
  }
  return null;
}
/* 대비 계산(스크립트와 같은 WCAG 식) */
function parseHex(h) {
  const s = h.replace('#', '');
  return [parseInt(s.slice(0, 2), 16), parseInt(s.slice(2, 4), 16), parseInt(s.slice(4, 6), 16)];
}
function lum(rgb) {
  const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  return 0.2126 * f(rgb[0]) + 0.7152 * f(rgb[1]) + 0.0722 * f(rgb[2]);
}
function ratio(a, b) {
  const la = lum(parseHex(a)), lb = lum(parseHex(b));
  const hi = Math.max(la, lb), lo = Math.min(la, lb);
  return (hi + 0.05) / (lo + 0.05);
}

const V48_AT = STYLE.indexOf('14. v48');
const V48_LAND = mediaBlock('@media (orientation: landscape) and (max-height: 500px)', V48_AT) || '';
const V48_PRINT = mediaBlock('@media print', V48_AT) || '';

async function run() {
  /* ── 1) 버전·부팅·훅 ─────────────────────────────────────────── */
  const A = makeDom();
  await waitBooted(A.window);
  const w = A.window, doc = A.doc;
  const $ = (s, r) => (r || doc).querySelector(s);
  const $$ = (s, r) => Array.from((r || doc).querySelectorAll(s));
  ok('A1 meta v48', ($('meta[name="app-version"]') || {}).content === 'v50', ($('meta[name="app-version"]') || {}).content);
  ok('A2 부팅 오류 0', !A.errors.length, A.errors.slice(0, 2));
  ok('A3 v47 스켈레톤 훅 유지', !!w.__ttokttokSkeleton && w.__ttokttokSkeleton.version === 'v47');
  ok('A4 v48 로빙 훅 노출', !!w.__ttokttokRoving && /^v4[89]$/.test(w.__ttokttokRoving.version), w.__ttokttokRoving);
  ok('A5 v48 인쇄 훅 노출', !!w.__ttokttokPrint && /^v(49|50)$/.test(w.__ttokttokPrint.version) && typeof w.__ttokttokPrint.mark === 'function');
  ok('A6 v45 테마 훅 유지', !!w.__ttokttokTheme && w.__ttokttokTheme.version === 'v45');

  /* ── 2) 경계 대비 토큰 (WCAG 1.4.11 — 비텍스트 3:1) ──────────── */
  ok('B1 v48 CSS 절이 있다', V48_AT > 0);
  ok('B2 v48 절은 v47 절 뒤에 있다', V48_AT > STYLE.indexOf('13. v47'));
  function rootBlock(name) {
    const i = STYLE.indexOf(name);
    if (i < 0) return '';
    let d = 0;
    for (let p = i; p < STYLE.length; p++) {
      if (STYLE[p] === '{') d++;
      else if (STYLE[p] === '}') { d--; if (!d) return STYLE.slice(i, p + 1); }
    }
    return '';
  }
  const lightRoot = rootBlock(':root{');
  const darkRoot = rootBlock(':root[data-theme="dark"]');
  const edgeLight = (lightRoot.match(/--edge-ctl:\s*(#[0-9A-Fa-f]{6})/) || [])[1];
  const edgeDark = (darkRoot.match(/--edge-ctl:\s*(#[0-9A-Fa-f]{6})/) || [])[1];
  ok('B3 라이트 경계 토큰', !!edgeLight, edgeLight);
  ok('B4 다크 경계 토큰', !!edgeDark, edgeDark);
  ok('B5 라이트 경계 ≥3:1 (페이지 #F7F8FA)', !!edgeLight && ratio(edgeLight, '#F7F8FA') >= 3,
    edgeLight && ratio(edgeLight, '#F7F8FA').toFixed(2));
  ok('B6 라이트 경계 ≥3:1 (카드 #FFFFFF)', !!edgeLight && ratio(edgeLight, '#FFFFFF') >= 3,
    edgeLight && ratio(edgeLight, '#FFFFFF').toFixed(2));
  ok('B7 다크 경계 ≥3:1 (페이지 #0B1119)', !!edgeDark && ratio(edgeDark, '#0B1119') >= 3,
    edgeDark && ratio(edgeDark, '#0B1119').toFixed(2));
  ok('B8 다크 경계 ≥3:1 (카드 #151D29)', !!edgeDark && ratio(edgeDark, '#151D29') >= 3,
    edgeDark && ratio(edgeDark, '#151D29').toFixed(2));
  ok('B9 조작 요소가 경계 토큰을 쓴다(버튼·칩·입력)', /body \.btn-outline,body \.chip,body \.segmented button/.test(STYLE) &&
    /body select,body \.input,body textarea,/.test(STYLE), edgeLight);
  ok('B10 조작 요소 규칙은 !important로 못 박는다', /body \.chip,body \.segmented button[^{]*\{border-color:var\(--edge-ctl\)!important\}/.test(STYLE));
  ok('B11 채워진 선택 상태는 테두리를 비운다', /body \.chip\.is-on,body \.segmented button\.is-on[^{]*\{border-color:transparent!important\}/.test(STYLE));
  ok('B12 표면(카드·배지·표 셀)은 낮은 대비 선을 남기지 않는다',
    /body \.card,body \.teacher,body \.card-form,body \.pass,body \.booking-row/.test(STYLE) &&
    /body \.home-program-card,body \.h-mini-card,body \.report-cta\{border-color:transparent!important\}/.test(STYLE));
  ok('B13 표면 규칙은 테두리 폭을 남긴다(레이아웃 불변)', !/border:\s*0/.test((STYLE.match(/body \.card,body \.teacher[^}]*\}/) || [''])[0]));
  ok('B14 상태(선택·찜·호버) 테두리는 되살린다', /body \.pass\.is-on\{border-color:var\(--ink-title\)!important\}/.test(STYLE) &&
    /body \.teacher\.is-selected\{border-color:var\(--line-blue\)!important\}/.test(STYLE) &&
    /body \.teacher\.is-fav\{border-color:var\(--line-rose\)!important\}/.test(STYLE));
  ok('B15 구분선 토큰은 건드리지 않았다', /--line:rgba\(15,23,42,\.06\)/.test(STYLE) && /--line-2:rgba\(15,23,42,\.05\)/.test(STYLE));
  ok('B16 다크에서 카드 표면을 한 단 올린다', /:root\[data-theme="dark"\] \.card,\n:root\[data-theme="dark"\] \.teacher/.test(STYLE));
  ok('B17 입력창도 경계 토큰', /body input\[type=text\],body input\[type=tel\]/.test(STYLE));
  ok('B18 종이 토큰(인쇄)이 두 테마에 있다', /--paper:#FFFFFF/.test(lightRoot) && /--paper-ink:#0F172A/.test(lightRoot) &&
    /--paper:#FFFFFF/.test(darkRoot) && /--paper-ink:#0F172A/.test(darkRoot));
  ok('B19 :root는 한 블록(토큰 정합성 유지)', (STYLE.match(/:root\{/g) || []).length === 1);

  /* ── 3) 가로모드(짧은 화면) ─────────────────────────────────── */
  ok('C1 가로모드 절이 있다', V48_LAND.length > 200, V48_LAND.length);
  ok('C2 가로모드는 430px 우편함을 없앤다', /\.app\{max-width:none!important;width:100%!important/.test(V48_LAND));
  ok('C3 헤더를 44px로 줄인다', /\.app-header\{min-height:44px;padding:[^;]*!important/.test(V48_LAND) &&
    /\.brand-sub\{display:none!important\}/.test(V48_LAND));
  ok('C4 탭바를 줄이되 터치 44px은 지킨다', /\.tabbar\{position:fixed!important/.test(V48_LAND) &&
    /\.tabbtn\{min-height:44px!important/.test(V48_LAND) && /\.tabbtn\{[^}]*font-size:var\(--fs-10h\)/.test(V48_LAND));
  ok('C5 선생님 찾기는 두 칸(레일|목록)', /#screen-teachers \.tt46-cols\{display:grid!important;grid-template-columns:minmax\(0,\.66fr\)/.test(V48_LAND));
  ok('C6 시작 화면은 그림을 접고 CTA를 올린다', /\.gate-scene\{display:none!important\}/.test(V48_LAND) &&
    /\.gate-points\{display:grid!important;grid-template-columns:1fr 1fr!important/.test(V48_LAND));
  ok('C7 시트는 화면 높이를 다 쓴다', /\.sheet\{max-height:100vh!important/.test(V48_LAND));

  /* ── 4) 인쇄 ────────────────────────────────────────────────── */
  ok('D1 인쇄 절이 있다', V48_PRINT.length > 200, V48_PRINT.length);
  ok('D2 인쇄에서 헤더·탭바·토스트를 숨긴다',
    /\.app-header,\.tabbar,\.toast,\.book-total,#ttAlertHost/.test(V48_PRINT));
  ok('D3 인쇄에서 떠 있는 버튼·필터를 숨긴다', /\.role-switch,\.seg-tabs,\.rc-actions/.test(V48_PRINT) && /\[data-print-hide\]/.test(V48_PRINT));
  ok('D4 인쇄는 활성 화면 하나만', /\.screen\{display:none!important\}/.test(V48_PRINT) &&
    /body:not\(\.sheet-open\) \.screen\.is-active\{display:block!important\}/.test(V48_PRINT));
  ok('D5 인쇄는 .is-print 시트만', /\.sheet-backdrop\.is-print\{display:block!important\}/.test(V48_PRINT));
  ok('D6 인쇄에서 시트는 정적으로 펼친다', /\.sheet-backdrop\.is-print \.sheet\{position:static!important;transform:none!important/.test(V48_PRINT));
  ok('D7 인쇄 색을 그대로 찍는다', /print-color-adjust:exact/.test(V48_PRINT));
  ok('D8 카드·표는 페이지 중간에서 잘리지 않는다', /break-inside:avoid/.test(V48_PRINT));
  ok('D9 정산서 시트 안내문·버튼줄은 인쇄에서 빠진다', /data-print-hide/.test(HTML) &&
    ($('#stlPrintNote') || {}).getAttribute && $('#stlPrintNote').getAttribute('data-print-hide') !== null);

  /* ── 5) 로빙 탭인덱스 ──────────────────────────────────────── */
  const list = $('#teacherList');
  ok('E1 목록에 낭독 안내가 붙어 있다', list.getAttribute('aria-describedby') === 'teacherListHint' &&
    /방향키/.test(($('#teacherListHint') || {}).textContent || ''));
  ok('E2 목록은 그룹으로 읽힌다', list.getAttribute('role') === 'group' && /선생님 목록/.test(list.getAttribute('aria-label') || ''));
  click($('[data-login="customer"]'));
  await sleep(260);
  click($('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]'));
  await sleep(300);
  const cards = () => $$('#teacherList .teacher');
  /* v49 · 정지점은 카드가 아니라 카드 전체를 덮는 열기 버튼(.t-open)에 있다 */
  const openers = () => $$('#teacherList .teacher .t-open');
  const tabStops = () => openers().filter((c) => c.getAttribute('tabindex') === '0');
  ok('E3 카드 8명', cards().length === 8, cards().length);
  ok('E4 Tab 정지점은 목록 전체 1개', tabStops().length === 1, tabStops().length);
  ok('E5 첫 열기 버튼이 정지점', openers()[0].getAttribute('tabindex') === '0');
  ok('E6 나머지 열기 버튼은 -1', openers().slice(1).every((c) => c.getAttribute('tabindex') === '-1'));
  ok('E7 훅도 1개로 센다', w.__ttokttokRoving.tabStops() === 1 && w.__ttokttokRoving.count() === 8,
    [w.__ttokttokRoving.tabStops(), w.__ttokttokRoving.count()]);

  /* 방향키로 옮기면 정지점도 따라온다 */
  openers()[0].focus();
  ok('E8 첫 열기 버튼에 초점', doc.activeElement === openers()[0]);
  key(openers()[0], 'ArrowDown');
  ok('E9 ↓로 다음 카드', doc.activeElement === openers()[1], doc.activeElement && doc.activeElement.getAttribute('aria-label'));
  ok('E10 정지점이 옮겨간다', openers()[1].getAttribute('tabindex') === '0' && openers()[0].getAttribute('tabindex') === '-1');
  ok('E11 여전히 정지점은 1개', tabStops().length === 1);
  ok('E12 훅이 고른 카드를 기억한다', w.__ttokttokRoving.activeId() === cards()[1].getAttribute('data-teacher'),
    w.__ttokttokRoving.activeId());
  key(openers()[1], 'End');
  ok('E13 End는 마지막 카드', doc.activeElement === openers()[7] && openers()[7].getAttribute('tabindex') === '0');
  key(openers()[7], 'Home');
  ok('E14 Home은 첫 카드', doc.activeElement === openers()[0]);

  /* 필터로 목록이 다시 그려져도 정지점은 1개 */
  click($('#teacherFilters [data-cat="stroke"]'));
  await sleep(260);
  ok('E15 필터 뒤 카드 3명', cards().length === 3, cards().length);
  ok('E16 다시 그려도 정지점 1개', tabStops().length === 1, tabStops().length);
  click($('#teacherFilters [data-cat="all"]'));
  await sleep(260);
  ok('E17 전체로 돌아와도 정지점 1개', cards().length === 8 && tabStops().length === 1);

  /* 카드에서 나가면 다음 칸으로 (jsdom은 Tab 이동을 흉내내지 않으므로 DOM 순서로 확인) */
  const mainCol = $('#teacherMainCol');
  const afterList = Array.from(mainCol.children).filter((el) => (cards()[0].compareDocumentPosition(el) & 4) !== 0);
  ok('E18 목록 다음에 프로필 열·안내가 온다(DOM 순서)', afterList.some((el) => el.id === 'teacherPane'),
    afterList.map((el) => el.id || el.className));

  /* ── 6) 인쇄 대상 표시 ─────────────────────────────────────── */
  click($('#teacherList .teacher'));
  await sleep(220);
  ok('F1 카드를 누르면 시트가 열린다', $('#teacherSheet').classList.contains('is-open'));
  const printed = w.__ttokttokPrint.mark();
  ok('F2 가장 위 시트를 인쇄 대상으로 표시', printed === 'teacherSheet' && $('#teacherSheet').classList.contains('is-print'),
    printed);
  ok('F3 한 번에 하나만', $$('.sheet-backdrop.is-print').length === 1);
  click($('#teacherSheet [data-sheet-close]'));
  await sleep(200);
  w.__ttokttokPrint.mark();
  ok('F4 닫으면 인쇄 대상이 없다', $$('.sheet-backdrop.is-print').length === 0);

  /* ── 7) 비즈니스 규칙 불변 ─────────────────────────────────── */
  const M = w.__ttokttokModel;
  const pr = M && M.pricing;
  ok('G1 단가 90,000/70,000·수수료 22.2%', pr && pr.consumerPrice === 90000 && pr.teacherPayout === 70000 && pr.platformFeeRate === 0.2222,
    pr && pr.consumerPrice);
  ok('G2 정산 D+3·15일/말일', pr && pr.settlementConfirmDays === 3 && JSON.stringify(pr.settlementPayDays) === '[15,"end"]');
  ok('G3 회차권 5종 유지', pr && pr.plans.map((p) => p.price).join(',') === '0,90000,320000,592000,840000');
  ok('G4 시드 예약 TT-261021-7302', /TT-261021-7302/.test(HTML));
  ok('G5 백업 스키마 ttokttok.v23', /ttokttok\.v23/.test(HTML));
  ok('G6 시연용 배지', /시연용/.test(HTML));
  ok('G7 외부 연결 없음(fetch/XMLHttpRequest/supabase)', !/\bfetch\(|XMLHttpRequest|supabase\.co/i.test(HTML));
  ok('G8 문의 번호·상호 표기 유지', /031-919-8577/.test(HTML) && /상호 똑똑쌤/.test(HTML));

  /* ── 8) 중복 id·구조 ──────────────────────────────────────── */
  const ids = $$('[id]').map((el) => el.id);
  const dup = ids.filter((v, i) => ids.indexOf(v) !== i);
  ok('H1 중복 id 0', dup.length === 0, dup.slice(0, 4));
  ok('H2 카드 안내문은 낭독 전용', ($('#teacherListHint') || {}).className === 'sr-only');

  console.log('\n=== v48 jsdom: ' + pass + ' 통과 / ' + fails.length + ' 실패 ===');
  if (fails.length) {
    fails.forEach((f) => console.log('  ✗ ' + f));
    process.exitCode = 1;
  }
}

run().catch((e) => { console.error(e); process.exitCode = 1; });
