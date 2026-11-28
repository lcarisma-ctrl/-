#!/usr/bin/env python3
"""v25 스크린샷: 홈 통합 요약·첫 방문 온보딩·FAQ 검색(320·375·1280)."""
import os
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from playwright.sync_api import sync_playwright
URL = "file://" + os.path.join(ROOT, "index.html")
SHOT = os.path.join(ROOT, "preview")


def snap(page, name):
    page.screenshot(path=os.path.join(SHOT, "v25_%s.png" % name))


with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    for w, h, label, mobile in [(320, 568, "320", True), (375, 812, "375", True), (1280, 800, "1280", False)]:
        ctx = b.new_context(viewport={"width": w, "height": h}, is_mobile=mobile, has_touch=mobile,
                            device_scale_factor=2, locale="ko-KR")
        page = ctx.new_page()
        page.goto(URL)
        page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
        page.eval_on_selector('[data-login="customer"]', "el => el.click()")
        page.wait_for_timeout(2400)
        snap(page, "%s_home_summary" % label)
        page.tap("#homeGuideBtn") if mobile else page.click("#homeGuideBtn")
        page.wait_for_timeout(500)
        page.eval_on_selector("#obPrep-dress", "el => el.click()")
        page.wait_for_timeout(250)
        page.eval_on_selector("#guideSheet .sheet-scroll", "el => el.scrollTop = el.scrollHeight * 0.45")
        page.wait_for_timeout(250)
        snap(page, "%s_onboarding" % label)
        page.keyboard.press("Escape")
        page.wait_for_timeout(250)
        page.eval_on_selector('.tabbar[data-mode="customer"] [data-tab="mypage"]', "el => el.click()")
        page.wait_for_timeout(300)
        page.tap("#mpFaqRow") if mobile else page.click("#mpFaqRow")
        page.wait_for_timeout(500)
        page.fill("#faqSearch", "환불")
        page.wait_for_timeout(350)
        snap(page, "%s_faq_search" % label)
        page.fill("#faqSearch", "없는검색어")
        page.wait_for_timeout(350)
        snap(page, "%s_faq_empty" % label)
        page.keyboard.press("Escape")
        page.wait_for_timeout(250)
        ctx.close()
    b.close()
print("done")
