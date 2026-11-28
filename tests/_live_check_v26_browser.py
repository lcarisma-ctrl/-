#!/usr/bin/env python3
"""똑똑쌤 v26 라이브(GitHub Pages) 실브라우저 점검 — 선생님 정산 명세서·월별 리포트.
실행: python3 tests/_live_check_v26_browser.py
"""
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")
from playwright.sync_api import sync_playwright

LIVE = "https://lcarisma-ctrl.github.io/-/?v=26"
SHOT = os.path.join(ROOT, "preview")
passed, failed, failures = 0, 0, []


def ok(name, cond, extra=""):
    global passed, failed
    if cond:
        passed += 1
        print("  ✓ " + name)
    else:
        failed += 1
        failures.append(name + (" :: " + str(extra) if extra else ""))
        print("  ✗ " + name + (" :: " + str(extra) if extra else ""))


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--font-render-hinting=none"])
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                                  is_mobile=True, has_touch=True, locale="ko-KR",
                                  user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
        page.goto(LIVE, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)

        def overflow(state):
            m = page.evaluate("() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})")
            return m["sw"] <= m["cw"] + 1, "%s: %d/%d" % (state, m["sw"], m["cw"])

        ok("v26 라이브 앱 버전", page.evaluate("() => document.querySelector('meta[name=app-version]').content") == "v26")
        ok("v26 라이브 부팅 오류 0", not errors, errors[:3])
        ok("v26 명세서 모델 노출", page.evaluate("() => window.__ttokttokModel.statementVersion") == "v26" and
           abs(page.evaluate("() => window.__ttokttokModel.withholdingRate") - 0.033) < 1e-9)

        page.eval_on_selector('[data-login="therapist"]', "el => el.click()")
        page.wait_for_timeout(400)
        ok("v26 파트너 홈 정산 링크", page.is_visible('#tpSettle [data-tab="tp-settle"]'))
        page.tap('#tpSettle [data-tab="tp-settle"]')
        page.wait_for_timeout(500)
        ok("v26 정산 탭 화면", page.eval_on_selector(".screen.is-active", "el => el.id") == "screen-tp-settle")
        okk, why = overflow("settle")
        ok("v26 정산 화면 390px 넘침 없음", okk, why)
        ok("v26 월 칩 2개·11월 선택", page.eval_on_selector_all("#tpsMonths [data-stl-month]", "els => els.length") == 2 and
           page.eval_on_selector('#tpsMonths [data-stl-month="2026-11"]', "el => el.classList.contains('is-on')"))
        summary = page.eval_on_selector("#tpsSummary", "el => el.textContent.replace(/\\s+/g, ' ').trim()")
        ok("v26 월 요약 수치", "980,000" in summary and "지급완료 7건" in summary and "실수령 예상" in summary and "947,660원" in summary, summary[:110])
        ok("v26 회차별 14건", page.eval_on_selector_all("#tpsRows [data-stl-row]", "els => els.length") == 14)
        page.screenshot(path=os.path.join(SHOT, "live_v26_settle_390.png"))
        page.tap('#tpsMonths [data-stl-month="2026-10"]')
        page.wait_for_timeout(400)
        ok("v26 10월 전환 12건", page.eval_on_selector_all("#tpsRows [data-stl-row]", "els => els.length") == 12)
        page.tap('#tpsMonths [data-stl-month="2026-11"]')
        page.wait_for_timeout(400)
        page.tap('#tpsScreen [data-stl-preview]')
        page.wait_for_timeout(600)
        ok("v26 미리보기 시트", page.eval_on_selector("#settlementPrintSheet", "el => el.classList.contains('is-open')") and
           "똑똑쌤 정산 명세서" in page.eval_on_selector("#settlementPrintBody", "el => el.textContent"))
        page.screenshot(path=os.path.join(SHOT, "live_v26_print_sheet.png"))
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        page.set_viewport_size({"width": 320, "height": 568})
        page.wait_for_timeout(350)
        okk, why = overflow("settle/320")
        ok("v26 정산 화면 320px 넘침 없음", okk, why)
        page.screenshot(path=os.path.join(SHOT, "live_v26_320_settle.png"))
        ok("v26 라이브 오류 0", not errors, errors[:3])
        browser.close()

    print("\nRESULT: %d passed, %d failed" % (passed, failed))
    if failures:
        for f in failures:
            print(" - " + f)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(2)
