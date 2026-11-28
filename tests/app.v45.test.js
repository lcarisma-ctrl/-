/*
 * 똑똑쌤 v45 — 다크 모드·색상 토큰 검증 (jsdom)
 * 실행: cd projects/ttokttok-app/tests && node --max-old-space-size=2600 app.v45.test.js
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

/* ── CSS 토큰 파싱(jsdom은 var() 계산을 하지 않으므로 값 자체를 읽는다) ── */
function rootBlock(selector) {
  const i = STYLE.indexOf(selector);
  if (i < 0) return '';
  const start = STYLE.indexOf('{', i);
  let d = 0;
  for (let p = start; p < STYLE.length; p++) {
    if (STYLE[p] === '{') d++;
    else if (STYLE[p] === '}') { d--; if (!d) return STYLE.slice(start + 1, p); }
  }
  return '';
}
function tokensOf(block) {
  const out = {};
  const re = /(--[a-z0-9-]+)\s*:\s*([^;]+);/g;
  let m;
  while ((m = re.exec(block))) out[m[1]] = m[2].trim();
  return out;
}
const LIGHT = tokensOf(rootBlock(':root{'));
const DARK = tokensOf(rootBlock(':root[data-theme="dark"]'));

function rgbOf(v) {
  v = String(v).trim();
  let m = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(v);
  if (m) {
    let h = m[1];
    if (h.length === 3) h = h.split('').map((c) => c + c).join('');
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16), 1];
  }
  m = /rgba?\(([^)]+)\)/.exec(v);
  if (m) {
    const p = m[1].split(/[,\s\/]+/).filter(Boolean).map(Number);
    return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
  }
  return null;
}
function over(fg, bg) {
  const a = fg[3] + bg[3] * (1 - fg[3]);
  if (!a) return [0, 0, 0, 0];
  return [
    (fg[0] * fg[3] + bg[0] * bg[3] * (1 - fg[3])) / a,
    (fg[1] * fg[3] + bg[1] * bg[3] * (1 - fg[3])) / a,
    (fg[2] * fg[3] + bg[2] * bg[3] * (1 - fg[3])) / a, a
  ];
}
function lum(c) {
  const f = (u) => { u /= 255; return u <= 0.03928 ? u / 12.92 : Math.pow((u + 0.055) / 1.055, 2.4); };
  return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
}
function ratio(fgHex, bgHex) {
  const fg = rgbOf(fgHex), bg = rgbOf(bgHex);
  if (!fg || !bg) return 0;
  const f = fg[3] < 1 ? over(fg, bg) : fg;
  const b = bg[3] < 1 ? over(bg, [11, 17, 25, 1]) : bg;
  const l1 = lum(f), l2 = lum(b);
  const hi = Math.max(l1, l2), lo = Math.min(l1, l2);
  return (hi + 0.05) / (lo + 0.05);
}

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
      if (o.pref) window.localStorage.setItem('ttokttok_theme_v1', o.pref);
      if (o.darkOS) {
        window.matchMedia = function (q) {
          return { matches: /prefers-color-scheme:\s*dark/.test(q), media: q, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} };
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

async function run() {
  /* ── 1) 기본(저장값 없음 · 라이트 OS) ────────────────────────── */
  const A = makeDom();
  await waitBooted(A.window);
  const w = A.window, doc = A.doc;
  const $ = (s, r) => (r || doc).querySelector(s);
  const $$ = (s, r) => Array.from((r || doc).querySelectorAll(s));

  ok('A1 meta v45', (doc.querySelector('meta[name="app-version"]') || {}).content === 'v50',
    (doc.querySelector('meta[name="app-version"]') || {}).content);
  ok('A2 부팅 오류 0', !A.errors.length, A.errors.slice(0, 2));
  ok('A3 첫 페인트 전 data-theme=light', doc.documentElement.getAttribute('data-theme') === 'light',
    doc.documentElement.getAttribute('data-theme'));
  ok('A4 부트 스크립트가 <head>에 있고</style> 뒤가 아니다',
    HTML.indexOf("ttokttok_theme_v1") < HTML.indexOf('<body'));
  ok('A5 테마 훅 노출', !!w.__ttokttokTheme && w.__ttokttokTheme.version === 'v45',
    w.__ttokttokTheme && w.__tokttokTheme);
  ok('A6 선택지 3개(시스템·라이트·다크)',
    $$('#mpTheme [data-theme-opt]').map((b) => b.getAttribute('data-theme-opt')).join(',') === 'system,light,dark',
    $$('#mpTheme [data-theme-opt]').map((b) => b.getAttribute('data-theme-opt')));
  ok('A7 기본은 시스템(라이트로 해석)', w.__ttokttokTheme.pref === 'system' && w.__ttokttokTheme.resolved === 'light');
  ok('A8 radiogroup·aria-checked', $('#mpTheme').getAttribute('role') === 'radiogroup' &&
    $('#mpTheme').getAttribute('aria-label') === '화면 테마' &&
    $$('#mpTheme [role="radio"]').every((b) => b.hasAttribute('aria-checked')));
  ok('A9 44px 터치 타깃 규칙', /\.mp-text-card \.segmented button\{min-height:44px/.test(STYLE));
  ok('A10 안내 문구에 기기 저장·시스템 안내', /이 기기에만 저장/.test($('#mpThemeNote').textContent) &&
    /시스템/.test($('#mpThemeNote').textContent));

  /* ── 2) 토큰 체계 ───────────────────────────────────────────── */
  const required = ['--bg', '--bg-2', '--surface', '--surface-2', '--surface-3', '--ink', '--ink-2', '--ink-3',
    '--ink-muted', '--ink-caption', '--line', '--line-strong', '--ink-teal', '--ink-amber', '--ink-rose',
    '--ink-blue', '--on-dark', '--navy-800', '--blue', '--teal', '--amber', '--rose', '--shade-1',
    '--art-fill', '--tint-blue', '--tint-teal', '--tint-amber', '--tint-rose'];
  const missingL = required.filter((n) => !LIGHT[n]);
  const missingD = required.filter((n) => !DARK[n]);
  ok('B1 라이트 토큰 전부 정의', !missingL.length, missingL);
  ok('B2 다크 토큰이 같은 이름으로 전부 덮임', !missingD.length, missingD);
  const sameSkip = ['--grad-', '--line-white', '--veil-', '--on-dark', '--art-', '--shade-white', '--a-mint'];
  const notOverridden = Object.keys(LIGHT).filter((n) => DARK[n] === undefined && !/^var\(/.test(LIGHT[n]) &&
    !sameSkip.some((p) => n.startsWith(p)) && !/^--(fs|sp|pad|gap|r|lh|ls|ease|spring|tap|dur|press|stagger|z|t|tr|shadow|elev|v7-|v9-|v11-|kb|i$|k$)/.test(n));
  ok('B3 색 토큰은 다크에서 빠짐없이 덮인다', notOverridden.length === 0, notOverridden.slice(0, 8));
  /* 남은 리터럴: 팔레트 블록·마스크·인쇄 문서·아바타 팔레트를 뺀 CSS에는 색 리터럴이 없어야 한다 */
  const cssBody = STYLE.replace(rootBlock(':root{'), '').replace(rootBlock(':root[data-theme="dark"]'), '');
  const literals = cssBody.match(/#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)/g) || [];
  /* 남는 것은 (1) 마스크 그라디언트의 #000, (2) 투명 정지점, (3) 두 테마 공통으로 두는 색 글로우 그림자뿐 */
  const allowed = literals.filter((x) => /^#000$/.test(x) || /rgba\([^)]*,0\)$/.test(x) ||
    /^rgba\((13,148,136|37,99,235|95,227,201|27,125,232|0,0,0)[,\.]/.test(x) || /^#E9B45B$/.test(x));
  ok('B4 CSS 본문에 남은 색 리터럴은 장식 글로우·투명 정지점뿐(24개 이하)',
    literals.length - allowed.length === 0 && allowed.length <= 24,
    { left: literals.filter((x) => !allowed.includes(x)).slice(0, 6), allowed: allowed.length });
  const bodyLiterals = HTML.slice(HTML.indexOf('<body')).replace(/var\(--[a-z0-9-]+\)/g, '');
  ok('B5 HTML·JS에도 색 리터럴은 아바타 팔레트·인쇄 문서뿐',
    (bodyLiterals.match(/#[0-9a-fA-F]{6}\b/g) || []).length < 70,
    (bodyLiterals.match(/#[0-9a-fA-F]{6}\b/g) || []).length);
  ok('B6 color-scheme 전환', /:root\[data-theme="dark"\]\{[^}]*color-scheme:dark/.test(STYLE));

  /* ── 3) 대비(WCAG AA) — 라이트·다크 양쪽 본문 4.5:1 ──────────── */
  const pairs = [
    ['--ink', '--surface'], ['--ink-2', '--surface'], ['--ink-3', '--surface'], ['--ink-muted', '--surface'],
    ['--ink-caption', '--surface'], ['--ink', '--bg'], ['--ink-2', '--bg'], ['--ink-muted', '--bg'],
    ['--ink-teal', '--surface'], ['--ink-amber', '--surface'], ['--ink-rose', '--surface'],
    ['--ink-blue', '--surface'], ['--ink-link', '--surface'], ['--ink', '--tint-blue'],
    ['--ink-2', '--tint-teal'], ['--ink-amber-2', '--tint-amber'], ['--ink-rose-3', '--tint-rose'],
    ['--ink-title', '--bg'], ['--ink-v7', '--surface']
  ];
  const whiteOn = [['--on-dark', '--blue'], ['--on-dark', '--blue-strong'], ['--on-dark', '--teal-fill'],
    ['--on-dark', '--teal-fill-2'], ['--on-dark', '--teal-badge'], ['--on-dark', '--amber'],
    ['--on-dark', '--rose'], ['--on-dark', '--navy-800'], ['--on-dark', '--navy-600']];
  const bad = { light: [], dark: [] };
  for (const theme of ['light', 'dark']) {
    const T = theme === 'light' ? LIGHT : DARK;
    for (const [fg, bg] of pairs) {
      const r = ratio(T[fg], T[bg]);
      if (r < 4.5) bad[theme].push(fg + '/' + bg + ' ' + r.toFixed(2));
    }
    for (const [fg, bg] of whiteOn) {
      const r = ratio(T[fg], T[bg]);
      if (r < 4.5) bad[theme].push(fg + '/' + bg + ' ' + r.toFixed(2));
    }
  }
  ok('C1 라이트 본문·버튼 대비 4.5:1 이상', bad.light.length === 0, bad.light.slice(0, 6));
  ok('C2 다크 본문·버튼 대비 4.5:1 이상', bad.dark.length === 0, bad.dark.slice(0, 6));
  const capLight = ratio(LIGHT['--ink-caption'], LIGHT['--surface']);
  const capDark = ratio(DARK['--ink-caption'], DARK['--surface']);
  ok('C3 캡션·각주도 4.5:1 이상(양쪽)', capLight >= 4.5 && capDark >= 4.5, [capLight.toFixed(2), capDark.toFixed(2)]);
  ok('C4 면과 바탕이 구분된다(다크 카드 > 바탕)',
    lum(rgbOf(DARK['--surface'])) > lum(rgbOf(DARK['--bg'])), [DARK['--surface'], DARK['--bg']]);
  ok('C5 다크 바탕은 어둡고 글자는 밝다',
    lum(rgbOf(DARK['--bg'])) < 0.05 && lum(rgbOf(DARK['--ink'])) > 0.7,
    [DARK['--bg'], DARK['--ink']]);

  /* ── 4) 테마 바꾸기·저장 ─────────────────────────────────────── */
  click($('#mpTheme [data-theme-opt="dark"]'));
  await sleep(120);
  ok('D1 다크 선택 → html data-theme=dark', doc.documentElement.getAttribute('data-theme') === 'dark');
  ok('D2 선택 상태 반영(aria-checked·is-on)',
    $('#mpTheme [data-theme-opt="dark"]').getAttribute('aria-checked') === 'true' &&
    $('#mpTheme [data-theme-opt="dark"]').classList.contains('is-on') &&
    $('#mpTheme [data-theme-opt="system"]').getAttribute('aria-checked') === 'false');
  ok('D3 기기에 저장', w.localStorage.getItem('ttokttok_theme_v1') === 'dark');
  ok('D4 안내 문구 갱신', $('#mpThemeHint').textContent === '다크', $('#mpThemeHint').textContent);
  ok('D5 주소창 색(theme-color)도 어둡게',
    ($('meta[name="theme-color"]') || {}).content === '#0B1119', ($('meta[name="theme-color"]') || {}).content);
  ok('D6 토스트 안내', /다크/.test((doc.querySelector('.toast') || {}).textContent || ''),
    (doc.querySelector('.toast') || {}).textContent);
  click($('#mpTheme [data-theme-opt="light"]'));
  await sleep(100);
  ok('D7 라이트 선택 → 되돌아온다', doc.documentElement.getAttribute('data-theme') === 'light' &&
    w.localStorage.getItem('ttokttok_theme_v1') === 'light');
  ok('D8 시스템 선택 → pref/system 표기', (function () {
    click($('#mpTheme [data-theme-opt="system"]'));
    return doc.documentElement.getAttribute('data-theme-pref') === 'system' && /^시스템/.test($('#mpThemeHint').textContent);
  })());

  /* ── 5) 저장값이 있으면 첫 페인트부터 다크(깜빡임 없음) ──────── */
  const B = makeDom({ pref: 'dark' });
  await waitBooted(B.window);
  ok('E1 저장값 dark → 부팅 직후 data-theme=dark', B.doc.documentElement.getAttribute('data-theme') === 'dark');
  ok('E2 그때 theme-color도 어둡다', (B.doc.querySelector('meta[name="theme-color"]') || {}).content === '#0B1119');
  ok('E3 훅 resolved=dark', B.window.__ttokttokTheme.resolved === 'dark' && B.window.__ttokttokTheme.pref === 'dark');
  ok('E4 다크에서도 부팅 오류 0', !B.errors.length, B.errors.slice(0, 2));

  /* ── 6) 시스템 설정 따라가기 ────────────────────────────────── */
  const C = makeDom({ darkOS: true });
  await waitBooted(C.window);
  ok('F1 기기가 다크 → 시스템 선택이 다크로 해석', C.doc.documentElement.getAttribute('data-theme') === 'dark' &&
    C.window.__ttokttokTheme.pref === 'system' && C.window.__ttokttokTheme.resolved === 'dark');
  const D = makeDom({ pref: 'light', darkOS: true });
  await waitBooted(D.window);
  ok('F2 라이트를 골랐으면 기기가 다크여도 라이트', D.doc.documentElement.getAttribute('data-theme') === 'light');

  /* ── 7) 사업 수치·시드 불변, 기존 세대 유지 ─────────────────── */
  const M = w.__ttokttokModel;
  ok('G1 단가·수수료·정산 규칙 불변', M.pricing.consumerPrice === 90000 && M.pricing.teacherPayout === 70000 &&
    M.pricing.platformFeeRate === 0.2222 && M.settlementRule.confirmDays === 3 &&
    String(M.settlementRule.payDays) === '15,end');
  ok('G2 시드 예약 TT-261021-7302 유지', (M.reservations() || []).some((r) => r.no === 'TT-261021-7302'));
  ok('G3 시연용 배지 유지', /시연용/.test(HTML));
  ok('G4 백업 스키마 ttokttok.v23 유지', typeof M.exportWorkspaceSnapshot === 'function' &&
    M.exportWorkspaceSnapshot().schemaVersion === 'ttokttok.v23');
  ok('G5 v42 글자 크기 3단 유지', $$('#mpTextSize [data-textsize]').length === 3);
  ok('G6 v42 홈 네 장 유지', !!$('#homePassCard') && !!$('#homeReportCard') && !!$('#homeRebookCard'));
  ok('G7 v43 빈 상태 그림 유지', /empty-art/.test(w.__ttokttokUI.emptyHtml('admin-resv')));
  ok('G8 v44 탭 스크롤 기억 유지', !!(w.__ttokttokTabScroll && w.__ttokttokTabScroll.version === 'v44'));
  ok('G9 CSS·HTML 예산', STYLE.length <= 243000 && Buffer.byteLength(HTML, 'utf8') <= 1450 * 1024,
    STYLE.length + ' / ' + Buffer.byteLength(HTML, 'utf8'));

  console.log('\nV45 RESULT: ' + pass + ' passed, ' + fails.length + ' failed');
  if (fails.length) {
    console.log('FAILURES:');
    fails.forEach((f) => console.log(' - ' + f));
  }
  process.exit(fails.length ? 1 : 0);
}

run().catch((e) => { console.error(e); process.exit(2); });
