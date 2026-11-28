#!/usr/bin/env python3
"""v43 라이브 확인 — https://lcarisma-ctrl.github.io/-/?v=43"""
import os
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright
import urllib.request

URL = "https://lcarisma-ctrl.github.io/-/?v=43&live=%d" % os.getpid()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "preview")
okc = 0; bad = []
def ok(name, cond, extra=""):
    global okc
    if cond: okc += 1; print("  ✓", name)
    else: bad.append(name + (" :: " + str(extra) if extra else "")); print("  ✗", name, extra)

html = urllib.request.urlopen("https://lcarisma-ctrl.github.io/-/?v=43").read().decode("utf-8")
ok("HTTP 200 · app-version v43", 'content="v43"' in html, len(html))
ok("인트로 컷신 장면 포함", "in-teacher" in html and "in-recover" in html)
ok("로고 base64 중복 없음", html.count("data:image/png;base64") <= 3, html.count("data:image/png;base64"))

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
    # 인트로
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="ko-KR")
    ctx.add_init_script("try{sessionStorage.removeItem('ttokttok_intro_v41')}catch(e){}")
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.goto(URL + "&intro=1"); pg.wait_for_function("window.__ttokttokBooted===true", timeout=30000); pg.wait_for_timeout(200)
    ok("인트로 컷신 표시", pg.evaluate("() => !document.getElementById('intro').hidden"))
    pg.screenshot(path=os.path.join(OUT, "live_v43_intro.png"))
    pg.wait_for_timeout(2400)
    ok("인트로가 스스로 끝남", pg.evaluate("() => document.getElementById('intro').hidden === true"))
    pg.eval_on_selector('[data-login="customer"]', "el=>el.click()"); pg.wait_for_timeout(2000)
    ok("첫 화면 정상", pg.is_visible("#homeSummaryCard") and pg.is_visible("#homePassCard"))
    ok("콘솔·페이지 오류 0", not errs, errs[:3])
    ctx.close()
    # 320
    ctx = b.new_context(viewport={"width": 320, "height": 568}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="ko-KR")
    pg = ctx.new_page(); pg.goto(URL + "&intro=0"); pg.wait_for_function("window.__ttokttokBooted===true", timeout=30000); pg.wait_for_timeout(400)
    pg.eval_on_selector('[data-login="customer"]', "el=>el.click()"); pg.wait_for_timeout(2000)
    fold = pg.evaluate("""() => { const r=(s)=>{const e=document.querySelector(s); if(!e) return null; return Math.round(e.getBoundingClientRect().bottom);};
      return {pass:r('#homePassCard'), tab:r('.tabbar[data-mode=customer]')}; }""")
    ok("320 첫 화면에 회차권 카드까지", fold["pass"] and fold["pass"] <= fold["tab"], fold)
    pg.screenshot(path=os.path.join(OUT, "live_v43_320_home.png"))
    ctx.close()
    # 빈 상태 그림
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="ko-KR")
    pg = ctx.new_page(); pg.goto(URL + "&intro=0"); pg.wait_for_function("window.__ttokttokBooted===true", timeout=30000); pg.wait_for_timeout(300)
    pg.eval_on_selector('[data-login="admin"]', "el=>el.click()"); pg.wait_for_timeout(1500)
    pg.evaluate("""() => { const b = [...document.querySelectorAll('#adminResvFilters [data-admin-resv-filter]')].find((x) => /노쇼/.test(x.textContent)); if (b) b.click(); }""")
    pg.wait_for_timeout(600)
    ok("빈 상태 그림 표시", pg.evaluate("() => !!document.querySelector('#adminResvQueue .empty svg.empty-art')"))
    pg.evaluate("()=>{const e=document.querySelector('#adminResvQueue'); if(e) e.scrollIntoView({block:'center'});}"); pg.wait_for_timeout(300)
    pg.screenshot(path=os.path.join(OUT, "live_v43_empty.png"))
    ctx.close(); b.close()

print("\nLIVE v43: %d passed, %d failed" % (okc, len(bad)))
for x in bad: print(" -", x)
