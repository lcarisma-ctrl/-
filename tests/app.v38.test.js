/*
 * 똑똑쌤 v38 — 문구 다듬기·용어 통일 검증 (jsdom)
 * 실행: cd projects/ttokttok-app/tests && node --max-old-space-size=2600 app.v38.test.js
 * ─ 이 파일은 '말'을 본다. 화면의 이름이 표준(GLOSSARY.md)과 같은지, 금지어가 남았는지,
 *   말투(해요체/합니다체)가 자리별로 지켜지는지, 고정 수치가 흔들리지 않았는지.
 * ─ 픽셀·레이아웃은 Chromium(E2E v38 · qa_v24)이 본다.
 */
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const GLOSSARY = fs.readFileSync(path.join(__dirname, '..', 'GLOSSARY.md'), 'utf8');
const STYLE = (HTML.match(/<style>([\s\S]*?)<\/style>/) || ['', ''])[1];
const FIXED_NOW = new Date('2026-11-26T13:00:00.000Z').getTime();

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
const cleanText = (doc) => {
  const clone = doc.body.cloneNode(true);
  [].forEach.call(clone.querySelectorAll('script,style,noscript,svg'), (el) => el.remove());
  return String(clone.textContent || '').replace(/\s+/g, ' ');
};
const textOf = (doc, sel) => {
  const el = doc.querySelector(sel);
  return el ? String(el.textContent || '').replace(/\s+/g, ' ') : '';
};

/* FAQ·약관 원문은 화면 밖 데이터라 HTML에서 바로 읽는다(렌더 결과와 같은 원천). */
const FAQ_BLOCK = HTML.slice(HTML.indexOf('var FAQ_ITEMS = ['), HTML.indexOf('var TERMS_DOCS'));
const FAQ_QA = (FAQ_BLOCK.match(/(?:q|a):\s*'([^']*)'/g) || [])
  .map((s) => s.replace(/^\w+:\s*'/, '').replace(/'$/, ''));
const TERMS_BLOCK = HTML.slice(HTML.indexOf('var TERMS_DOCS'), HTML.indexOf('var faqOpenId'));
const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

