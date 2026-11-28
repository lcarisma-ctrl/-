#!/usr/bin/env python3
"""v26 정산 명세서 화면 스크린샷(검토용)."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")
from playwright.sync_api import sync_playwright

URL = "file://" + os.path.join(ROOT, "index.html")
SHOT = os.path.join(ROOT, "preview")

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    for w, h, tag in [(390, 844, "390"), (320, 568, "320")]:
        ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="ko-KR")
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.goto(URL)
        page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
        page.eval_on_selector('[data-login="therapist"]', "el => el.click()")
        page.wait_for_timeout(400)
        page.screenshot(path=os.path.join(SHOT, "v26_%s_tp_home.png" % tag), full_page=False)
        page.tap('#tpSettle [data-tab="tp-settle"]')
        page.wait_for_timeout(500)
        page.screenshot(path=os.path.join(SHOT, "v26_%s_settle_top.png" % tag))
        page.evaluate("window.scrollTo(0, 520)")
        page.wait_for_timeout(300)
        page.screenshot(path=os.path.join(SHOT, "v26_%s_settle_rows.png" % tag))
        m = page.evaluate("() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})")
        print(tag, "overflow", m, "errors", errs)
        page.tap('#tpsScreen [data-stl-preview]')
        page.wait_for_timeout(500)
        page.screenshot(path=os.path.join(SHOT, "v26_%s_print_sheet.png" % tag))
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
        ctx.close()
    b.close()
print("done")
