"""v9 화면 컷: 일러스트 아바타 · 홈 카드 포인트 심볼 · 예약 완료(.ics) 확인용.

실행: python3 tests/_shots_v9.py  → preview/v9_home.png, v9_teachers.png,
     v9_teacher_sheet.png, v9_done.png
"""
import os
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright

ROOT = "/workspace/projects/ttokttok-app"
OUT = ROOT + "/preview"


def steady(page, ms=280):
    """토스트가 사라진 뒤에 찍는다."""
    try:
        page.wait_for_function("!document.querySelector('#toast').classList.contains('is-on')", timeout=3500)
    except Exception:
        pass
    page.wait_for_timeout(ms)


with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="ko-KR")
    page = ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
    page.goto("file://" + ROOT + "/index.html")
    page.wait_for_function("window.__ttokttokBooted === true")
    page.wait_for_timeout(300)
    page.tap("#gateCta")
    page.wait_for_timeout(500)
    page.tap('[data-login="customer"]')
    page.wait_for_timeout(1200)

    # 홈 (증상 카드 포인트 심볼)
    steady(page, 450)
    page.evaluate("window.scrollTo(0, 210)")
    steady(page, 400)
    page.screenshot(path=OUT + "/v9_home.png")

    # 선생님 목록 (일러스트 아바타)
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]')
    page.evaluate("window.scrollTo(0, 0)")
    steady(page, 600)
    page.screenshot(path=OUT + "/v9_teachers.png")

    # 선생님 상세 시트
    page.tap("#teacherList .teacher")
    page.wait_for_timeout(800)
    page.screenshot(path=OUT + "/v9_teacher_sheet.png")
    page.tap("[data-sheet-close]")
    page.wait_for_timeout(400)

    # 예약 완료 + 캘린더 버튼
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="booking"]')
    page.wait_for_timeout(300)
    page.tap('#provinceQuick [data-prov="서울"]')
    page.select_option("#bookDistrict", "강남구")
    page.fill("#bookAddress", "대치동 123-4, 101동 1203호")
    page.tap('#bookSyms [data-val="뇌졸중·편마비"]')
    page.tap('[data-next="1"]')
    page.wait_for_timeout(280)
    page.tap("#bookDates .date-chip")
    page.wait_for_timeout(150)
    page.tap("#bookSlots .slot:not([disabled])")
    page.tap('[data-next="2"]')
    page.wait_for_timeout(280)
    page.tap('#passList [data-pass="eval"]')
    page.tap('[data-next="3"]')
    page.wait_for_timeout(280)
    page.fill("#bookName", "김순자")
    page.fill("#bookPhone", "01012345678")
    page.check("#bookAgree")
    page.tap("#payBtn")
    page.wait_for_timeout(1700)
    steady(page, 700)
    page.screenshot(path=OUT + "/v9_done.png")

    ics = page.evaluate("window.__ttokttokIcs || null")
    print("ICS name:", ics and ics.get("name"))
    print("ICS head:", (ics and ics.get("text") or "")[:220].replace("\r\n", " | "))
    print("JS errors:", errs[:3] if errs else "none")
    b.close()