async function run() {
  const { window, doc, errors } = makeDom();
  await sleep(80);
  const M = window.__ttokttokModel;
  const C = window.__ttokttokCopy;

  /* ============================================================
     1) 표준이 코드에 있다 — 버전·용어·금지어·검사기
     ============================================================ */
  ok('DA0 v38 부트 JS 오류 0', errors.length === 0, errors.slice(0, 3).join(' | '));
  ok('DA1 meta v38 · copyVersion v38', doc.querySelector('meta[name="app-version"]').content === 'v49' &&
    M.copyVersion === 'v38' && C && C.version === 'v38');
  ok('DA2 검사 훅 노출(audit·visibleText·toneOf)', typeof C.audit === 'function' &&
    typeof C.visibleText === 'function' && typeof C.toneOf === 'function');
  ok('DA3 역할·상품 표준값', M.copyTerms.guardian === '보호자' && M.copyTerms.teacher === '선생님' &&
    M.copyTerms.operator === '관리자' && M.copyTerms.pass === '회차권' && M.copyTerms.round === '회차' &&
    M.copyTerms.journal === '방문 일지' && M.copyTerms.demo === '시연용', JSON.stringify(M.copyTerms));
  ok('DA4 정산 표기 표준 문장', M.copyTerms.settlement === '회차 완료 D+3 정산 확정 · 월 2회(15일·말일) 지급', M.copyTerms.settlement);
  ok('DA5 금지어 9종과 대체어', M.copyBanned.length === 9 &&
    M.copyBanned.every((x) => x.term && x.use) &&
    ['이용권', '회기', '방문권', '파트너', '고객 모드', '회복 일지', '프로토타입', '데모', 'DEMO']
      .every((w) => M.copyBanned.some((x) => x.term === w)), JSON.stringify(M.copyBanned));
  ok('DA6 auditCopy가 자리·문맥과 함께 잡는다', (function () {
    const hit = M.auditCopy('결제한 이용권은 내 정보에 저장됩니다.');
    return hit.length === 1 && hit[0].term === '이용권' && hit[0].use === '회차권' &&
      /이용권/.test(hit[0].context) && typeof hit[0].at === 'number';
  })(), JSON.stringify(M.auditCopy('결제한 이용권은 저장됩니다.')));
  ok('DA7 auditCopy 빈 값·정상 문구는 통과', M.auditCopy('').length === 0 && M.auditCopy(null).length === 0 &&
    M.auditCopy('보호자가 회차권을 골랐어요. 선생님이 방문해요.').length === 0);
  ok('DA8 고객센터는 허용(금지어는 고객 모드)', M.auditCopy('현금영수증은 고객센터로 문의해 주세요.').length === 0);
  ok('DA9 copyToneOf — 섞인 문단을 잡는다', (function () {
    const bad = M.copyToneOf('이 화면은 미리보기입니다. 외부로 발송되지 않아요.');
    const good = M.copyToneOf('이 화면은 미리보기예요. 외부로 발송되지 않아요.');
    return bad.mixed === true && good.mixed === false && good.polite > 0;
  })());

  /* ============================================================
     2) 용어 사전(GLOSSARY.md)과 코드가 같은 말을 쓴다
     ============================================================ */
  ok('DB1 GLOSSARY.md 존재·분량', GLOSSARY.length > 6000, String(GLOSSARY.length));
  ok('DB2 사전에 표준값이 모두 적혀 있다', ['보호자', '선생님', '관리자', '회차권', '회차', '방문 일지', '시연용']
    .every((w) => GLOSSARY.includes(w)));
  ok('DB3 사전의 정산 표기 = 코드', GLOSSARY.includes(M.copyTerms.settlement));
  ok('DB4 금지어와 대체어가 사전에 있다', (function () {
    const bannedDoc = GLOSSARY.slice(GLOSSARY.indexOf('## 2.'), GLOSSARY.indexOf('## 3.'));
    return M.copyBanned.every((x) => bannedDoc.includes(x.term) && bannedDoc.includes(x.use));
  })());
  ok('DB5 사전에 화면별 말투 규칙·고정 수치·banned 목록', /해요체/.test(GLOSSARY) && /합니다체/.test(GLOSSARY) &&
    /90,000원/.test(GLOSSARY) && /22\.2%/.test(GLOSSARY) && /D\+3/.test(GLOSSARY) &&
    /TT-261021-7302/.test(GLOSSARY));

  /* ============================================================
     3) 화면 이름 — 보호자·선생님·관리자
     ============================================================ */
  ok('DC1 역할 표시 "보호자 모드"', textOf(doc, '#rolePill') === '보호자 모드', textOf(doc, '#rolePill'));
  ok('DC2 모드 전환 시트 — 보호자 모드로 계속', /보호자 모드로 계속 이용하기/.test(textOf(doc, '#roleSheet')) &&
    /선생님 모드로 전환/.test(textOf(doc, '#roleSheet')));
  ok('DC3 모드 전환 시트에 개발 용어 없음(DEMO 배지 → 시연용)', !/DEMO/.test(textOf(doc, '#roleSheet')) &&
    /시연용/.test(textOf(doc, '#roleSheet')), textOf(doc, '#roleSheet').slice(0, 80));
  ok('DC4 선생님 탭 라벨·화면 제목', textOf(doc, '[data-tab="tp-home"]').trim() === '선생님 홈' &&
    textOf(doc, '#screen-tp-home h1') === '선생님 홈' && textOf(doc, '#screen-tp-mypage h1') === '선생님 내 정보');
  ok('DC5 심사 카드 제목 "선생님 심사 상태"', (doc.body.textContent.match(/선생님 심사 상태/g) || []).length >= 1 &&
    !/파트너 심사 상태/.test(doc.body.textContent));
  ok('DC6 지원 화면 — "선생님 지원하기"·"선생님 이용약관"', /선생님 지원하기/.test(textOf(doc, '#screen-partner')) &&
    /선생님 이용약관/.test(cleanText(doc)) && !/파트너/.test(cleanText(doc)));
  ok('DC7 게이트 역할 버튼 — 보호자', /보호자/.test(textOf(doc, '.gate-roles')) &&
    /보호자·선생님·관리자\(시연용\) 화면은/.test(doc.body.textContent));

  /* ============================================================
     4) 상품·회차 — 회차권·1·4·8·12회권
     ============================================================ */
  const passNames = [].map.call(doc.querySelectorAll('#passList .pass'), (el) => {
    const n = el.querySelector('.pass-name');
    return n ? String(n.textContent || '').replace(/(11%|18%|22%) 할인/, '').trim() : '';
  });
  ok('DD1 예약 3단계 이름 "회차권 선택"', /<p class="wstep-title">회차권 선택<\/p>/.test(HTML) &&
    /<b>회차권 선택 후 시작<\/b>/.test(HTML));
  ok('DD2 상품 5종 이름 — 평가권·1·4·8·12회권', (function () {
    const plans = M.pricing.plans.map((p) => p.name);
    return plans[0] === '첫 1:1 방문 평가권' && plans.slice(1).join('|') === '1회권|4회권|8회권|12회권';
  })(), JSON.stringify(M.pricing.plans.map((p) => p.name)));
  ok('DD3 상품 가격 불변(0/90,000/320,000/592,000/840,000)', (function () {
    const p = M.pricing.plans;
    return p[0].price === 0 && p[1].price === 90000 && p[2].price === 320000 && p[3].price === 592000 && p[4].price === 840000;
  })());
  ok('DD4 예약 화면 카드에도 같은 이름', passNames.length === 5 && passNames.slice(1).join('|') === '1회권|4회권|8회권|12회권',
    JSON.stringify(passNames));
  ok('DD5 내 예약 시트 — "내 예약 · 회차권"·"보유 회차권"', /내 예약 · 회차권/.test(textOf(doc, '#accountSheet')) &&
    /보유 회차권/.test(textOf(doc, '#accountSheet')));
  ok('DD6 내 정보 메뉴 — "회차권 5회 남음"', /회차권 5회 남음/.test(textOf(doc, '#screen-mypage')));
  ok('DD7 일지 진행 "전체 12회차 중 5회차"', /전체 12회차 중 5회차 진행/.test(cleanText(doc)) &&
    !/회기/.test(cleanText(doc)));
  ok('DD8 회복 추이 라벨도 회차(누적·전체·최근 5회차)', /<span>누적 회차<\/span>/.test(HTML) &&
    /최근 5회차 · /.test(HTML) && /회복 추이 \(최근 5회차\)/.test(HTML));
  ok('DD9 시드 회차권 이름 "8회권"', /8회권/.test(cleanText(doc)) && !/방문권/.test(cleanText(doc)));

  /* ============================================================
     5) 화면 전체 문구 — 금지어 0
     ============================================================ */
  const bodyText = cleanText(doc);
  const hits = M.auditCopy(bodyText);
  ok('DE1 화면 전체(숨은 시트 포함) 금지어 0', hits.length === 0,
    hits.slice(0, 4).map((x) => x.term + '@' + x.context).join(' | '));
  ok('DE2 보이는 화면 금지어 0', C.audit(C.visibleText()).length === 0,
    C.audit(C.visibleText()).slice(0, 3).map((x) => x.term).join(','));
  ok('DE3 이 기기 저장 고지 유지', /이 기기에만 저장 · 서버 미연결\(이 브라우저에만 반영\)/.test(bodyText));
  ok('DE4 시연용 고지 3곳 이상', (bodyText.match(/시연용/g) || []).length >= 3,
    String((bodyText.match(/시연용/g) || []).length));
  ok('DE5 과장 문구 제거 — "증상으로 바로 찾기"', /증상으로 바로 찾기/.test(bodyText) && !/누르면 바로 매칭/.test(bodyText));
  ok('DE6 운영 지표 용어 — 예약 진행 단계·매칭 대기 시간', /예약 진행 단계/.test(bodyText) && !/퍼널|SLA/.test(bodyText));

  /* ============================================================
     6) 말투 — 화면은 해요체, 고지·약관은 합니다체
     ============================================================ */
  ok('DF1 FAQ 문항·답변에 합니다체 없음', FAQ_QA.length >= 20 &&
    FAQ_QA.every((s) => !/(습니다|입니다)/.test(s)),
    FAQ_QA.filter((s) => /(습니다|입니다)/.test(s)).join(' | ').slice(0, 120));
  ok('DF2 FAQ 답변에 금지어 없음', FAQ_QA.every((s) => M.auditCopy(s).length === 0),
    FAQ_QA.map((s) => M.auditCopy(s).map((x) => x.term).join(',')).filter(Boolean).join(' | '));
  ok('DF3 예약 알림 템플릿에 금지어 없음', M.auditCopy(JSON.stringify(M.notices)).length === 0,
    M.auditCopy(JSON.stringify(M.notices)).slice(0, 3).map((x) => x.term).join(','));
  ok('DF4 약관·개인정보는 합니다체 유지', /똑똑쌤은 국가면허를 검증한 재활 선생님과 가정을 연결하는 방문재활 중개 플랫폼입니다/.test(TERMS_BLOCK) &&
    /5년 보관합니다/.test(TERMS_BLOCK) && /파기하며/.test(TERMS_BLOCK));
  ok('DF5 개인정보 — 회원 탈퇴 용어는 법령 표기로 유지', /회원 탈퇴 후 30일 안에 파기/.test(TERMS_BLOCK));
  ok('DF6 의료 범위 고지 유지', /똑똑쌤은 의료기관이 아니며 의료행위를 제공하지 않습니다/.test(bodyText));
  ok('DF7 응급 안내 — 119 먼저·센터 번호', /먼저 119/.test(textOf(doc, '#safetySheet')) &&
    M.safetyContacts.map((c) => c.tel).join(',').indexOf('031-919-8577') !== -1 &&
    M.safetyContacts[0].tel === '119');
  ok('DF8 화면 안내문에 "~하십시오" 없음', !/하십시오/.test(bodyText));
  ok('DF9 FAQ 검색은 옛 표현(이용권)도 찾는다', M.faqFilter('이용권', 'all').indexOf('faq-pass') !== -1,
    JSON.stringify(M.faqFilter('이용권', 'all')));
  ok('DF10 FAQ는 회차권으로 답한다', /회차권은 어떻게 쓰나요/.test(FAQ_BLOCK) && /1회권·4회권·8회권·12회권/.test(FAQ_BLOCK));

  /* ============================================================
     7) 운영자 화면 문구
     ============================================================ */
  ok('DG1 예약 큐 고지 — 이 기기에만 저장', /이 기기에만 저장 · 서버 미연결/.test(textOf(doc, '#adminResvDemoNotice')));
  ok('DG2 지표 고지 — 예시 수치·서버 미연결', /이 기기 데이터로만 계산한 예시 수치예요/.test(textOf(doc, '#adminMetricsNote')));
  ok('DG3 오늘 처리할 일 안내 해요체', /예외를 먼저 모았어요/.test(HTML) &&
    /배정할 수 있어요/.test(textOf(doc, '#adminOpsSub')), textOf(doc, '#adminOpsSub'));
  ok('DG4 데모 콘솔 → 시연용 콘솔', /시연용 콘솔이에요/.test(bodyText) && /시연용: 심사 승인 처리/.test(bodyText));
  ok('DG5 리마인드 미리보기 — 실제 발송 없음 고지 유지', /실제 문자·알림톡 발송은 하지 않습니다/.test(bodyText));

  /* ============================================================
     8) 지켜야 할 것 — 수치·시드·디자인
     ============================================================ */
  ok('DH1 단가·수수료·정산 규칙 불변', M.pricing.consumerPrice === 90000 && M.pricing.teacherPayout === 70000 &&
    M.pricing.platformFeeRate === 0.2222 && M.settlementRule.confirmDays === 3 &&
    JSON.stringify(M.settlementRule.payDays) === '[15,"end"]');
  ok('DH2 시드 예약 TT-261021-7302 그대로', /TT-261021-7302/.test(bodyText));
  ok('DH3 CSS 길이 상한(v48 경계·가로모드·인쇄 절 추가: 23.8만, 24.2만 이하)', STYLE.length >= 159697 && STYLE.length <= 242000, String(STYLE.length));
  ok('DH4 접근성 이름·대화상자 규칙 유지', (function () {
    const a = M.a11y.auditAll();
    return a.blank.length === 0 && M.a11y.labelledDialogs() === M.a11y.dialogCount() && M.a11y.dialogCount() >= 22;
  })());
  ok('DH5 index.html 1.45MB 이하', Buffer.byteLength(HTML, 'utf8') <= 1450 * 1024, String(Buffer.byteLength(HTML, 'utf8')));
  ok('DH6 문구 표준 상수는 화면에 렌더되지 않는다', M.copyBanned.length === 9 && !/copyBanned|COPY_BANNED/.test(bodyText));

  console.log('\nRESULT: ' + pass + ' passed, ' + fails.length + ' failed');
  if (fails.length) {
    console.log('FAILURES:');
    fails.forEach((f) => console.log(' - ' + f));
  }
  process.exit(fails.length ? 1 : 0);
}

run().catch((e) => { console.log('FATAL', (e && e.stack) || e); process.exit(1); });
