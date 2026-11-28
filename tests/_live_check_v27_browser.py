#!/usr/bin/env python3
"""똑똑쌤 v27 라이브(GitHub Pages) 실브라우저 점검 — 알림·리마인드 센터.
실행: python3 tests/_live_check_v27_browser.py
"""
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")
from playwright.sync_api import sync_playwright

LIVE = "https://lcarisma-ctrl.github.io/-/?v=27"
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

        ok("v27 라이브 앱 버전", page.evaluate("() => document.querySelector('meta[name=app-version]').content") == "v27")
        ok("v27 라이브 부팅 오류 0", not errors, errors[:3])
        ok("v27 리마인드 큐 모델", page.evaluate("() => window.__ttokttokModel.reminderQueueVersion") == "v27" and
           page.evaluate("() => window.__ttokttokModel.reminderCategories.length") == 4)

        # ── 보호자 알림함: 분류 칩·문구 미리보기
        page.eval_on_selector('[data-login="customer"]', "el => el.click()")
        page.wait_for_timeout(400)
        page.tap("#btnNotif")
        page.wait_for_timeout(500)
        chips = page.evaluate("() => window.__ttokttokModel.notifScreenState().chips")
        ok("v27 보호자 알림함 카테고리 칩 4개", len(chips) == 4, chips)
        ok("v27 칩 안 읽음 수", any(c["text"].startswith("전체") for c in chips) and
           any(c["key"] == "visit" for c in chips) and any(c["key"] == "report" for c in chips) and
           any(c["key"] == "ops" for c in chips), [c["text"] for c in chips])
        okk, why = overflow("notif")
        ok("v27 알림 시트 390px 넘침 없음", okk, why)
        page.screenshot(path=os.path.join(SHOT, "live_v27_notif_chips.png"))
        page.tap('#notifChips [data-notif-cat="report"]')
        page.wait_for_timeout(320)
        ok("v27 리포트/재평가 필터 1건", page.evaluate("() => window.__ttokttokModel.notifScreenState().rows") == 1)
        page.tap('#notifChips [data-notif-cat="all"]')
        page.wait_for_timeout(300)
        page.tap('#notifList .notif')
        page.wait_for_timeout(500)
        pv = page.evaluate("() => window.__ttokttokModel.notifPreviewInfo()")
        ok("v27 알림 클릭 → 문구 미리보기", bool(pv) and pv["open"] is True and len(pv["text"] or "") > 40, pv and pv.get("title"))
        sheet_text = page.eval_on_selector("#notifPreviewSheet", "el => el.textContent.replace(/\\s+/g, ' ')")
        ok("v27 로컬 미리보기 고지", "실제 발송 전 로컬 미리보기" in sheet_text and "발송되지 않습니다" in sheet_text)
        page.screenshot(path=os.path.join(SHOT, "live_v27_notif_preview.png"))
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        # ── 선생님 알림함 전체 보기 시트
        page.evaluate("() => document.getElementById('entryGate').classList.add('is-open')")
        page.wait_for_timeout(150)
        page.eval_on_selector('[data-login="therapist"]', "el => el.click()")
        page.wait_for_timeout(500)
        ok("v27 선생님 알림함 칩 4개", page.evaluate("() => window.__ttokttokModel.tpNotifState().inlineChips") == 4)
        page.tap("#tpNotifSec [data-tp-noti-open]")
        page.wait_for_timeout(450)
        ok("v27 선생님 알림함 전체 보기 시트", page.evaluate("() => window.__ttokttokModel.tpNotifState().sheetOpen") is True)
        page.screenshot(path=os.path.join(SHOT, "live_v27_tp_noti_sheet.png"))
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        # ── 운영자 리마인드 미리보기
        page.evaluate("() => document.getElementById('entryGate').classList.add('is-open')")
        page.wait_for_timeout(150)
        page.eval_on_selector('[data-login="admin"]', "el => el.click()")
        page.wait_for_timeout(500)
        ad = page.evaluate("() => window.__ttokttokModel.adminReminderState()")
        ok("v27 운영자 리마인드 보드", ad["total"] >= 3 and len(ad["cards"]) == ad["total"], ad["total"])
        ok("v27 발송 안 함 고지", "실제 문자·알림톡 발송은 하지 않습니다" in ad["noticeText"])
        page.evaluate("() => document.getElementById('adminReminderSec').scrollIntoView({block:'start'})")
        page.wait_for_timeout(400)
        page.screenshot(path=os.path.join(SHOT, "live_v27_admin_reminders.png"))
        page.tap("#adminReminderCopyAll")
        page.wait_for_timeout(350)
        hook = page.evaluate("() => window.__ttokttokReminderCopy || {}")
        ok("v27 전체 문구 복사", "[똑똑쌤 오늘 발송할 리마인드]" in (hook.get("text") or ""), (hook.get("text") or "")[:50])
        page.set_viewport_size({"width": 320, "height": 568})
        page.wait_for_timeout(400)
        okk, why = overflow("adminReminder/320")
        ok("v27 운영자 보드 320px 넘침 없음", okk, why)
        page.screenshot(path=os.path.join(SHOT, "live_v27_320_admin_reminders.png"))
        ok("v27 라이브 오류 0", not errors, errors[:3])
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
