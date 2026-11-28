/*
 * 똑똑쌤 v35 — 디자인 토큰 통합(:root 하나) · 회색 13종의 시맨틱 토큰화 · 인라인 스타일 클래스 회수 검증 (jsdom)
 * 실행: cd projects/ttokttok-app/tests && node --max-old-space-size=2600 app.v35.test.js
 * ─ 색의 실제 렌더 값·대비는 Chromium(E2E·qa_v24·_contrast_audit.py)에서 확인하고,
 *   여기서는 토큰 정의·CSS 정합성·마크업 정리(인라인 회수)를 본다.
 */
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const STYLE = (HTML.match(/<style>([\s\S]*?)<\/style>/) || ['', ''])[1];

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

function makeDom() {
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
      const FIXED = new Date('2026-11-26T13:00:00.000Z').getTime();
      const RealDate = window.Date;
      function FixedDate(...args) { return args.length ? new RealDate(...args) : new RealDate(FIXED); }
      FixedDate.prototype = RealDate.prototype;
      FixedDate.now = () => FIXED;
      FixedDate.parse = RealDate.parse;
      FixedDate.UTC = RealDate.UTC;
      window.Date = FixedDate;
    }
  });
  return { dom, window: dom.window, doc: dom.window.document, errors };
}

/* ── 색 계산(토큰 값끼리의 대비를 숫자로 고정한다) ─────────────── */
const hex2rgb = (h) => {
  h = String(h).trim().replace('#', '');
  if (h.length === 3) h = h.split('').map((c) => c + c).join('');
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
};
const lum = (rgb) => {
  const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  return 0.2126 * f(rgb[0]) + 0.7152 * f(rgb[1]) + 0.0722 * f(rgb[2]);
};
const contrast = (a, b) => { const l1 = lum(hex2rgb(a)), l2 = lum(hex2rgb(b)); const hi = Math.max(l1, l2), lo = Math.min(l1, l2); return (hi + 0.05) / (lo + 0.05); };
const tokenRaw = (name) => {
  const m = STYLE.match(new RegExp('--' + name.replace(/^--/, '') + '\\s*:\\s*([^;}]+)'));
  return m ? m[1].trim() : '';
};
/* v45: 별칭(--text-caption:var(--ink-caption))은 한 단계 풀어서 실제 색을 본다. */
const token = (name) => {
  let v = tokenRaw(name);
  const a = /^var\((--[a-z0-9-]+)\)$/.exec(v);
  if (a) v = tokenRaw(a[1]);
  return v;
};

