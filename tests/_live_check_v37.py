#!/usr/bin/env python3
"""v37 라이브 실브라우저 확인 — 입력 UX(자동 포커스·포맷·aria·키보드 회피)."""
import os, sys, importlib.util
spec = importlib.util.spec_from_file_location("e2e", os.path.join(os.path.dirname(os.path.abspath(__file__)), "e2e_chromium.py"))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
from playwright.sync_api import sync_playwright

LIVE = "https://lcarisma-ctrl.github.io/-/?v=37"
passed, failed, fails = 0, 0, []
def ok(name, cond, extra=""):
    global passed, failed
    if cond: passed += 1; print("  ✓ " + name)
    else:
        failed += 1; fails.append(name + (" :: " + str(extra) if extra else "")); print("  ✗ " + name + (" :: " + str(extra) if extra else ""))

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--font-render-hinting=none"])
    for (w, h, mob) in [(320, 568, True), (375, 812, True), (1280, 800, False)]:
        ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if mob else 1,
                            is_mobile=mob, has_touch=mob, locale="ko-KR")
        page = ctx.new_page(); errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda mm: errs.append("console:" + mm.text) if mm.type == "error" else None)
        tag = "[live %d] " % w
        page.goto(LIVE, wait_until="load", timeout=45000)
        page.wait_for_function("window.__ttokttokBooted === true", timeout=20000)
        page.wait_for_timeout(400)
        ok(tag + "부팅·meta v37", page.evaluate("() => document.querySelector('meta[name=app-version]').content") == "v37")
        ok(tag + "입력 훅 v37·필드 11", page.evaluate("() => { const s = window.__ttokttokModel.inputState(); return s.version === 'v37' && s.fields === 11 && s.bound === 11; }"))
        page.eval_on_selector("#gateCta", "el => el.click()")
        page.wait_for_timeout(420)
        ok(tag + "게이트 시트 자동 포커스(번호)", page.evaluate("() => document.activeElement && document.activeElement.id") == "gatePhone")
        page.fill("#gatePhone", "")
        page.keyboard.type("010", delay=30)
        page.keyboard.press("Tab")
        page.wait_for_timeout(220)
        ok(tag + "짧은 번호 → aria-invalid·오류 문구", page.evaluate("""() => { const el = document.getElementById('gatePhone'); const err = document.getElementById('gatePhoneErr');
            return el.getAttribute('aria-invalid') === 'true' && el.getAttribute('aria-describedby') === 'gatePhoneErr' && getComputedStyle(err).display !== 'none'; }"""))
        page.click("#gatePhone"); page.fill("#gatePhone", ""); page.keyboard.type("01012345678", delay=20)
        page.wait_for_timeout(160)
        ok(tag + "입력 즉시 하이픈", page.evaluate("() => document.getElementById('gatePhone').value") == "010-1234-5678")
        page.keyboard.press("Tab"); page.wait_for_timeout(180)
        ok(tag + "고친 뒤 오류 해제", page.evaluate("() => document.getElementById('gatePhone').getAttribute('aria-invalid') === 'false'"))
        page.evaluate("() => window.__ttokttokModel.simulateKeyboard(280)")
        page.wait_for_timeout(240)
        kb = page.evaluate("""() => { const s = document.querySelector('#gateSheet .sheet'); const r = s.getBoundingClientRect();
            return { inset: getComputedStyle(document.documentElement).getPropertyValue('--kb-inset').trim(), bottom: Math.round(r.bottom), innerH: innerHeight }; }""")
        ok(tag + "키보드 시뮬레이션 → 시트가 그만큼 올라감", kb["inset"] == "280px" and abs(kb["bottom"] - (kb["innerH"] - 280)) <= 3, str(kb))
        over = page.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        ok(tag + "가로 넘침 0", over <= 0, str(over))
        ok(tag + "JS 오류 0", not errs, errs[:2])
        page.screenshot(path=os.path.join(m.SHOT, "live_v37_%d_gate.png" % w))
        ctx.close()
    b.close()

print("\nLIVE V37: %d passed, %d failed" % (passed, failed))
for f in fails: print(" - " + f)
sys.exit(1 if failed else 0)
