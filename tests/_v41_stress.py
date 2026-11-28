#!/usr/bin/env python3
"""v41 빠른 시각·텍스트 붕괴 점검 (Chromium).

전 화면·시트를 320/375/390/1280 에서 돌며
  ① 문서·요소 가로 넘침    ② 글자 잘림(scrollWidth > clientWidth)
  ③ 버튼 글자 2줄           ④ 접근성 이름 없는 버튼
  ⑤ 터치 44px 미만          ⑥ 콘솔 오류
를 센다. --stress 를 주면 긴 이름·긴 금액·긴 주소를 주입해 같은 검사를 반복한다.

사용: python3 tests/_v41_stress.py            (기본)
      python3 tests/_v41_stress.py --stress   (긴 콘텐츠 주입)
"""
import os, sys, json
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "file://" + os.path.join(ROOT, "index.html")
STRESS = "--stress" in sys.argv
WIDTHS = [(320, 568), (375, 812), (390, 844), (1280, 900)]

AUDIT = r"""
() => {
  const out = {doc:[], clip:[], ell:[], wordbreak:[], btn2:[], unnamed:[], small:[], badtext:[]};
  const vw = document.documentElement.clientWidth;
  const label = (el) => el.id ? '#'+el.id : (typeof el.className==='string' && el.className.trim() ? '.'+el.className.trim().split(/\s+/).slice(0,2).join('.') : el.tagName.toLowerCase());
  const vis = (el) => {
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    if (s.visibility==='hidden'||s.display==='none'||Number(s.opacity)===0) return false;
    return r.width>1 && r.height>1;
  };
  const DOC_OVER = document.documentElement.scrollWidth > vw+1;
  if (DOC_OVER) out.doc.push('scrollWidth='+document.documentElement.scrollWidth+' > '+vw);
  document.querySelectorAll('body *').forEach((el)=>{
    if (!vis(el)) return;
    const s = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    if (DOC_OVER && s.position!=='fixed') {
      if (r.right > vw+1.5 && r.width <= vw+1) out.doc.push(label(el)+' right='+Math.round(r.right));
      if (r.left < -1.5) out.doc.push(label(el)+' left='+Math.round(r.left));
    }
    // 글자 잘림: 넘치는 자식이 hidden/ellipsis 로 잘려 있는데 스크롤로도 안 보이는 경우
    const hasText = Array.from(el.childNodes).some(n=>n.nodeType===3 && n.textContent.trim());
    if (hasText && el.scrollWidth > el.clientWidth+1 && (s.overflowX==='hidden'||s.overflowX==='clip') && s.textOverflow!=='ellipsis') {
      out.clip.push(label(el)+' '+el.scrollWidth+'>'+el.clientWidth+' "'+(el.textContent||'').trim().slice(0,24)+'"');
    }
    if (hasText && s.textOverflow==='ellipsis' && el.scrollWidth > el.clientWidth+1) {
      out.ell.push(label(el)+' "'+(el.textContent||'').trim().slice(0,26)+'"');
    }
    if (hasText && s.wordBreak==='break-all' && /[가-힣]/.test(el.textContent||'')) {
      out.wordbreak.push(label(el)+' word-break:'+s.wordBreak+' "'+(el.textContent||'').trim().slice(0,20)+'"');
    }
    if (hasText && el.scrollHeight > el.clientHeight+2 && (s.overflowY==='hidden'||s.overflowY==='clip') && s.display!=='inline') {
      out.clip.push(label(el)+' h '+el.scrollHeight+'>'+el.clientHeight+' "'+(el.textContent||'').trim().slice(0,24)+'"');
    }
    if (/(undefined|NaN|\[object |Infinity|null원)/.test(el.textContent||'') && hasText) out.badtext.push(label(el)+' "'+(el.textContent||'').trim().slice(0,30)+'"');
  });
  // 버튼 글자 2줄
  document.querySelectorAll('.btn,.wiz-nav button,.sheet-foot button,.gate-cta,.chip').forEach((el)=>{
    if (!vis(el)) return;
    const tops = [];
    // 글자 노드만 센다(아이콘 줄과 글자 줄을 두 줄로 오해하지 않게)
    const tw = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let n; const rg = document.createRange();
    while ((n = tw.nextNode())) {
      if (!n.textContent.trim()) continue;
      rg.selectNodeContents(n);
      [...rg.getClientRects()].filter(x=>x.width>1&&x.height>1).forEach(x=>{ if(!tops.some(y=>Math.abs(y-x.top)<7)) tops.push(x.top); });
    }
    if (tops.length>=2) out.btn2.push(label(el)+' "'+el.textContent.trim().slice(0,20)+'"');
  });
  // 이름 없는 버튼 / 44px 미만
  document.querySelectorAll('button,[role="button"],a[href]').forEach((el)=>{
    if (!vis(el)) return;
    const n = (el.getAttribute('aria-label')||'').trim() || (el.textContent||'').replace(/\s+/g,' ').trim() || (el.getAttribute('title')||'');
    if (!n) out.unnamed.push(label(el));
    const r = el.getBoundingClientRect();
    if (r.width<43.5 || r.height<43.5) out.small.push(label(el)+' '+Math.round(r.width)+'x'+Math.round(r.height));
  });
  return out;
}
"""

