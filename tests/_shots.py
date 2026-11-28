"""v4 화면 컷: 시작 화면(게이트) · 시트 · 서비스 지역 · 주요 플로우.

실행: python3 tests/_shots.py  → preview/v4_*.png
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
    page.screenshot(path=OUT + "/v4_gate.png")
    print("gate overflow:",
          page.eval_on_selector("#entryGate", "el => el.scrollHeight - el.clientHeight"))

    # 시작 화면 시트 (휴대폰 번호 + 역할)
    page.tap("#gateCta")
    page.wait_for_timeout(500)
    page.screenshot(path=OUT + "/v4_gate_sheet.png")
    page.tap("[data-gate-close]")
    page.wait_for_timeout(350)

    # 서비스 지역 확인 (가능 / 준비 중)
    page.tap("#gateRegionLink")
    page.wait_for_timeout(500)
    page.screenshot(path=OUT + "/v4_region_1.png")
    page.select_option("#regionProvince", "서울")
    page.select_option("#regionDistrict", "강남구")
    page.wait_for_timeout(300)
    page.screenshot(path=OUT + "/v4_region_ok.png")
    page.select_option("#regionProvince", "경남")
    page.select_option("#regionDistrict", "창원시")
    page.wait_for_timeout(300)
    page.screenshot(path=OUT + "/v4_region_wait.png")

    # 고객 시작
    page.tap("[data-region-close]")
    page.wait_for_timeout(300)
    page.tap("#gateCta")
    page.wait_for_timeout(450)
    page.tap('[data-login="customer"]')
    page.wait_for_timeout(500)
    page.wait_for_timeout(2200)  # let toast clear
    page.screenshot(path=OUT + "/v4_home.png")

    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]')
    page.wait_for_timeout(500)
    page.screenshot(path=OUT + "/v4_teachers.png")
    page.tap('#teacherList .teacher')
    page.wait_for_timeout(500)
    page.screenshot(path=OUT + "/v4_sheet.png")
    page.tap('#sheetChat')
    page.wait_for_timeout(400)
    page.fill('#chatInput', '방문 시간을 바꿀 수 있나요?')
    page.tap('.chat-send')
    page.wait_for_timeout(1100)
    page.screenshot(path=OUT + "/v4_chat.png")
    page.tap('[data-chat-close]')
    page.wait_for_timeout(300)
    page.tap('#teacherList .teacher')
    page.wait_for_timeout(350)
    page.tap('#sheetBook')
    page.wait_for_timeout(400)
    page.select_option('#bookProvince', '서울')
    page.select_option('#bookDistrict', '강남구')
    page.fill('#bookAddress', '대치동 123-4')
    page.tap('#bookSyms [data-val="뇌졸중·편마비"]')
    page.screenshot(path=OUT + "/v4_booking1.png")
    page.tap('[data-next="1"]')
    page.wait_for_timeout(300)
    page.tap('#bookDates .date-chip')
    page.tap('#bookSlots .slot:not([disabled])')
    page.wait_for_timeout(200)
    page.screenshot(path=OUT + "/v4_booking2.png")
    page.tap('[data-next="2"]')
    page.wait_for_timeout(300)
    page.tap('#passList [data-pass="p8"]')
    page.wait_for_timeout(3200)  # let toast clear
    page.screenshot(path=OUT + "/v4_booking3.png")
    page.tap('[data-next="3"]')
    page.wait_for_timeout(300)
    page.fill('#bookName', '김순자')
    page.fill('#bookPhone', '01012345678')
    page.tap('#payMethods [data-pay="카카오페이"]')
    page.check('#bookAgree')
    page.screenshot(path=OUT + "/v4_booking4.png")
    page.tap('#payBtn')
    page.wait_for_timeout(1400)
    page.screenshot(path=OUT + "/v4_done.png")
    page.tap('#doneMypage')
    page.wait_for_timeout(600)
    page.screenshot(path=OUT + "/v4_mypage.png")
    page.tap('#rolePill')
    page.wait_for_timeout(500)
    page.screenshot(path=OUT + "/v4_tp_home.png")
    b.close()
print("shots done")
