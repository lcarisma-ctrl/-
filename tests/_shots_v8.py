"""v8 화면 컷: 홈 · 보호자 공유 리포트 · 매칭 트래커 확인용.

실행: python3 tests/_shots_v8.py  → preview/v8_home.png, v8_journal.png,
     v8_report_sheet.png, v8_report_sheet_bottom.png, v8_tracker.png, v8_done.png
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

    # 홈
    steady(page, 450)
    page.screenshot(path=OUT + "/v8_home.png")

    # 일지 (리포트 진입 카드)
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="journal"]')
    steady(page, 500)
    page.evaluate("window.scrollTo(0, 560)")
    steady(page, 450)
    page.screenshot(path=OUT + "/v8_journal.png")

    # 보호자 공유 리포트 시트
    page.tap("#reportOpen")
    page.wait_for_timeout(900)
    page.screenshot(path=OUT + "/v8_report_sheet.png")
    page.eval_on_selector("#reportSheet .sheet-scroll", "el => { el.scrollTop = el.scrollHeight; }")
    page.wait_for_timeout(600)
    page.screenshot(path=OUT + "/v8_report_sheet_bottom.png")
    page.tap("#reportSheet [data-report-close]")
    page.wait_for_timeout(400)

    # 내 예약 · 이용권 시트 → 매칭 트래커
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="mypage"]')
    page.wait_for_timeout(350)
    page.tap("#mpBookLink")
    steady(page, 600)
    page.screenshot(path=OUT + "/v8_tracker.png")

    page.tap("[data-account-close]")
    page.wait_for_timeout(300)

    # 예약 완료 화면 트래커
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
    page.wait_for_timeout(1600)
    steady(page, 500)
    page.screenshot(path=OUT + "/v8_done.png")

    print("JS errors:", errs[:3] if errs else "none")
    b.close()
