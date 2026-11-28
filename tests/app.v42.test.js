/*
 * 똑똑쌤 v42 — 홈·예약·관리자·제스처 마감 검증 (jsdom)
 * 실행: cd projects/ttokttok-app/tests && node --max-old-space-size=2600 app.v42.test.js
 *
 * 이 파일이 잠그는 것
 *   ① 홈 요약이 네 장(다음 방문·회차권·최근 4주·다시 예약)으로 나뉘고 순서·표시가 맞다
 *   ② 글자 크기 설정(보통·크게·아주 크게)이 타입 토큰 하나로 전 화면에 적용된다
 *   ③ 예약 3·4단계의 밀도 정리(가격 열 고정·4단계 합계 바 제거·이전 단계 버튼)
 *   ④ 관리자 운영 표의 열 맞춤(라벨·숫자·비율)과 지역 카드 수치 칸
 *   ⑤ 시트 스와이프 닫기·상태 배지 전환 모션의 훅과 CSS
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
      if (o.textsize) window.localStorage.setItem('ttokttok_textsize_v1', o.textsize);
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

async function waitBooted(w, ms) {
  const until = Date.now() + (ms || 40000);
  while (!w.__ttokttokBooted && Date.now() < until) await sleep(20);
  return !!w.__ttokttokBooted;
}
const textOf = (doc, sel) => {
  const el = doc.querySelector(sel);
  return el ? String(el.textContent || '').replace(/\s+/g, ' ').trim() : '';
};
const click = (el) => el && el.dispatchEvent(new el.ownerDocument.defaultView.MouseEvent('click', { bubbles: true, cancelable: true }));

async function run() {
  const A = makeDom();
  await waitBooted(A.window);
  const w = A.window, doc = A.doc;
  const $ = (s, r) => (r || doc).querySelector(s);
  const $$ = (s, r) => Array.from((r || doc).querySelectorAll(s));
  const M = w.__ttokttokModel;

  /* ── 0) 버전·부팅 ───────────────────────────────────────────── */
  ok('A1 meta(현재 빌드)', (doc.querySelector('meta[name="app-version"]') || {}).content === 'v47',
    (doc.querySelector('meta[name="app-version"]') || {}).content);
  ok('A2 부팅 오류 0', !A.errors.length, A.errors.slice(0, 2));
  ok('A3 손짓 훅 v42', !!w.__ttokttokGesture && w.__ttokttokGesture.version === 'v42',
    w.__ttokttokGesture && w.__ttokttokGesture.version);
  ok('A4 글자 크기 훅 v42', !!w.__ttokttokTextSize && w.__ttokttokTextSize.version === 'v42' &&
    w.__ttokttokTextSize.current === 'md' && w.__ttokttokTextSize.scale === 1,
    JSON.stringify(w.__ttokttokTextSize));

  /* ── 1) 타입 토큰이 사용자 배율 하나를 곱한다 ────────────────── */
  const tokenNames = ['fs-11h', 'fs-13', 'fs-22', 'fs-page', 't-hero', 't-body', 't-meta', 't-micro'];
  const tokenOf = (name) => {
    const m = STYLE.match(new RegExp('--' + name + '\\s*:\\s*([^;}]+)'));
    return m ? m[1].trim() : '';
  };
  ok('A5 타입 토큰이 모두 calc(Npx * var(--fs-scale))', tokenNames.every((n) =>
    /^calc\([0-9.]+px \* var\(--fs-scale\)\)$/.test(tokenOf(n))),
    tokenNames.map((n) => n + '=' + tokenOf(n)).join(' '));
  ok('A6 기본 배율 1', /--fs-scale:\s*1;/.test(STYLE));
  ok('A7 크게 1.15 · 아주 크게 1.3', /html\[data-textsize="lg"\]\{--fs-scale:1\.15\}/.test(STYLE) &&
    /html\[data-textsize="xl"\]\{--fs-scale:1\.3\}/.test(STYLE));
  ok('A8 토큰 기준 픽셀값 유지(v41과 같다)', /calc\(11\.5px \* var\(--fs-scale\)\)/.test(tokenOf('fs-11h')) &&
    /calc\(23px \* var\(--fs-scale\)\)/.test(tokenOf('fs-page')) &&
    /calc\(28px \* var\(--fs-scale\)\)/.test(tokenOf('t-hero')));

  /* ── 2) 글자 크기 화면 ──────────────────────────────────────── */
  const sizeBtns = $$('#mpTextSize [data-textsize]');
  ok('A9 글자 크기 3단(보통·크게·아주 크게)', sizeBtns.length === 3 &&
    /보통/.test(sizeBtns[0].textContent) && /크게/.test(sizeBtns[1].textContent) && /아주 크게/.test(sizeBtns[2].textContent),
    sizeBtns.map((b) => b.textContent.trim()).join('/'));
  ok('A10 기본은 보통(aria-checked 하나만)', sizeBtns.filter((b) => b.getAttribute('aria-checked') === 'true').length === 1 &&
    sizeBtns[0].getAttribute('aria-checked') === 'true' && /보통/.test(textOf(doc, '#mpTextHint')));
  click(sizeBtns[2]);
  await sleep(30);
  ok('A11 아주 크게 → html[data-textsize=xl]', doc.documentElement.getAttribute('data-textsize') === 'xl',
    doc.documentElement.getAttribute('data-textsize'));
  ok('A12 선택 저장(이 기기)', w.localStorage.getItem('ttokttok_textsize_v1') === 'xl',
    w.localStorage.getItem('ttokttok_textsize_v1'));
  ok('A13 선택 표시·훅 갱신', sizeBtns[2].getAttribute('aria-checked') === 'true' &&
    sizeBtns[0].getAttribute('aria-checked') === 'false' && /아주 크게/.test(textOf(doc, '#mpTextHint')) &&
    w.__ttokttokTextSize.scale === 1.3, JSON.stringify(w.__ttokttokTextSize));
  click(sizeBtns[0]);
  await sleep(20);
  ok('A14 보통으로 되돌리면 속성 제거', !doc.documentElement.getAttribute('data-textsize') &&
    w.localStorage.getItem('ttokttok_textsize_v1') === 'md');

  /* 새로 열어도 저장된 크기가 적용된다 */
  const B = makeDom({ textsize: 'lg' });
  await waitBooted(B.window);
  ok('A15 저장된 크게 → 새로 열어도 적용', B.doc.documentElement.getAttribute('data-textsize') === 'lg' &&
    B.window.__ttokttokTextSize.current === 'lg' && B.window.__ttokttokTextSize.scale === 1.15,
    B.doc.documentElement.getAttribute('data-textsize'));
  ok('A16 글자 크기 바꿔도 홈 데이터는 그대로', /TT-261021-7302/.test(textOf(B.doc, '#homeSummaryNext')),
    textOf(B.doc, '#homeSummaryNext').slice(0, 60));
  try { B.window.close(); } catch (e) {}

  /* ── 3) 홈 요약 네 장 ──────────────────────────────────────── */
  const cards = ['#homeSummaryCard', '#homePassCard', '#homeReportCard', '#homeRebookCard'];
  ok('A17 네 카드가 모두 있다', cards.every((s) => !!$(s)) && !!$('#homeFirstVisitCard'), cards.join(','));
  const body = $('#screen-home .home-body');
  const order = cards.map((s) => $(s)).map((el) => Array.prototype.indexOf.call(body.children, el));
  ok('A18 순서: 다음 방문 → 회차권 → 최근 4주 → 다시 예약 → 첫 방문 안내', order.every((v, i) => v >= 0 && (i === 0 || v > order[i - 1])) &&
    Array.prototype.indexOf.call(body.children, $('#homeFirstVisitCard')) > order[3], JSON.stringify(order));
  ok('A19 히어로 카드에는 다음 방문만', /다음 방문/.test(textOf(doc, '#homeSummaryCard')) &&
    /TT-261021-7302/.test(textOf(doc, '#homeSummaryNext')) &&
    !/잔여 5회/.test(textOf(doc, '#homeSummaryCard')), textOf(doc, '#homeSummaryCard').slice(0, 90));
  ok('A20 회차권 카드(잔여 5회·5회 / 8회·만료일)', /잔여 5회/.test(textOf(doc, '#homeSummaryPass')) &&
    /5회 \/ 8회/.test(textOf(doc, '#homeSummaryPass')) && /2027\.01\.27/.test(textOf(doc, '#homeSummaryPass')) &&
    /8회권/.test(textOf(doc, '#homePassCount') + textOf(doc, '#homePassRows')),
    textOf(doc, '#homeSummaryPass'));
  ok('A21 회차권 안내 문구 유지(1·4·8·12회권)', /1회권/.test(textOf(doc, '#homeSummaryPass')) &&
    /12회권/.test(textOf(doc, '#homeSummaryPass')));
  ok('A22 최근 4주 카드(방문 횟수·재평가)', /최근 4주 방문/.test(textOf(doc, '#homeSummaryReport')) &&
    /재평가/.test(textOf(doc, '#homeSummaryReport')) && /최근 4주 방문 2회/.test(textOf(doc, '#homeReportRange')),
    textOf(doc, '#homeReportRange'));
  ok('A23 회차권 카드 링크 → 보유 회차권 시트', (function () {
    click($('#homePassCard [data-summary="pass"]'));
    return $('#accountSheet').classList.contains('is-open');
  })());
  click($('#accountSheet .sheet-close, #accountSheet [data-account-close]'));
  await sleep(20);
  ok('A24 요약 전체에 금액·수수료 없음', cards.every((s) => !/\d+,\d{3}원/.test(textOf(doc, s)) && !/수수료/.test(textOf(doc, s))),
    cards.map((s) => textOf(doc, s).slice(0, 30)).join(' | '));

  /* 첫 방문 전 미리보기: 네 장 모두 접힌다 */
  ok('A25 첫 방문 전에는 요약 네 장이 모두 접힌다', (function () {
    M.setStagePreview('first');
    const hidden = cards.every((s) => $(s).hidden === true);
    const first = body.firstElementChild.id === 'homeFirstVisitCard';
    M.setStagePreview('');
    const back = cards.every((s) => $(s).hidden === false);
    return hidden && first && back;
  })(), JSON.stringify(M.homeStageState()));

  /* ── 4) 예약 3·4단계 ───────────────────────────────────────── */
  w.__ttokttokModel.startBooking ? w.__ttokttokModel.startBooking({ passId: 'p8' }) : click($('.tabbtn[data-tab="booking"]'));
  await sleep(60);
  click($('.tabbar[data-mode="customer"] .tabbtn[data-tab="booking"]'));
  await sleep(80);
  const passCards = $$('#passList .pass');
  ok('A26 회차권 카드 5장', passCards.length === 5, String(passCards.length));
  const p8 = $('#passList [data-pass="p8"]');
  ok('A27 가격 열 구조(정가 s·회당 em)', !!p8 && !!p8.querySelector('.pass-price s') &&
    !!p8.querySelector('.pass-per') && /74,000원\/회/.test(p8.querySelector('.pass-per').textContent),
    p8 && p8.querySelector('.pass-per') && p8.querySelector('.pass-per').textContent);
  ok('A28 설명에서 회당 가격을 분리(중복 없음)', !/74,000원\/회/.test(p8.querySelector('.pass-sub').textContent),
    p8.querySelector('.pass-sub').textContent);

  /* 4단계로: 필수 입력 */
  doc.querySelector('#provinceQuick [data-prov="서울"]').dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  doc.querySelector('#bookDistrict').value = '강남구';
  doc.querySelector('#bookAddress').value = '대치동 123-4, 101동 1203호';
  click(doc.querySelector('#bookSyms [data-val="뇌졸중·편마비"]'));
  click(doc.querySelector('[data-next="1"]'));
  await sleep(60);
  ok('A29 2단계로 이동(합계 바는 아직)', $('#wstep-2').classList.contains('is-active') && $('#bookTotalBar').hidden === true);
  click($('#bookDates .date-chip'));
  await sleep(40);
  click($('#bookSlots .slot:not([disabled])'));
  await sleep(40);
  click(doc.querySelector('[data-next="2"]'));
  await sleep(80);
  ok('A29b 3단계 진입(회차권을 고르면 합계 바가 뜬다)', (function () {
    const bar = $('#bookTotalBar');
    const before = bar.hidden;
    click($('#passList [data-pass="p8"]'));
    return $('#wstep-3').classList.contains('is-active') && before === true && bar.hidden === false &&
      $('#screen-booking').classList.contains('has-total');
  })(), JSON.stringify({ hidden: $('#bookTotalBar').hidden, step3: $('#wstep-3').classList.contains('is-active') }));
  await sleep(60);
  click(doc.querySelector('[data-next="3"]'));
  await sleep(80);
  ok('A30 3단계 → 4단계', $('#wstep-4').classList.contains('is-active'));
  ok('A31 4단계에서는 합계 바를 띄우지 않는다(같은 금액 두 번 방지)', $('#bookTotalBar').hidden === true &&
    !$('#screen-booking').classList.contains('has-total'));
  ok('A32 4단계 요약 표 라벨·값 구조', $$('#bookSummary .sum-line').length >= 5 &&
    /방문 지역/.test(textOf(doc, '#bookSummary')) && /서울 강남구/.test(textOf(doc, '#bookSummary')),
    textOf(doc, '#bookSummary').slice(0, 80));
  ok('A33 4단계 그룹 제목(예약자 정보)', (function () {
    const t = $('#wstep-4 .form-group-title');
    const nameField = $('#f-bookName');
    return !!t && /예약자 정보/.test(t.textContent) &&
      (t.compareDocumentPosition(nameField) & w.Node.DOCUMENT_POSITION_FOLLOWING) !== 0;
  })(), textOf(doc, '#wstep-4 .form-group-title'));
  ok('A34 이전 단계 버튼이 폼 안에 있다', (function () {
    const btn = $('#wstep-4 .prev-step');
    return !!btn && btn.getAttribute('data-back') === '4';
  })());
  click($('#wstep-4 .prev-step'));
  await sleep(50);
  ok('A35 이전 단계 버튼 → 3단계', $('#wstep-3').classList.contains('is-active') &&
    $('#bookTotalBar').hidden === false);

  /* ── 5) 관리자 표 ──────────────────────────────────────────── */
  click(doc.querySelector('[data-login="admin"]'));
  await sleep(200);
  const funnel = $('#adminMetricsFunnelRows');
  const rows = funnel ? $$('.adm-row', funnel) : [];
  ok('A36 퍼널 표 6행(단계 4 + 취소·노쇼)', rows.length === 6, String(rows.length));
  ok('A37 열 구성: 라벨·건수·비율', rows.every((r) => !!r.querySelector('.adm-k') &&
    !!r.querySelector('.adm-n') && !!r.querySelector('.adm-r')) &&
    /전체 신청/.test(rows[0].querySelector('.adm-k').textContent) &&
    /2건/.test(rows[0].querySelector('.adm-n').textContent) &&
    /100%/.test(rows[0].querySelector('.adm-r').textContent),
    rows[0] && rows[0].textContent);
  const rev = $$('.adm-row', $('#adminMetricsRevenueRows'));
  ok('A38 매출 표 값(2,340,000원·520,000원·22.2%)', /2,340,000원/.test(textOf(doc, '#adminMetricsRevenueRows')) &&
    /520,000원/.test(textOf(doc, '#adminMetricsRevenueRows')) && /22\.2%/.test(textOf(doc, '#adminMetricsRevenueRows')) &&
    rev.length === 5, String(rev.length));
  ok('A39 지역 카드 수치 칸(수요·필요·등록)', (function () {
    const reg = $('.adm-reg');
    if (!reg) return false;
    const cells = $$('.adm-reg > span', reg).map((s) => s.textContent.replace(/\s+/g, ''));
    return cells.length === 3 && cells.some((t) => /^수요/.test(t)) && cells.some((t) => /^필요/.test(t)) &&
      cells.some((t) => /^등록/.test(t));
  })(), textOf(doc, '.adm-reg'));
  ok('A40 표 숫자 우측 정렬·고정폭', /\.adm-n\{[^}]*text-align:right/.test(STYLE) &&
    /\.adm-n\{[^}]*tabular-nums/.test(STYLE) && /\.adm-row\{[^}]*grid-template-columns/.test(STYLE));
  ok('A41 KPI 6장 유지', $$('#adminMetricsKpis .settle-cell').length === 6,
    String($$('#adminMetricsKpis .settle-cell').length));

  /* ── 6) 손짓: 시트 스와이프·배지 전환 ──────────────────────── */
  const G = w.__ttokttokGesture;
  ok('A42 스와이프 가능한 시트 10개 이상', G.sheets >= 10, String(G.sheets));
  ok('A43 시작 화면(게이트) 시트는 끌어 닫지 않는다', G.has('#gateSheet') === false, JSON.stringify(G.bound.slice(0, 4)));
  ok('A44 선생님 시트에 스와이프가 붙었다', G.has('#teacherSheet') === true);
  click(doc.querySelector('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]'));
  await sleep(120);
  click(doc.querySelector('#teacherList [data-teacher]'));
  await sleep(60);
  ok('A45 스와이프 훅으로 시트 닫기', (function () {
    const open = $('#teacherSheet').classList.contains('is-open');
    const done = G.swipeClose('#teacherSheet', 140);
    return open && done && !$('#teacherSheet').classList.contains('is-open');
  })());
  ok('A46 스와이프는 닫힘 횟수를 센다', G.closes >= 1, String(G.closes));
  ok('A47 배지 전환 모션 CSS(transform·opacity만)', /\.tt-badge-swap\{animation:tt42Badge/.test(STYLE) &&
    /@keyframes tt42Badge\{0%\{opacity:\.45;transform:translateY\(3px\) scale\(\.94\)\}/.test(STYLE));
  ok('A48 동작 줄이기에서는 배지 모션 없음', /@media\(prefers-reduced-motion:reduce\)\{\.tt-badge-swap\{animation:none!important\}\}/.test(STYLE));
  ok('A49 배지 훅으로 애니메이션 클래스가 붙는다', (function () {
    const el = doc.querySelector('#adminResvQueue .status-badge') || doc.querySelector('.status-badge');
    if (!el) return false;
    G.animateBadge(el);
    return el.classList.contains('tt-badge-swap') && G.badgeSwaps >= 1;
  })());
  ok('A50 배지 감시가 예약 카드 상태를 기억한다', G.badgeCount() > 0, String(G.badgeCount()));

  /* ── 7) 큰 글자에서 시트 바닥 버튼이 세로로 ────────────────── */
  ok('A51 아주 크게: 시트 바닥 두 버튼 세로 배치 규칙', /html\[data-textsize="xl"\] \.sheet-foot > div\{flex-direction:column\}/.test(STYLE) &&
    /html\[data-textsize="xl"\] \.reject-foot\{flex-direction:column\}/.test(STYLE));

  /* ── 8) 사업 수치·정책 불변 ────────────────────────────────── */
  ok('A52 단가·수수료·정산·시드 불변', M.pricing.consumerPrice === 90000 && M.pricing.teacherPayout === 70000 &&
    M.pricing.platformFeeRate === 0.2222 && M.settlementRule.confirmDays === 3 &&
    String(M.settlementRule.payDays) === '15,end' &&
    (M.reservations() || []).some((r) => r.no === 'TT-261021-7302' && r.dateIso === '2026-11-28'));
  ok('A53 시연용 배지 문구 유지', /시연용/.test(doc.body.textContent || ''));

  /* ── 9) 예산·저장 차단 ─────────────────────────────────────── */
  ok('A54 CSS 길이 23.2만자 이하', STYLE.length <= 232000, String(STYLE.length));
  ok('A55 index.html 1.45MB 이하', Buffer.byteLength(HTML, 'utf8') <= 1450 * 1024, String(Buffer.byteLength(HTML, 'utf8')));
  const C = makeDom({ blockStorage: true });
  await waitBooted(C.window);
  ok('A56 저장 차단에서도 부팅·글자 크기 기본값', !C.errors.filter((e) => !/localStorage|SecurityError/.test(e)).length &&
    C.window.__ttokttokTextSize.current === 'md' && (C.window.__ttokttokModel.reservations() || []).length >= 1,
    C.errors.slice(0, 2));

  console.log('\nV42 RESULT: ' + pass + ' passed, ' + fails.length + ' failed');
  if (fails.length) {
    console.log('FAILURES:');
    fails.forEach((f) => console.log(' - ' + f));
  }
  process.exit(fails.length ? 1 : 0);
}

run().catch((e) => {
  console.error(e);
  process.exit(2);
});
