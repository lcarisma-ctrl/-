#!/usr/bin/env python3
"""v42 라이브 확인 — https://lcarisma-ctrl.github.io/-/?v=42 실제 브라우저 12항목."""
import os
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright
import urllib.request, re

URL = "https://lcarisma-ctrl.github.io/-/?v=42&live=%d" % os.getpid()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "preview")
okc = 0; bad = []
def ok(name, cond, extra=""):
    global okc
    if cond: okc += 1; print("  ✓", name)
    else: bad.append(name + (" :: " + str(extra) if extra else "")); print("  ✗", name, extra)

html = urllib.request.urlopen("https://lcarisma-ctrl.github.io/-/?v=42").read().decode("utf-8")
ok("HTTP 200 본문 · app-version v42", 'content="v42"' in html, len(html))
ok("토큰 배율(--fs-scale) 포함", "--fs-scale:1" in html)
ok("손짓 스크립트 포함", "TtGesture" in html)

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="ko-KR")
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.goto(URL); pg.wait_for_function("window.__ttokttokBooted===true", timeout=30000); pg.wait_for_timeout(600)
    ok("v42 메타", pg.evaluate("() => document.querySelector('meta[name=app-version]').content") == "v42")
    pg.eval_on_selector('[data-login="customer"]', "el=>el.click()"); pg.wait_for_timeout(2200)
    fold = pg.evaluate("""() => { const r=(s)=>{const e=document.querySelector(s); if(!e) return null; const b=e.getBoundingClientRect(); return Math.round(b.bottom);};
      return {pass:r('#homePassCard'), tab:r('.tabbar[data-mode=customer]')}; }""")
    ok("첫 화면에 회차권 카드까지", fold["pass"] and fold["tab"] and fold["pass"] <= fold["tab"], fold)
    pg.screenshot(path=os.path.join(OUT, "live_v42_home.png"))
    pg.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]', "el=>el.click()"); pg.wait_for_timeout(700)
    pg.eval_on_selector('#teacherList [data-teacher]', "el=>el.click()"); pg.wait_for_timeout(600)
    hb = pg.evaluate("""() => { const h=document.querySelector('#teacherSheet .sheet-handle'); const r=h.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2}; }""")
    pg.mouse.move(hb["x"], hb["y"]); pg.mouse.down()
    for i in range(1, 12): pg.mouse.move(hb["x"], hb["y"] + i*13); pg.wait_for_timeout(14)
    pg.mouse.up(); pg.wait_for_timeout(700)
    ok("시트 스와이프로 닫힘", not pg.evaluate("() => document.querySelector('#teacherSheet').classList.contains('is-open')"))
    pg.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=mypage]', "el=>el.click()"); pg.wait_for_timeout(600)
    pg.eval_on_selector('#mpTextSize [data-textsize="xl"]', "el=>el.click()"); pg.wait_for_timeout(400)
    ok("글자 크기 아주 크게 적용", pg.evaluate("() => document.documentElement.getAttribute('data-textsize')") == "xl")
    pg.screenshot(path=os.path.join(OUT, "live_v42_textsize.png"))
    pg.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=home]', "el=>el.click()"); pg.wait_for_timeout(1200)
    ok("아주 크게 홈 넘침 없음", pg.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1"))
    pg.screenshot(path=os.path.join(OUT, "live_v42_home_xl.png"))
    pg.eval_on_selector('#mpTextSize [data-textsize="md"]', "el=>el.click()") if pg.query_selector('#mpTextSize') else None
    pg.eval_on_selector('#rolePill', "el=>el.click()"); pg.wait_for_timeout(400)
    pg.eval_on_selector('[data-role-switch="admin"], [data-admin-open]', "el=>el.click()"); pg.wait_for_timeout(1600)
    rows = pg.eval_on_selector_all("#adminMetricsFunnelRows .adm-row", "els => els.length")
    ok("관리자 표 6행", rows == 6, rows)
    ok("지역 카드 수치 칸", pg.eval_on_selector_all(".adm-reg > span", "els => els.length") >= 3)
    pg.eval_on_selector('#adminMetricsFunnel', "el=>el.scrollIntoView({block:'start'})"); pg.wait_for_timeout(500)
    pg.screenshot(path=os.path.join(OUT, "live_v42_admin.png"))
    ok("콘솔·페이지 오류 0", not errs, errs[:3])
    ctx.close(); b.close()

print("\nLIVE v42: %d passed, %d failed" % (okc, len(bad)))
for x in bad: print(" -", x)
