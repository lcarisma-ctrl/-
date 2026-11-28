"""v11 감사용: 주요 화면의 실제 계산값(패딩·간격·폰트)을 뽑는다.

실행: python3 tests/_audit_spacing.py
"""
import json
import os

os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "file://" + os.path.join(ROOT, "index.html")

JS = r"""
(sel) => {
  const el = document.querySelector(sel);
  if (!el) return null;
  const c = getComputedStyle(el);
  const r = el.getBoundingClientRect();
  return {
    sel,
    box: [Math.round(r.width), Math.round(r.height)],
    pad: c.padding, margin: c.margin, gap: c.gap,
    font: c.fontSize + '/' + c.lineHeight + '/' + c.letterSpacing + ' w' + c.fontWeight,
    radius: c.borderRadius, shadow: (c.boxShadow || '').slice(0, 60),
    border: c.borderWidth + ' ' + c.borderColor
  };
}
"""

TARGETS = [
    "#appHeader", ".screen.is-active", ".home-notice", ".home-body",
    ".home-hero", ".hh-greet", ".hh-title", ".hh-cta", ".hh-guide",
    ".home-link-card", ".home-programs", ".hp-head", ".hp-title", ".hp-rail",
    ".home-program-card", ".hpc-name", ".hpc-top",
    "#screen-teachers .page-head h1", "#screen-teachers .page-head p",
    ".home-search", ".trust-strip", ".segmented", "#teacherList", ".teacher",
    ".t-name", ".t-meta", ".t-tags", ".t-foot",
    "#screen-booking .page-head h1", "#screen-booking .page-head p",
    ".booking-promo", ".bk-progress", ".wstep-title", ".wstep-sub",
    "#passList", ".pass", ".pass-name", ".pass-sub", ".pass-price",
    ".coupon-pick", ".coupon-chip", ".pass-note", ".wiz-nav",
    ".sum-card", ".sum-line", ".total", ".total b", ".discount-note",
    ".mp-top", ".mp-eyebrow", ".mp-title", ".mp-meta", ".mp-guide-link",
    ".mp-banner", ".mp-consult", ".mp-list", ".mp-row", ".mp-badge", ".mp-fine",
    ".sheet-scroll", ".sheet-title", ".sheet-desc", ".sheet-label", ".sheet-note",
    "#paySheet .sheet-title", "#paySheet .sheet-desc",
    "#notifSheet .sheet-title", "#couponSheet .sheet-desc", "#faqSheet .sheet-title",
    ".pm-list", ".pm-row", ".pm-row .pm-main b", ".pm-add", ".card-form",
    ".notif-list", ".notif", ".notif-main b", ".notif-main p",
    ".coupon-code", ".coupon-list", ".coupon-card", ".coupon-main b",
    ".faq-list", ".faq-item", ".faq-q", ".faq-a", ".terms-tabs", ".terms-body",
    ".booking-row", ".br-ics", ".dday-card", ".wallet-card", ".tabbar",
]


def run(page, label, shots=None):
    print("\n== " + label + " ==")
    for t in TARGETS:
        v = page.evaluate(JS, t)
        if not v:
            continue
        print("%-34s %-10s pad:%s gap:%s font:%s r:%s" % (v["sel"], str(v["box"]), v["pad"], v["gap"], v["font"], v["radius"]))


with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                        is_mobile=True, has_touch=True, locale="ko-KR")
    page = ctx.new_page()
    page.goto(URL)
    page.wait_for_function("window.__ttokttokBooted === true")
    page.wait_for_timeout(300)
    page.tap("#gateCta")
    page.wait_for_timeout(400)
    page.tap('[data-login="customer"]')
    page.wait_for_timeout(800)

    run(page, "HOME")

    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]')
    page.wait_for_timeout(400)
    run(page, "TEACHERS")

    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="mypage"]')
    page.wait_for_timeout(400)
    run(page, "MYPAGE")

    page.tap("#mpPayRow")
    page.wait_for_timeout(450)
    run(page, "PAY SHEET")
    page.tap("[data-pay-close]")
    page.wait_for_timeout(250)

    page.tap("#mpCouponRow")
    page.wait_for_timeout(450)
    run(page, "COUPON SHEET")
    page.tap("[data-coupon-close]")
    page.wait_for_timeout(250)

    page.tap("#mpFaqRow")
    page.wait_for_timeout(450)
    run(page, "FAQ SHEET")
    page.tap("[data-faq-close]")
    page.wait_for_timeout(250)

    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="booking"]')
    page.wait_for_timeout(300)
    page.tap('#provinceQuick [data-prov="서울"]')
    page.select_option("#bookDistrict", "강남구")
    page.fill("#bookAddress", "대치동 123-4, 101동 1203호")
    page.tap('#bookSyms [data-val="뇌졸중·편마비"]')
    page.tap('[data-next="1"]')
    page.wait_for_timeout(300)
    page.tap("#bookDates .date-chip")
    page.wait_for_timeout(120)
    page.tap("#bookSlots .slot:not([disabled])")
    page.tap('[data-next="2"]')
    page.wait_for_timeout(350)
    page.tap('#passList [data-pass="p8"]')
    page.wait_for_timeout(300)
    run(page, "BOOKING STEP3")
    page.tap('[data-next="3"]')
    page.wait_for_timeout(350)
    run(page, "BOOKING STEP4")
    b.close()
