#!/usr/bin/env python3
"""v16 라이브 실브라우저 확인: 부팅·정책 모델·FAQ 서비스·환불 탭·초안 고지·취소 시트 견적."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")
from playwright.sync_api import sync_playwright

URL = "https://lcarisma-ctrl.github.io/-/?v=16"
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
    info = page.evaluate("""() => {
      const m = window.__ttokttokModel;
      return {
        version: document.querySelector('meta[name="app-version"]').content,
        booted: window.__ttokttokBooted === true,
        policy: m.policyVersion,
        draft: m.policyMeta.isDraft,
        draftLabel: m.policyMeta.draftLabel,
        reviewItems: m.policyMeta.reviewItems.map(r => r.code),
        q24: m.calculateRefundQuote(85000, 24, 'customer').refund,
        q23: m.calculateRefundQuote(85000, 5, 'customer').refund,
        qPast: m.calculateRefundQuote(85000, -1, 'customer').refund,
        qPass: m.calculateRefundQuote(592000, 48, 'customer', { isPass: true }).restoreSessions,
        passRefund: m.calculatePassRefund({ paidAmount: 592000, totalSessions: 8, usedSessions: 3 }).refund,
        plans: m.passes().map(x => x.price).join(',')
      };
    }""")
    print(info)
    print("pageerrors", errs)
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="mypage"]')
    page.wait_for_timeout(350)
    page.tap("#mpFaqRow")
    page.wait_for_timeout(450)
    print("draft note:", "법률 자문이 아닌 운영 기준 초안" in page.inner_text("#faqDraftNote"))
    page.tap('#faqTabs [data-terms="policy"]')
    page.wait_for_timeout(350)
    body = page.inner_text("#termsBody")
    print("policy sections:", all(k in body for k in ["서비스 이용 기준", "비용 안내", "취소·변경·환불 규정"]))
    print("disclaimer in body:", "법률 자문이 아닙니다" in body)
    page.screenshot(path=os.path.join(SHOT, "live_v16_faq_policy.png"))
    page.tap("[data-faq-close]")
    page.wait_for_timeout(300)
    page.tap("#mpBookLink")
    page.wait_for_timeout(450)
    page.tap("#bookingList [data-manage]")
    page.wait_for_timeout(400)
    page.tap("[data-manage-cancel]")
    page.wait_for_timeout(400)
    cancel = page.inner_text("#manageSheetBody")
    print("cancel quote + draft:", "예상 환불" in cancel and "법률 자문이 아닌 운영 기준 초안" in cancel)
    page.screenshot(path=os.path.join(SHOT, "live_v16_cancel_quote.png"))
    browser.close()
print("LIVE OK")