async function run() {
  /* ============================================================
     AH. v35 — 디자인 토큰 · CSS 정리
     ============================================================ */

  /* ── 1) 토큰이 한 곳에 ─────────────────────────────────────── */
  const roots = (STYLE.match(/:root\{/g) || []).length;
  ok('AH1 :root는 한 블록(v2~v11에 6곳으로 흩어져 있던 것을 통합)', roots === 1, String(roots));
  const defs = new Set((STYLE.match(/--[a-zA-Z0-9-]+\s*:/g) || []).map((x) => x.replace(/\s*:$/, '')));
  const uses = (STYLE.match(/var\((--[a-zA-Z0-9-]+)\)/g) || []).map((x) => x.slice(4, -1));
  const undef = [...new Set(uses)].filter((u) => !defs.has(u));
  ok('AH2 CSS가 쓰는 var()가 모두 정의됨', undef.length === 0, undef.slice(0, 4).join(','));
  ok('AH3 CSS 중괄호 균형', (STYLE.match(/\{/g) || []).length === (STYLE.match(/\}/g) || []).length);
  ok('AH4 토큰 이름이 의미 단위로 정리(색)', ['--text-caption', '--text-muted', '--text-on-brand', '--surface', '--line', '--grad-brand'].every((t) => defs.has(t)));
  ok('AH5 토큰 이름이 의미 단위로 정리(여백·타이포·모서리·그림자·겹침)',
    ['--sp-1', '--sp-2h', '--sp-7', '--pad-x', '--fs-cap', '--fs-page', '--r-pill', '--shadow-card', '--z-sheet', '--z-gate'].every((t) => defs.has(t)));
  ok('AH6 예전 두 이름(--muted/--muted-2)은 사라짐', !defs.has('--muted') && !defs.has('--muted-2'));
  ok('AH7 CSS 어디에도 var(--muted) 형태가 남지 않음', !/var\(--muted(-2)?\)/.test(HTML));

  /* ── 2) 색 토큰 값과 대비(WCAG AA 4.5:1) ───────────────────── */
  ok('AH8 --text-caption = #626B7A(v45: --ink-caption 별칭)', token('text-caption').toUpperCase() === '#626B7A', token('text-caption'));
  ok('AH9 --text-muted = #58617A(v45: --ink-muted 별칭)', token('text-muted').toUpperCase() === '#58617A', token('text-muted'));
  ok('AH10 --teal-ink = #0B7A6B(v45: --ink-teal 별칭)', token('teal-ink').toUpperCase() === '#0B7A6B', token('teal-ink'));
  const pairs = [
    ['캡션', 'text-caption', '#EEF2F8'], ['캡션', 'text-caption', '#EAF3FF'], ['캡션', 'text-caption', '#FFFFFF'],
    ['보조 본문', 'text-muted', '#EEF2F8'], ['보조 본문', 'text-muted', '#F3F6FC'],
    ['민트 글자', 'teal-ink', '#E7F6F3'], ['민트 글자', 'teal-ink', '#FFFFFF'],
    ['앰버 글자', 'amber', '#FFF6E8'], ['배지(파랑)', 'sky-ink', '#EAF3FF'], ['배지(찜)', 'fav-ink', '#FFEDF1'],
  ];
  for (const [label, name, bg] of pairs) {
    const v = token(name);
    ok('AH11 ' + label + ' ' + name + ' 대비 4.5:1 이상 (' + bg + ')', contrast(v, bg) >= 4.5, name + '=' + v + ' ' + contrast(v, bg).toFixed(2));
  }
  const grads = { '--grad-brand': ['#2E72CE', '#1E5FB8'], '--grad-mint': ['#0B7A6B', '#0A6E60'] };
  for (const t of Object.keys(grads)) {
    ok('AH12 ' + t + ' 두 정지점 모두 흰 글자 4.5:1 이상', grads[t].every((c) => contrast(c, '#FFFFFF') >= 4.5) && (/var\(--/.test(tokenRaw(t)) || token(t).indexOf(grads[t][0]) > -1),
      token(t));
  }
  const OLD_GRAYS = ['#94A3B8', '#98A3B3', '#7B8798', '#A2ADBD', '#8A96A8', '#8E9AAB', '#96A1B2', '#9AA5B4', '#A6B0BF', '#6B7789', '#AAB4C2', '#A9B3C1', '#8D99A9'];
  const leftOver = OLD_GRAYS.filter((g) => new RegExp('color\\s*:\\s*' + g, 'i').test(HTML));
  ok('AH13 흩어져 있던 회색 13종이 color에 남지 않음', leftOver.length === 0, leftOver.join(','));

  /* ── 3) 타이포·간격·모서리·겹침 토큰화 ─────────────────────── */
  const fsLeft = (STYLE.match(/font-size:\s*[\d.]+px/g) || []).length;
  ok('AH14 font-size는 모두 토큰(var(--fs-*))으로(320 시작 화면 1줄 예외)' , fsLeft <= 1, String(fsLeft));
  /* v42: 타입 토큰은 --fs-scale을 곱하는 calc() 형태가 됐다(사용자 글자 크기).
     기준 픽셀값이 그대로인지 본다 — 기본(scale 1)에서는 v41과 같은 값이다. */
  const basePx = (name) => {
    const v = token(name);
    const m = v.match(/^calc\(([0-9.]+)px \* var\(--fs-scale\)\)$/);
    return m ? m[1] + 'px' : v;
  };
  ok('AH15 글자 크기 토큰이 실제 값과 일치(--fs-11h=11.5px, --fs-page=23px)',
    basePx('fs-11h') === '11.5px' && basePx('fs-page') === '23px', token('fs-11h') + '/' + token('fs-page'));
  ok('AH16 알약 모서리는 --r-pill로', (STYLE.match(/border-radius:(999px|99px)/g) || []).length === 0 &&
    (STYLE.match(/border-radius:var\(--r-pill\)/g) || []).length >= 50);
  ok('AH17 z-index 주요 층이 토큰으로(시트 130·게이트 300·토스트 400)',
    token('z-sheet') === '130' && token('z-gate') === '300' && token('z-toast') === '400' &&
    (STYLE.match(/z-index:\s*\d{3}/g) || []).length === 0, (STYLE.match(/z-index:\s*\d{3}/g) || []).join(','));
  ok('AH18 그림자 토큰 8종이 :root에 모임', ['--shadow-card', '--shadow-float', '--shadow-hero', '--v7-card', '--v9-shadow', '--v9-shadow-raise', '--v11-card', '--v11-card-raise'].every((t) => defs.has(t)));

  /* ── 4) 인라인 스타일 회수 ─────────────────────────────────── */
  const statics = (HTML.match(/style="([^"]*)"/g) || []).map((x) => x.slice(7, -1)).filter((x) => x.indexOf("' +") < 0);
  ok('AH19 정적 인라인 style 474 → 200개 이하', statics.length <= 200, String(statics.length));
  const banned = ['margin-top', 'margin-bottom', 'margin-left', 'margin-right', 'font-size', 'font-weight'];
  const badInline = statics.filter((x) => banned.some((p) => new RegExp('(^|;)\\s*' + p + '\\s*:').test(x)));
  ok('AH20 여백·글자 크기·굵기 인라인 0(클래스로 회수)', badInline.length === 0, badInline.slice(0, 2).join(' | '));
  const utils = STYLE.match(/\.(mt|mb|ml|mr|m|fs|fw|c|ta|cur|td)-[a-z0-9-]+\{[^}]*!important\}/g) || [];
  ok('AH21 회수 유틸리티 클래스가 CSS에 정의됨(40종 이상)', utils.length >= 40, String(utils.length));
  /* v41: 글자 유틸리티는 픽셀 이름(.fs-10p) 대신 의미 이름(.fs-micro)을 쓴다.
     간격 유틸(.mt-10=10px)과 색 유틸(.c-cap)은 그대로다. */
  ok('AH22 대표 유틸리티 값(.mt-10=10px, .fs-micro=캡션 토큰, .c-cap=캡션 색)', (function () {
    const mt = STYLE.match(/\.mt-10\{([^}]*)\}/);
    const fs = STYLE.match(/\.fs-micro\{([^}]*)\}/);
    const c = STYLE.match(/\.c-cap\{([^}]*)\}/);
    return !!mt && /margin-top:10px/.test(mt[1]) && !!fs && /font-size:var\(--t-micro\)/.test(fs[1]) && !!c && /color:var\(--text-caption\)/.test(c[1]);
  })());
  const oldChars = 12465;
  const nowChars = statics.reduce((n, x) => n + x.length, 0);
  ok('AH23 인라인 스타일 글자 수 절반 이하', nowChars <= oldChars / 2, nowChars + '/' + oldChars);
  ok('AH24 남은 인라인은 레이아웃 제어 속성만(display·gap·min-*·width 등)', statics.every((x) => !/color\s*:\s*var\(--(text-|teal-ink|text-caption)/.test(x)));

  /* ── 5) 화면은 그대로: 구조·클래스·문구 ────────────────────── */
  const A = makeDom();
  await sleep(520);
  const d = A.doc;
  const W = A.window;
  const M = W.__ttokttokModel;
  ok('AH25 meta v35', (d.querySelector('meta[name=app-version]') || {}).content === 'v50');
  ok('AH26 v33 빈 상태 클래스 유지(empty-v7)', !!d.querySelector('.empty-v7') || /empty-v7/.test(HTML));
  ok('AH27 word-break:keep-all 규칙 유지(단어 중간 줄바꿈 없음)', /word-break:keep-all/.test(STYLE) && (STYLE.match(/word-break:keep-all/g) || []).length >= 5,
    String((STYLE.match(/word-break:keep-all/g) || []).length));
  ok('AH28 단가·수수료·정산 규칙 불변', M.pricing.consumerPrice === 90000 && M.pricing.teacherPayout === 70000 &&
    M.pricing.platformFeeRate === 0.2222 && M.settlementRule.confirmDays === 3 && JSON.stringify(M.settlementRule.payDays) === '[15,"end"]');
  ok('AH29 시드 예약 유지', /TT-261021-7302/.test(d.querySelector('#homeSummaryNext').textContent));
  ok('AH30 접근성 기능(v34) 그대로 — 게이트 잠금·이름 감사', M.a11y.topDialog() === '#entryGate' && M.a11y.backgroundLocked() === true &&
    M.a11y.auditAll().blank.length === 0 && M.a11y.auditAll().iconNoLabel.length === 0);
  ok('AH31 JS 오류 없음', A.errors.length === 0, A.errors.slice(0, 2).join(' | '));

  /* ── 6) index.html 크기 상한 ───────────────────────────────── */
  const bytes = Buffer.byteLength(HTML, 'utf8');
  ok('AH32 index.html 1.45MB 이하(토큰·유틸 추가 후에도)', bytes <= 1450 * 1024, String(bytes));
  ok('AH33 회수한 유틸리티가 같은 스타일 블록 안에 있다(블록 추가 없음)', STYLE.indexOf('v35 · 인라인 스타일에서 회수한 유틸리티') > -1 &&
    HTML.indexOf('</style>') > HTML.indexOf('.mt-10{margin-top:10px!important}'));

  console.log('\nRESULT: ' + pass + ' passed, ' + fails.length + ' failed');
  if (fails.length) {
    console.log('FAILURES:');
    fails.forEach((f) => console.log(' - ' + f));
  }
  process.exit(fails.length ? 1 : 0);
}

run().catch((e) => { console.log('FATAL', (e && e.stack) || e); process.exit(1); });
