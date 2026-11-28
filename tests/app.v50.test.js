/*
 * 똑똑쌤 v50 — 정산서 인쇄 줄 맞춤·여백 통일 (jsdom)
 * 실행: cd projects/ttokttok-app/tests && node --max-old-space-size=2600 app.v50.test.js
 *
 * 이 스위트가 고정하는 것
 *   · 종이에서는 여백이 한 벌이다 — 머리말·카드·꼬리말이 --pad-print/--pad-print-text 한 값
 *   · 시트·화면마다 다르던 좌우 패딩(18/18/32)과 카드 안쪽(13/15/16/18/20)을 인쇄에서 하나로
 *   · 정산서 회차 목록은 카드 속 글자선에서 시작하고 금액 끝선도 카드와 같다
 *   · 머리 카드의 발급줄·정산규칙줄은 각각 한 줄 — '(15일·말일) 지급'만 떨어지지 않는다
 *   · 인쇄 줄을 재는 훅(frame)이 있다
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

/* CSS 블록 하나의 본문 (중괄호 균형) */
function block(header, from) {
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
const V50_AT = STYLE.indexOf('18. v50');
const V50_PRINT = block('@media print', V50_AT) || '';
const V50_RULES = STYLE.slice(V50_AT > 0 ? V50_AT : STYLE.length);

async function run() {
  /* ── 1) 버전·부팅·훅 ─────────────────────────────────────────── */
  const A = makeDom();
  await waitBooted(A.window);
  const w = A.window, doc = A.doc;
  const $ = (s, r) => (r || doc).querySelector(s);
  const $$ = (s, r) => Array.from((r || doc).querySelectorAll(s));
  ok('A1 meta v50', ($('meta[name="app-version"]') || {}).content === 'v50', ($('meta[name="app-version"]') || {}).content);
  ok('A2 부팅 오류 0', !A.errors.length, A.errors.slice(0, 2));
  ok('A3 인쇄 훅 v50 · frame()', !!w.__ttokttokPrint && w.__ttokttokPrint.version === 'v50' && typeof w.__ttokttokPrint.frame === 'function',
    w.__ttokttokPrint && w.__ttokttokPrint.version);
  ok('A4 v49 인쇄 훅(머리·꼬리) 유지', typeof w.__ttokttokPrint.runner === 'function' && typeof w.__ttokttokPrint.mark === 'function');
  ok('A5 v50 CSS 절이 v49 절 뒤에 있다', V50_AT > 0 && V50_AT > STYLE.indexOf('17. v49'));

  /* ── 2) 인쇄 여백: 한 벌의 값 ───────────────────────────────── */
  ok('B1 종이 여백 토큰 두 개(--pad-print/--pad-print-text)', /--pad-print:18px;/.test(STYLE) && /--pad-print-text:16px;/.test(STYLE) &&
    (STYLE.match(/:root\{/g) || []).length === 1);
  ok('B2 머리말은 여백선에서 시작하고 글자는 카드 속 글자선에', /#printRunner\{left:var\(--pad-print\)!important;right:var\(--pad-print\)!important;padding:0 var\(--pad-print-text\) 2mm!important\}/.test(V50_PRINT));
  ok('B3 꼬리말도 같은 선', /#printFoot\{left:var\(--pad-print\)!important;right:var\(--pad-print\)!important;padding:2mm var\(--pad-print-text\) 0!important\}/.test(V50_PRINT));
  ok('B4 시트·화면 좌우 패딩을 한 값으로', /\.sheet-backdrop\.is-print \.sheet-scroll\{padding-left:var\(--pad-print\)!important;padding-right:var\(--pad-print\)!important\}/.test(V50_PRINT) &&
    /#screen-journal,#screen-admin,#screen-tp-settle,/.test(V50_PRINT));
  ok('B5 화면 제목도 카드 속 글자선', /\.page-head\{padding-left:var\(--pad-print-text\)!important;padding-right:var\(--pad-print-text\)!important\}/.test(V50_PRINT));
  ok('B6 카드 안쪽 여백을 종이에서 15px로 고정', /#weeklySheet \.rc-card\{padding:15px!important\}/.test(V50_PRINT) &&
    /#screen-tp-settle :is\(\.card,\.admin-card\)/.test(V50_PRINT) &&
    /#settlementPrintBody :is\(\.card,\.admin-card\)/.test(V50_PRINT));
  ok('B7 한 낱말 덩이는 줄 끝에서 안 쪼갠다', /\.nw\{white-space:nowrap\}/.test(V50_RULES));

  /* ── 3) 정산서 머리 카드: 두 줄로 정돈 ─────────────────────── */
  ok('C1 발급·수수료는 규칙줄과 다른 문단', /'<p class="fine" style="margin:5px 0 0">' \+ settleClause\('발급 '/.test(HTML) &&
    /settleClause\('수수료 22\.2%'\)/.test(HTML));
  ok('C2 규칙 문구는 · 로 나눠 각각 nowrap', /String\(s\.rule\.label \|\| ''\)\.split\(' · '\)\.map\(settleClause\)\.join\(' · '\)/.test(HTML));
  ok('C3 settleClause는 nowrap span', /function settleClause\(t\) \{ return '<span class="nw">' \+ esc\(t\) \+ '<\/span>'; \}/.test(HTML));

  /* ── 4) 미리보기 본문: 줄과 금액의 세로선 ─────────────────── */
  click($('.tabbar[data-mode="therapist"] .tabbtn[data-tab="tp-settle"]'));
  await sleep(300);
  const st = (w.__ttokttokModel && w.__ttokttokModel.openStatementPreview) ? w.__ttokttokModel.openStatementPreview() : null;
  await sleep(200);
  ok('D1 미리보기 본문이 열린다', !!st && $$('#settlementPrintBody .admin-card').length >= 2, st && st.rows && st.rows.length);
  const fines = $$('#settlementPrintBody .admin-card .fine');
  ok('D2 머리 카드 발급줄 내용', fines.length > 0 && /^발급 2026\.11\.\d{2}/.test(fines[0].textContent.trim()) && /수수료 22\.2%/.test(fines[0].textContent),
    fines[0] && fines[0].textContent);
  ok('D3 정산규칙줄은 따로 한 문단', fines.length > 1 && /회차 완료 D\+3 정산 확정/.test(fines[1].textContent) && /15일·말일/.test(fines[1].textContent),
    fines[1] && fines[1].textContent);
  ok('D4 규칙줄은 절마다 nowrap span', fines.length > 1 && fines[1].querySelectorAll('.nw').length >= 2,
    fines[1] && fines[1].querySelectorAll('.nw').length);
  ok('D5 발급줄은 절마다 nowrap span', fines.length > 0 && fines[0].querySelectorAll('.nw').length === 2,
    fines[0] && fines[0].querySelectorAll('.nw').length);
  const rows = $$('#settlementPrintBody [data-print-row]');
  ok('D6 회차 줄이 있다', rows.length > 0, rows.length);
  ok('D7 회차 줄은 카드 속 글자선만큼 안쪽에서 시작', rows.every((r) => /padding:7px var\(--pad-print-text,16px\)/.test(r.getAttribute('style') || '')),
    rows[0] && rows[0].getAttribute('style'));
  ok('D8 회차 줄에 0 패딩짜리(카드 밖) 줄이 없다', rows.every((r) => !/padding:7px 0(;|$)/.test(r.getAttribute('style') || '')));
  ok('D9 회차 금액은 오른쪽 <b>', rows.every((r) => !!r.querySelector('div > b:last-child')));

  /* ── 5) 줄을 재는 훅 ───────────────────────────────────────── */
  w.__ttokttokPrint.mark();
  const fr = w.__ttokttokPrint.frame();
  ok('E1 frame()이 카드·회차·머리·꼬리 자리를 돌려준다', !!fr && !!fr.card && !!fr.runner && !!fr.foot && 'rowText' in fr, fr);
  ok('E2 frame()에 버전 표기', !!fr && fr.version === 'v50');

  /* ── 6) 비즈니스 규칙 불변 ─────────────────────────────────── */
  const M = w.__ttokttokModel;
  const pr = M && M.pricing;
  ok('H1 단가 90,000/70,000·수수료 22.2%', pr && pr.consumerPrice === 90000 && pr.teacherPayout === 70000 && pr.platformFeeRate === 0.2222,
    pr && pr.consumerPrice);
  ok('H2 정산 D+3·15일/말일', pr && pr.settlementConfirmDays === 3 && JSON.stringify(pr.settlementPayDays) === '[15,"end"]');
  ok('H3 시드 예약 TT-261021-7302', /TT-261021-7302/.test(HTML));
  ok('H4 백업 스키마 ttokttok.v23', /ttokttok\.v23/.test(HTML));
  ok('H5 시연용 배지', /시연용/.test(HTML));
  ok('H6 외부 연결 없음(fetch/XMLHttpRequest/supabase)', !/\bfetch\(|XMLHttpRequest|supabase\.co/i.test(HTML));
  ok('H7 중복 id 0', (function () {
    const ids = $$('[id]').map((el) => el.id);
    return ids.filter((v, i) => ids.indexOf(v) !== i).length === 0;
  })());
  ok('H8 회차 14건·실수령 947,660원(시드 그대로)', !!st && st.rows.length === 14 && st.totals.netExpected === 947660,
    st && [st.rows.length, st.totals.netExpected]);

  console.log('\n=== v50 jsdom: ' + pass + ' 통과 / ' + fails.length + ' 실패 ===');
  if (fails.length) {
    fails.forEach((f) => console.log('  ✗ ' + f));
    process.exitCode = 1;
  }
}

run().catch((e) => { console.error(e); process.exitCode = 1; });
