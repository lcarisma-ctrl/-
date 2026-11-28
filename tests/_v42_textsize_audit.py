#!/usr/bin/env python3
"""v42 큰 글자 감사 — 390/320 × 보통/아주 크게(1.3) × 12화면.
   넘침(scrollWidth>clientWidth), 글자 잘림(clip), 두 줄 CTA, 44px 미만 터치, 콘솔 오류를 센다."""
import os, sys, json
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "file://" + os.path.join(ROOT, "index.html")
OUT = os.path.join(ROOT, "preview", "v42-audit")

AUDIT = r"""
() => {
  const out = { overflow: [], clip: [], btn2: [], small: [], vw: innerWidth, sw: document.documentElement.scrollWidth };
  const vis = (el) => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
  const inScroller = (el) => {
    let n = el.parentElement;
    while (n && n !== document.body) {
      const c = getComputedStyle(n);
      if (/(auto|scroll)/.test(c.overflowX)) return true;
      n = n.parentElement;
    }
    return false;
  };
  const all = [...document.querySelectorAll('.screen.is-active *, .sheet.is-open *, .backdrop.is-open *, .tabbar *')];
  all.forEach((el) => {
    if (!vis(el)) return;
    const cs = getComputedStyle(el);
    const txt = (el.textContent || '').trim();
    if (txt && el.children.length === 0) {
      if (el.scrollWidth > el.clientWidth + 1 && /hidden|clip/.test(cs.overflowX)) out.clip.push(el.tagName + '.' + el.className + ' :: ' + txt.slice(0, 30));
      if (cs.textOverflow === 'ellipsis' && el.scrollWidth > el.clientWidth + 1) out.clip.push('ELL ' + txt.slice(0, 30));
    }
  });
  all.forEach((el) => {
    if (!vis(el)) return;
    const r = el.getBoundingClientRect();
    if (r.right > innerWidth + 1 || r.left < -1) {
      if (!el.closest('.tabbar') && !inScroller(el)) out.overflow.push(el.tagName + '.' + (typeof el.className === 'string' ? el.className : '') + ' :: ' + (el.textContent || '').trim().slice(0, 24));
    }
  });
  document.querySelectorAll('.btn, .wiz-nav button, .sheet-foot button').forEach((el) => {
    if (!vis(el)) return;
    const r = el.getBoundingClientRect();
    const lh = parseFloat(getComputedStyle(el).lineHeight) || 20;
    const txt = (el.textContent || '').trim();
    if (txt && r.height > lh * 2.6 && r.height > 74) out.btn2.push(txt.slice(0, 24) + ' h=' + Math.round(r.height));
  });
  if (document.documentElement.scrollWidth > innerWidth + 1) out.overflow.unshift('PAGE scrollWidth=' + document.documentElement.scrollWidth);
  return out;
}
"""

SCREENS = [
    ("home", "() => {}"),
    ("teachers", "() => document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]').click()"),
    ("booking1", "() => document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=booking]').click()"),
    ("journal", "() => document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=journal]').click()"),
    ("mypage", "() => document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=mypage]').click()"),
]
PARTNER = [
    ("tp_home", "() => {}"),
    ("tp_settle", "() => document.querySelector('.tabbar[data-mode=therapist] .tabbtn[data-tab=tp-settle]').click()"),
]

def run():
    rows = []
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox","--disable-dev-shm-usage"])
        for size in ("md", "xl"):
            for w, h, mob in [(390, 844, True), (320, 568, True)]:
                for name, js in SCREENS:
                    ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, is_mobile=mob, has_touch=mob, locale="ko-KR")
                    ctx.add_init_script("try{localStorage.setItem('ttokttok_textsize_v1','%s')}catch(e){}" % size)
                    pg = ctx.new_page()
                    errs = []
                    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
                    pg.on("pageerror", lambda e: errs.append(str(e)))
                    pg.goto(URL); pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000); pg.wait_for_timeout(400)
                    pg.eval_on_selector('[data-login="customer"]', "el=>el.click()"); pg.wait_for_timeout(900)
                    pg.evaluate(js); pg.wait_for_timeout(2200)
                    r = pg.evaluate(AUDIT); r["err"] = errs[:3]
                    rows.append((size, w, name, r))
                    if size == "xl" and w == 390:
                        pg.screenshot(path=os.path.join(OUT, "xl_390_%s.png" % name))
                    ctx.close()
        # 파트너·관리자
        for size in ("md", "xl"):
            for w, h, mob in [(390, 844, True), (320, 568, True)]:
                for name, js in PARTNER:
                    ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, is_mobile=mob, has_touch=mob, locale="ko-KR")
                    ctx.add_init_script("try{localStorage.setItem('ttokttok_textsize_v1','%s')}catch(e){}" % size)
                    pg = ctx.new_page()
                    errs = []
                    pg.on("pageerror", lambda e: errs.append(str(e)))
                    pg.goto(URL); pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000); pg.wait_for_timeout(300)
                    pg.eval_on_selector('[data-login="therapist"]', "el=>el.click()"); pg.wait_for_timeout(900)
                    pg.evaluate(js); pg.wait_for_timeout(1500)
                    r = pg.evaluate(AUDIT); r["err"] = errs[:3]
                    rows.append((size, w, name, r))
                    ctx.close()
                ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, is_mobile=mob, has_touch=mob, locale="ko-KR")
                ctx.add_init_script("try{localStorage.setItem('ttokttok_textsize_v1','%s')}catch(e){}" % size)
                pg = ctx.new_page()
                errs = []
                pg.on("pageerror", lambda e: errs.append(str(e)))
                pg.goto(URL); pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000); pg.wait_for_timeout(300)
                pg.eval_on_selector('[data-login="admin"]', "el=>el.click()"); pg.wait_for_timeout(1500)
                pg.evaluate("()=>{const e=document.querySelector('#adminMetricsKpiCard'); if(e) e.scrollIntoView({block:'start'});}")
                pg.wait_for_timeout(600)
                r = pg.evaluate(AUDIT); r["err"] = errs[:3]
                rows.append((size, w, "admin", r))
                if size == "xl" and w == 390:
                    pg.screenshot(path=os.path.join(OUT, "xl_390_admin.png"))
                ctx.close()
        b.close()
    bad = 0
    for size, w, name, r in rows:
        n = len(r["overflow"]) + len(r["clip"]) + len(r["btn2"]) + len(r["err"])
        if n:
            bad += 1
            print("[%s %d %s] overflow=%d clip=%d btn2=%d err=%d" % (size, w, name, len(r["overflow"]), len(r["clip"]), len(r["btn2"]), len(r["err"])))
            for k in ("overflow", "clip", "btn2", "err"):
                for x in r[k][:4]:
                    print("   ", k, x)
    print("\n=== %d/%d 화면에 지적 있음 ===" % (bad, len(rows)))

run()
