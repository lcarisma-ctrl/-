#!/usr/bin/env python3
"""v19 라이브 실브라우저 확인: 부팅·버전·운영 보드·파트너 알림함·가용시간/지역 저장."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")
from playwright.sync_api import sync_playwright

URL = "https://lcarisma-ctrl.github.io/-/?v=19"
SHOT = os.path.join(ROOT, "preview")

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--no-sandbox", "--font-render-hinting=none"])
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                              is_mobile=True, has_touch=True, locale="ko-KR")
    page = ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.goto(URL, wait_until="load")
    page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
    page.tap("#gateCta")
    page.wait_for_selector('[data-login="customer"]', state="visible", timeout=8000)
    page.tap('[data-login="customer"]')
    page.wait_for_timeout(400)
    print(page.evaluate("""() => {
      const m = window.__ttokttokModel;
      return {
        version: document.querySelector('meta[name="app-version"]').content,
        booted: window.__ttokttokBooted === true,
        ops: m.opsVersion,
        cancelReasons: m.cancelReasons.length,
        teacherUnread: m.teacherUnread()
      };
    }"""))
    page.eval_on_selector("[data-admin-open]", "el => el.click()")
    page.wait_for_timeout(600)
    print("ops board visible:", page.is_visible("#adminOpsSec"))
    print("queue cards:", page.eval_on_selector_all("#adminMatchQueue .admin-card", "els => els.length"))
    print("exception groups:", page.eval_on_selector_all("#adminExceptionBoard .admin-card", "els => els.length"))
    print("board sub:", page.inner_text("#adminOpsSub"))
    page.screenshot(path=os.path.join(SHOT, "live_v19_admin_ops.png"))
    page.eval_on_selector('[data-login="therapist"]', "el => el.click()")
    page.wait_for_timeout(500)
    print("partner inbox items:", page.eval_on_selector_all("#tpNotifList [data-tp-notif]", "els => els.length"))
    page.eval_on_selector('.tabbar[data-mode="therapist"] .tabbtn[data-tab="tp-mypage"]', "el => el.click()")
    page.wait_for_timeout(400)
    print("avail chips:", page.eval_on_selector_all("#tpAvailForm [data-tp-day]", "els => els.length"),
          page.eval_on_selector_all("#tpAvailForm [data-tp-time]", "els => els.length"))
    page.screenshot(path=os.path.join(SHOT, "live_v19_partner_avail.png"))
    print("errors:", errs[:3])
    browser.close()