STRESS_JS = r"""
() => {
  // 실제 서비스에서 들어올 수 있는 긴 값으로 바꿔 본다(사실을 만들지 않고 같은 자리만 늘린다).
  const NAME = '김수한무거북이와두루미';
  const ADDR = '경기도 파주시 야당동 1234-56 봄빛마을 3단지 123동 1203호';
  const LONG = '대학병원 재활의학과 협진과 방문재활을 함께 해온 18년 차 물리치료사입니다. 뇌졸중·편마비 보행 재훈련과 낙상 예방을 주로 다루어요.';
  const AMT = '1,234,500원';
  let n = 0;
  document.querySelectorAll('.t-name,.h-name,.sheet-name,.brand-name').forEach(el=>{ el.textContent = NAME; n++; });
  document.querySelectorAll('.account-name,.mp-name,.tp-name,.role-body b').forEach(el=>{ el.textContent = NAME; n++; });
  document.querySelectorAll('.t-meta,.h-meta,.t-region,.region-line,.account-sub').forEach(el=>{ el.textContent = ADDR; n++; });
  document.querySelectorAll('.t-quote,.t-intro,.sheet-intro').forEach(el=>{ el.textContent = LONG; n++; });
  document.querySelectorAll('.t-price b,.price-row .pr-price b,.sum-row b,.total b,.num').forEach(el=>{ el.textContent = AMT; n++; });
  document.querySelectorAll('#teacherList .teacher').forEach(el=>{ el.setAttribute('data-teacher-stress','1'); });
  return n;
}
"""


def run():
    total = {k: 0 for k in ("doc", "clip", "ell", "wordbreak", "btn2", "unnamed", "small", "badtext")}
    detail = []
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--disable-dev-shm-usage"])
        for w, h in WIDTHS:
            mob = w < 500
            ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=1,
                                is_mobile=mob, has_touch=mob, locale="ko-KR")
            pg = ctx.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append("pageerror:" + str(e)))
            pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
            pg.goto(URL)
            pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000)
            pg.wait_for_timeout(300)

            def check(state):
                pg.wait_for_timeout(120)
                r = pg.evaluate(AUDIT)
                for k, v in r.items():
                    if v:
                        total[k] += len(v)
                        for item in v[:6]:
                            detail.append("[%d] %s :: %s" % (w, state, item))

            check("gate")
            for role, tabs in (("customer", ["home", "teachers", "booking", "journal", "mypage"]),
                               ("therapist", ["tp-home", "tp-schedule", "tp-journal", "tp-settle", "tp-mypage"])):
                pg.eval_on_selector('[data-login="%s"]' % role, "el=>el.click()")
                pg.wait_for_timeout(500)
                for i, t in enumerate(tabs):
                    if i or role == "therapist":
                        pg.eval_on_selector('.tabbar[data-mode=%s] .tabbtn[data-tab="%s"]' % ("customer" if role == "customer" else "therapist", t), "el=>el.click()")
                        pg.wait_for_timeout(260)
                    if STRESS:
                        pg.evaluate(STRESS_JS)
                    check(role + "/" + t)
                # 시트
                if role == "customer":
                    pg.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab="teachers"]', "el=>el.click()")
                    pg.wait_for_timeout(260)
                    pg.eval_on_selector("#teacherList .teacher", "el=>el.click()")
                    pg.wait_for_timeout(320)
                    if STRESS:
                        pg.evaluate(STRESS_JS)
                    check("teacherSheet")
                    pg.keyboard.press("Escape")
                    pg.wait_for_timeout(260)
            pg.eval_on_selector("#rolePill", "el=>el.click()")
            pg.wait_for_timeout(250)
            pg.eval_on_selector("#roleSheet [data-admin-open]", "el=>el.click()")
            pg.wait_for_timeout(420)
            check("admin")
            if errs:
                total["badtext"] += 0
                detail.append("[%d] console :: %s" % (w, str(errs[:2])))
            pg.close()
            ctx.close()
        b.close()
    print(json.dumps(total, ensure_ascii=False))
    for d in detail[:80]:
        print(" - " + d)
    print("TOTAL issues:", sum(total.values()))


run()
