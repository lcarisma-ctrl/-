#!/usr/bin/env python3
"""v20 라이브 실브라우저 확인: 부팅·버전·주간 보호자 리포트·4주 재평가·2분 일지·안전 시트."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")
from playwright.sync_api import sync_playwright

URL = "https://lcarisma-ctrl.github.io/-/?v=20"
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
    print(page.evaluate("""() => {
      const m = window.__ttokttokModel;
      const w = m.weeklyReport();
      return {
        version: document.querySelector('meta[name="app-version"]').content,
        booted: window.__ttokttokBooted === true,
        visitLogVersion: m.visitLogVersion,
        quickScale: m.quickScale.length,
        quickActivities: m.quickActivities.length,
        weeklyRounds: w ? w.rounds : null,
        weeklyText: w ? w.text.split('\\n').slice(0, 4) : null,
        customerReeval: m.customerReeval().total,
        safety: m.safetyContacts.map((c) => c.tel)
      };
    }"""))
    page.eval_on_selector('.tabbar[data-mode="customer"] .tabbtn[data-tab="journal"]', "el => el.click()")
    page.wait_for_timeout(500)
    print("weekly card:", page.inner_text("#weeklyBody").replace("\n", " | "))
    page.screenshot(path=os.path.join(SHOT, "live_v20_guardian_weekly.png"))
    page.tap("#weeklyOpen")
    page.wait_for_timeout(500)
    print("weekly sheet open:", page.eval_on_selector("#weeklySheet", "el => el.classList.contains('is-open')"))
    page.screenshot(path=os.path.join(SHOT, "live_v20_weekly_sheet.png"))
    page.tap("#weeklySheet [data-weekly-close]")
    page.wait_for_timeout(300)
    page.eval_on_selector('#screen-journal [data-safety-open]', "el => el.click()")
    page.wait_for_timeout(400)
    print("safety open:", page.eval_on_selector("#safetySheet", "el => el.classList.contains('is-open')"),
          "contacts:", page.eval_on_selector_all("#safetyContacts [data-safety-tel]", "els => els.length"),
          "steps:", page.eval_on_selector_all("#safetySteps .step-item", "els => els.length"))
    page.screenshot(path=os.path.join(SHOT, "live_v20_safety.png"))
    page.tap("#safetySheet [data-safety-close]")
    page.wait_for_timeout(250)
    page.eval_on_selector('[data-login="therapist"]', "el => el.click()")
    page.wait_for_timeout(400)
    page.eval_on_selector('.tabbar[data-mode="therapist"] .tabbtn[data-tab="tp-journal"]', "el => el.click()")
    page.wait_for_timeout(400)
    print("quick chips:", page.eval_on_selector_all("#qlPainChips [data-ql-pain]", "els => els.length"),
          page.eval_on_selector_all("#qlActChips [data-ql-act]", "els => els.length"))
    page.tap('#qlPainChips [data-ql-pain="2"]')
    page.tap('#qlCondChips [data-ql-cond="4"]')
    page.tap('#qlActChips [data-ql-act="walk"]')
    page.wait_for_timeout(250)
    print("progress:", page.inner_text("#qlProgress"))
    page.screenshot(path=os.path.join(SHOT, "live_v20_quick_journal.png"))
    page.eval_on_selector('.tabbar[data-mode="therapist"] .tabbtn[data-tab="tp-schedule"]', "el => el.click()")
    page.wait_for_timeout(400)
    print("visit buttons:", page.eval_on_selector_all("#tpScheduleList [data-tp-visit-start]", "els => els.length"))
    print("errors:", errs[:3])
    browser.close()
