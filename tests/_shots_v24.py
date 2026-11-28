#!/usr/bin/env python3
"""v24 QA 스크린샷 모음(320·375·1280). 실행: python3 tests/_shots_v24.py"""
import os
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from playwright.sync_api import sync_playwright
URL = "file://" + os.path.join(ROOT, "index.html")
SHOT = os.path.join(ROOT, "preview")


def snap(page, name):
    page.screenshot(path=os.path.join(SHOT, "v24_%s.png" % name))


with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    for w, h, label, mobile in [(320, 568, "320", True), (375, 812, "375", True), (1280, 800, "1280", False)]:
        ctx = b.new_context(viewport={"width": w, "height": h}, is_mobile=mobile, has_touch=mobile,
                            device_scale_factor=2, locale="ko-KR")
        page = ctx.new_page()
        page.goto(URL)
        page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
        snap(page, "%s_gate" % label)
        page.tap("#gateCta") if mobile else page.click("#gateCta")
        page.wait_for_timeout(300)
        snap(page, "%s_gate_sheet" % label)
        page.eval_on_selector('[data-login="customer"]', "el => el.click()")
        page.wait_for_timeout(2300)
        snap(page, "%s_home" % label)
        page.eval_on_selector('.tabbar[data-mode="customer"] [data-tab="teachers"]', "el => el.click()")
        page.wait_for_timeout(350)
        snap(page, "%s_teachers" % label)
        if label != "1280":
            page.eval_on_selector('#teacherViewTabs [data-view="near"]', "el => el.click()")
            page.wait_for_timeout(400)
            snap(page, "%s_near" % label)
            page.eval_on_selector('#teacherViewTabs [data-view="list"]', "el => el.click()")
            page.wait_for_timeout(250)
        page.eval_on_selector("#teacherList .teacher", "el => el.click()")
        page.wait_for_timeout(400)
        snap(page, "%s_teacher_sheet" % label)
        page.keyboard.press("Escape")
        page.wait_for_timeout(250)
        page.eval_on_selector('.tabbar[data-mode="customer"] [data-tab="mypage"]', "el => el.click()")
        page.wait_for_timeout(250)
        page.eval_on_selector("#mpBookLink", "el => el.click()")
        page.wait_for_timeout(350)
        snap(page, "%s_account" % label)
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
        page.eval_on_selector('.tabbar[data-mode="customer"] [data-tab="journal"]', "el => el.click()")
        page.wait_for_timeout(300)
        page.eval_on_selector("[data-safety-open]", "el => el.click()")
        page.wait_for_timeout(300)
        snap(page, "%s_safety" % label)
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
        # 선생님·관리자
        page.evaluate("() => document.getElementById('entryGate').classList.add('is-open')")
        page.wait_for_timeout(150)
        page.eval_on_selector('[data-login="therapist"]', "el => el.click()")
        page.wait_for_timeout(2300)
        snap(page, "%s_partner_home" % label)
        page.eval_on_selector('.tabbar[data-mode="therapist"] [data-tab="tp-journal"]', "el => el.click()")
        page.wait_for_timeout(350)
        snap(page, "%s_partner_quick" % label)
        page.evaluate("() => document.getElementById('entryGate').classList.add('is-open')")
        page.wait_for_timeout(150)
        page.eval_on_selector('[data-login="admin"]', "el => el.click()")
        page.wait_for_timeout(2300)
        snap(page, "%s_admin" % label)
        ctx.close()
    b.close()
print("shots done")
