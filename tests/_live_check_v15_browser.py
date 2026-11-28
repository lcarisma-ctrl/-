#!/usr/bin/env python3
"""v15 라이브 실브라우저 확인: 부팅·검증 모델·카드 배지·상세 시트 마스킹."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")
from playwright.sync_api import sync_playwright

URL = "https://lcarisma-ctrl.github.io/-/?v=15"
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
        verification: m.verificationVersion,
        steps: m.verificationSteps.map(s => s.key).join(','),
        maskLic: m.maskLicenseNo('11-2019-004821'),
        maskName: m.maskTeacherName('박서준'),
        parkBadges: m.getVerificationBadges('park').map(b => b.label),
        leeBadges: m.getVerificationBadges('lee').map(b => b.label),
        cards: document.querySelectorAll('#teacherList .teacher').length,
        chips: Array.from(document.querySelectorAll('#teacherList .lic')).map(e => e.textContent.replace(/\\s+/g,' ').trim())
      };
    }""")
    print(info)
    print("pageerrors", errs)
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]')
    page.wait_for_timeout(400)
    page.screenshot(path=os.path.join(SHOT, "live_v15_teachers.png"))
    page.tap('#teacherList [data-teacher="park"]')
    page.wait_for_timeout(500)
    sheet = page.inner_text("#teacherSheetBody")
    print("sheet masked:", "제○○-○○○○호" in sheet, "raw hidden:", "11-2008-004312" not in sheet)
    page.screenshot(path=os.path.join(SHOT, "live_v15_sheet.png"))
    page.tap("[data-sheet-close]")
    page.wait_for_timeout(300)
    page.tap('#teacherList [data-teacher="lee"]')
    page.wait_for_timeout(500)
    lee = page.inner_text("#teacherSheetBody")
    print("lee badges:", page.eval_on_selector_all("#teacherSheet .h-tags .tag", "els => els.map(e => e.textContent.trim())"))
    print("lee pending note:", "경력 확인은 진행 중이에요" in lee)
    page.screenshot(path=os.path.join(SHOT, "live_v15_sheet_lee.png"))
    browser.close()
print("LIVE OK")
