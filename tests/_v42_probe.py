#!/usr/bin/env python3
"""v42 개발용 프로브 — 홈 첫 화면 계측 + 관리자 KPI 겹침 확인."""
import os, json
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "file://" + os.path.join(ROOT, "index.html")

HOME_JS = """() => {
  const r = el => { if(!el) return null; const b = el.getBoundingClientRect(); return {top:Math.round(b.top),bottom:Math.round(b.bottom),h:Math.round(b.height)}; };
  return {
    vh: innerHeight,
    card: r(document.querySelector('#homeSummaryCard')),
    next: r(document.querySelector('#homeSummaryNext')),
    rebook: r(document.querySelector('#homeSummaryRebook')),
    pass: r(document.querySelector('#homeSummaryPass')),
    report: r(document.querySelector('#homeSummaryReport')),
    passFirst: r(document.querySelector('#homeSummaryPass .sum-row')),
    tabbar: r(document.querySelector('.tabbar[data-mode=customer]')),
  };
}"""

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox","--disable-dev-shm-usage"])
    for w,h,mob in [(390,844,True),(375,812,True),(320,568,True)]:
        ctx = b.new_context(viewport={"width":w,"height":h}, device_scale_factor=2, is_mobile=mob, has_touch=mob, locale="ko-KR")
        pg = ctx.new_page()
        pg.goto(URL); pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000); pg.wait_for_timeout(500)
        pg.eval_on_selector('[data-login="customer"]', "el=>el.click()"); pg.wait_for_timeout(1200)
        print(w, json.dumps(pg.evaluate(HOME_JS), ensure_ascii=False))
        pg.screenshot(path=os.path.join(ROOT,"preview","v42-audit","probe_%d_home.png"%w))
        ctx.close()
    # admin
    ctx = b.new_context(viewport={"width":390,"height":844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="ko-KR")
    pg = ctx.new_page(); pg.goto(URL); pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000); pg.wait_for_timeout(400)
    pg.eval_on_selector('[data-login="admin"]', "el=>el.click()"); pg.wait_for_timeout(1500)
    print("note box", pg.evaluate("""() => { const n=document.querySelector('#adminMetricsNote'); const r=n.getBoundingClientRect(); const cs=getComputedStyle(n); return {top:Math.round(r.top),h:Math.round(r.height),pos:cs.position,disp:cs.display,bg:cs.backgroundColor,scrollY:window.scrollY}; }"""))
    pg.screenshot(path=os.path.join(ROOT,"preview","v42-audit","probe_390_admin.png"))
    ctx.close()
    b.close()
