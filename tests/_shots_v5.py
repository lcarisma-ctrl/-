"""v5 화면 컷: 여백·가격 노출 정리 확인용.

실행: python3 tests/_shots_v5.py  → preview/v5_*.png
"""
import os
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright

ROOT = "/workspace/projects/ttokttok-app"
OUT = ROOT + "/preview"

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files"])
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="ko-KR")
    page = ctx.new_page()
    page.goto("file://" + ROOT + "/index.html")
    page.wait_for_function("window.__ttokttokBooted === true")
    page.wait_for_timeout(300)
    page.screenshot(path=OUT + "/v5_gate.png")

    page.tap("#gateCta")
    page.wait_for_timeout(450)
    page.tap('[data-login="customer"]')
    page.wait_for_timeout(3200)  # toast clear
    page.screenshot(path=OUT + "/v5_home.png")
    # 홈 전체(스크롤) 컷
    page.evaluate("window.scrollTo(0, 0)")
    h = page.evaluate("document.querySelector('#screen-home').scrollHeight")
    page.screenshot(path=OUT + "/v5_home_full.png", full_page=False)
    page.evaluate("window.scrollTo(0, 720)")
    page.wait_for_timeout(400)
    page.screenshot(path=OUT + "/v5_home_2.png")
    page.evaluate("window.scrollTo(0, 1440)")
    page.wait_for_timeout(400)
    page.screenshot(path=OUT + "/v5_home_3.png")
    page.evaluate("window.scrollTo(0, 99999)")
    page.wait_for_timeout(400)
    page.screenshot(path=OUT + "/v5_home_4.png")
    print("home scrollHeight:", h)

    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]')
    page.wait_for_timeout(500)
    page.screenshot(path=OUT + "/v5_teachers.png")
    page.tap('#teacherList .teacher')
    page.wait_for_timeout(550)
    page.screenshot(path=OUT + "/v5_sheet.png")

    page.tap('#sheetBook')
    page.wait_for_timeout(450)
    page.select_option('#bookProvince', '서울')
    page.select_option('#bookDistrict', '강남구')
    page.fill('#bookAddress', '대치동 123-4')
    page.tap('#bookSyms [data-val="뇌졸중·편마비"]')
    page.tap('[data-next="1"]')
    page.wait_for_timeout(300)
    page.tap('#bookDates .date-chip')
    page.tap('#bookSlots .slot:not([disabled])')
    page.tap('[data-next="2"]')
    page.wait_for_timeout(300)
    page.tap('#passList [data-pass="p8"]')
    page.wait_for_timeout(3200)  # toast clear
    page.screenshot(path=OUT + "/v5_booking_pay.png")
    page.tap('[data-next="3"]')
    page.wait_for_timeout(300)
    page.fill('#bookName', '김순자')
    page.fill('#bookPhone', '01012345678')
    page.tap('#payMethods [data-pay="카카오페이"]')
    page.check('#bookAgree')
    page.wait_for_timeout(400)
    page.screenshot(path=OUT + "/v5_booking_pay2.png")
    b.close()
print("shots done")
