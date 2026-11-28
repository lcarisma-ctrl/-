"""v7 화면 컷: 선생님 찾기 · 회복 일지 · 예약 · 파트너 · 관리자 톤 확인용.

실행: python3 tests/_shots_v7.py  → preview/v7_*.png
"""
import os
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright

ROOT = "/workspace/projects/ttokttok-app"
OUT = ROOT + "/preview"


def steady(page, ms=280):
    """토스트가 사라진 뒤에 찍는다 (스크린샷이 가리지 않도록)."""
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
    page.wait_for_timeout(1500)

    # 선생님 찾기 (하트 2개 찜한 상태)
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]')
    page.wait_for_timeout(500)
    favs = page.query_selector_all("#teacherList [data-fav]")
    if len(favs) >= 2:
        favs[0].tap()
        page.wait_for_timeout(300)
        page.query_selector_all("#teacherList [data-fav]")[1].tap()
        page.wait_for_timeout(500)
    steady(page, 400)
    page.screenshot(path=OUT + "/v7_teachers.png")

    page.tap("#favFilter")
    steady(page, 400)
    page.screenshot(path=OUT + "/v7_teachers_fav.png")
    page.tap("#favFilter")
    steady(page, 300)

    # 회복 일지 (D-day + 타임라인)
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="journal"]')
    steady(page, 500)
    page.screenshot(path=OUT + "/v7_journal.png")
    page.evaluate("window.scrollTo(0, 620)")
    steady(page, 450)
    page.screenshot(path=OUT + "/v7_journal_timeline.png")

    # 예약 1단계 / 3단계
    page.evaluate("window.scrollTo(0, 0)")
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="booking"]')
    steady(page, 500)
    page.screenshot(path=OUT + "/v7_booking.png")
    page.tap('#provinceQuick [data-prov="서울"]')
    page.wait_for_timeout(200)
    page.select_option("#bookDistrict", "강남구")
    page.fill("#bookAddress", "대치동 123-4, 101동 1203호")
    page.tap('#bookSyms [data-val="뇌졸중·편마비"]')
    page.tap('[data-next="1"]')
    steady(page, 450)
    page.screenshot(path=OUT + "/v7_booking2.png")
    page.tap("#bookDates .date-chip")
    page.wait_for_timeout(150)
    page.tap("#bookSlots .slot:not([disabled])")
    page.tap('[data-next="2"]')
    steady(page, 450)
    page.tap('#passList [data-pass="p8"]')
    steady(page, 450)
    page.screenshot(path=OUT + "/v7_booking3.png")

    # 내 예약 시트 (D-day 카드)
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="mypage"]')
    steady(page, 600)
    page.screenshot(path=OUT + "/v7_mypage.png")
    page.tap("#mpBookLink")
    steady(page, 600)
    page.screenshot(path=OUT + "/v7_account_dday.png")
    page.tap("[data-account-close]")
    page.wait_for_timeout(350)

    # 파트너 모드
    page.tap("#mpRoleRow")
    page.wait_for_timeout(400)
    page.tap('#roleSheet [data-role-switch="therapist"]')
    steady(page, 700)
    page.screenshot(path=OUT + "/v7_partner.png")
    page.tap('.tabbar[data-mode="therapist"] .tabbtn[data-tab="tp-schedule"]')
    steady(page, 500)
    page.screenshot(path=OUT + "/v7_partner_schedule.png")

    # 관리자 콘솔
    page.tap("#rolePill")
    page.wait_for_timeout(450)
    page.eval_on_selector("[data-admin-open]", "el => el.click()")
    steady(page, 700)
    page.screenshot(path=OUT + "/v7_admin.png")

    print("js errors:", errs[:5])
    b.close()
print("shots done")
