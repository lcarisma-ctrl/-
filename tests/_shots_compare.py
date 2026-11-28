"""같은 화면을 버전 태그로 찍어 전후 비교한다.

실행:
  python3 tests/_shots_compare.py v10   → preview/v10_home.png, v10_teachers.png,
                                          v10_booking3.png, v10_mypage.png,
                                          v10_notif.png, v10_coupon.png,
                                          v10_pay.png, v10_faq.png, v10_pay_discount.png
  python3 tests/_shots_compare.py v11   → preview/v11_*.png (같은 순서·같은 상태)
"""
import os
import sys

os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright

TAG = (sys.argv[1] if len(sys.argv) > 1 else "v10").strip()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "preview")


def steady(page, ms=300):
    try:
        page.wait_for_function("!document.querySelector('#toast').classList.contains('is-on')", timeout=3500)
    except Exception:
        pass
    page.wait_for_timeout(ms)


def shot(page, name):
    page.screenshot(path=os.path.join(OUT, TAG + "_" + name + ".png"))
    print("  · preview/" + TAG + "_" + name + ".png")


with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                        is_mobile=True, has_touch=True, locale="ko-KR")
    page = ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
    page.goto("file://" + os.path.join(ROOT, "index.html"))
    page.wait_for_function("window.__ttokttokBooted === true")
    page.wait_for_timeout(300)
    page.tap("#gateCta")
    page.wait_for_timeout(450)
    page.tap('[data-login="customer"]')
    page.wait_for_timeout(1100)

    # 1) 홈 (첫 화면)
    page.evaluate("window.scrollTo(0, 0)")
    steady(page, 450)
    shot(page, "home")

    # 2) 선생님 목록
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]')
    page.evaluate("window.scrollTo(0, 0)")
    steady(page, 550)
    shot(page, "teachers")

    # 3) 내 정보 (리스트 여백 확인)
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="mypage"]')
    page.wait_for_timeout(500)
    shot(page, "mypage")

    # 4) 쿠폰함 (코드 등록 후 3장)
    page.tap("#mpCouponRow")
    page.wait_for_timeout(500)
    steady(page, 350)
    shot(page, "coupon_before")
    page.fill("#couponCode", "WELCOME")
    page.tap("#couponRegister")
    steady(page, 400)
    shot(page, "coupon")
    page.tap("[data-coupon-close]")
    page.wait_for_timeout(300)

    # 5) 결제수단 관리
    page.tap("#mpPayRow")
    page.wait_for_timeout(500)
    steady(page, 350)
    shot(page, "pay")
    page.tap("#pmAddBtn")
    page.wait_for_timeout(350)
    shot(page, "pay_form")
    page.tap("#cardCancel")
    page.wait_for_timeout(250)
    page.tap("[data-pay-close]")
    page.wait_for_timeout(300)

    # 6) FAQ
    page.tap("#mpFaqRow")
    page.wait_for_timeout(500)
    steady(page, 350)
    shot(page, "faq_closed")
    page.tap('#faqList [data-faq="faq-refund"]')
    page.wait_for_timeout(400)
    shot(page, "faq")
    page.tap("[data-faq-close]")
    page.wait_for_timeout(300)

    # 7) 알림함 (홈 벨)
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="home"]')
    page.wait_for_timeout(350)
    page.tap("#btnNotif")
    page.wait_for_timeout(550)
    steady(page, 300)
    shot(page, "notif")
    page.tap("[data-notif-close]")
    page.wait_for_timeout(300)

    # 8) 예약 3단계 (이용권 + 쿠폰 선택)
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="booking"]')
    page.wait_for_timeout(300)
    page.tap('#provinceQuick [data-prov="서울"]')
    page.select_option("#bookDistrict", "강남구")
    page.fill("#bookAddress", "대치동 123-4, 101동 1203호")
    page.tap('#bookSyms [data-val="뇌졸중·편마비"]')
    page.tap('[data-next="1"]')
    page.wait_for_timeout(300)
    page.tap("#bookDates .date-chip")
    page.wait_for_timeout(150)
    page.tap("#bookSlots .slot:not([disabled])")
    page.tap('[data-next="2"]')
    page.wait_for_timeout(350)
    page.tap('#passList [data-pass="p8"]')
    page.wait_for_timeout(350)
    shot(page, "booking3")

    # 합계 바가 있는 3단계 하단(쿠폰 칩 포함)
    page.evaluate("window.scrollTo(0, 240)")
    page.wait_for_timeout(350)
    shot(page, "booking3_scrolled")
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(200)

    # 9) 예약 4단계 (쿠폰 할인 반영)
    page.tap('#couponChips [data-coupon-pick="cp-10000"]')
    page.wait_for_timeout(300)
    page.tap('[data-next="3"]')
    page.wait_for_timeout(400)
    steady(page, 500)
    shot(page, "pay_discount")
    page.evaluate("window.scrollTo(0, 420)")
    page.wait_for_timeout(350)
    shot(page, "pay_discount_scrolled")

    print("JS errors:", errs[:3] if errs else "none")
    b.close()
