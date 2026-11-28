import os, sys, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")
from playwright.sync_api import sync_playwright

URL = "https://lcarisma-ctrl.github.io/-/?v=32"
SHOT = os.path.join(ROOT, "preview")
EMPTY = json.dumps({"passes": [], "bookings": [], "receipts": [], "sessions": [], "myReviews": [], "profile": {"name": "현수"}}, ensure_ascii=False)
passed, failed, fails = 0, 0, []


def ok(name, cond, extra=""):
    global passed, failed
    if cond:
        passed += 1
        print("  ✓ " + name)
    else:
        failed += 1
        fails.append(name + (" :: " + str(extra) if extra else ""))
        print("  ✗ " + name + ((" :: " + str(extra)) if extra else ""))


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files"])
        for (w, h, mob) in [(320, 568, True), (375, 812, True), (1280, 800, False)]:
            ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if mob else 1,
                                      is_mobile=mob, has_touch=mob, locale="ko-KR")
            ctx.add_init_script("try{localStorage.setItem('ttokttok_account_v3', %s);}catch(e){}" % json.dumps(EMPTY))
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
            page.goto(URL, wait_until="load")
            page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
            page.wait_for_timeout(500)
            ok("live %d 앱 버전 v32" % w, page.evaluate("() => document.querySelector('meta[name=app-version]').content") == "v32")
            ok("live %d 공통 UI 훅" % w, page.evaluate("() => !!window.__ttokttokV32 && window.__ttokttokV32.version") == "v32")
            page.eval_on_selector('[data-login="customer"]', "el => el.click()")
            page.wait_for_timeout(320)
            page.eval_on_selector('.tabbar[data-mode="customer"] .tabbtn[data-tab="mypage"]', "el => el.click()")
            page.wait_for_timeout(320)
            page.eval_on_selector("#homeTicketBtn", "el => el.click()")
            page.wait_for_timeout(380)
            empty = page.evaluate("""() => [...document.querySelectorAll('.empty[data-empty]')].map(el => ({
                key: el.getAttribute('data-empty'), cta: !!el.querySelector('.btn'), desc: !!el.querySelector('p') }))""")
            keys = [x["key"] for x in empty]
            ok("live %d 빈 상태 4곳 통일" % w, all(k in keys for k in ("wallet-passes", "booking-list", "receipts", "journal-timeline")), keys)
            ok("live %d 빈 상태 설명·CTA" % w, len(empty) >= 4 and all(x["cta"] and x["desc"] for x in empty))
            ok("live %d 빈 상태 감사 위반 0" % w, page.evaluate("() => window.__ttokttokUI.audit().length") == 0)
            m = page.evaluate("() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})")
            ok("live %d 가로 넘침 없음" % w, m["sw"] <= m["cw"] + 1, m)
            ok("live %d JS 오류 없음" % w, not errors, errors[:2])
            page.screenshot(path=os.path.join(SHOT, "live_v32_%d_empty_sheet.png" % w))
            # 빈 상태 CTA → 예약 화면
            page.eval_on_selector('[data-empty="booking-list"] [data-go="booking"]', "el => el.click()")
            page.wait_for_timeout(3200)
            ok("live %d 빈 상태 CTA → 예약 화면" % w, page.evaluate("() => document.querySelector('#screen-booking').classList.contains('is-active')"))
            # 입력값 보존 + 로딩 + 오류
            page.select_option("#bookProvince", "서울")
            page.select_option("#bookDistrict", "강남구")
            page.fill("#bookAddress", "대치동 123-4, 101동 1203호")
            page.eval_on_selector('#bookSyms [data-val="뇌졸중·편마비"]', "el => el.click()")
            page.eval_on_selector('[data-next="1"]', "el => el.click()")
            page.wait_for_timeout(300)
            page.eval_on_selector('.tabbar[data-mode="customer"] .tabbtn[data-tab="home"]', "el => el.click()")
            page.wait_for_timeout(260)
            page.eval_on_selector('.tabbar[data-mode="customer"] .tabbtn[data-tab="booking"]', "el => el.click()")
            page.wait_for_timeout(280)
            ok("live %d 입력값 보존(탭 이동 후 유지)" % w,
               page.eval_on_selector("#bookAddress", "el => el.value").startswith("대치동 123-4"))
            if w == 320:
                page.screenshot(path=os.path.join(SHOT, "live_v32_320_before_loading.png"))
            page.eval_on_selector("#bookDates .date-chip", "el => el.click()")
            page.evaluate("() => { const b = [...document.querySelectorAll('#bookSlots .slot')].find(x => !x.disabled); if (b) b.click(); }")
            page.eval_on_selector('[data-next="2"]', "el => el.click()")
            page.wait_for_timeout(300)
            page.evaluate("() => window.__ttokttokV32.showLoading('#passList', '이용권을 불러오는 중')")
            page.wait_for_timeout(150)
            ok("live %d 로딩 블록 표시" % w, page.query_selector("#passList [data-loading='1']") is not None)
            page.eval_on_selector("#passList", "el => el.scrollIntoView({block: 'center'})")
            page.wait_for_timeout(200)
            if w in (320, 1280):
                page.screenshot(path=os.path.join(SHOT, "live_v32_%d_loading.png" % w))
            page.evaluate("""() => window.__ttokttokV32.showErrorTo('#bookError', 'booking-submit', '예약을 마무리하지 못했어요', '입력한 내용은 그대로 남아 있어요. 다시 시도해 주세요.')""")
            page.wait_for_timeout(150)
            ok("live %d 오류 블록 + 다시 시도" % w,
               page.query_selector("#bookError [data-retry='booking-submit']") is not None)
            # 저장 실패 띠
            page.evaluate("() => window.__ttokttokV32.simulateStorageFailure(true)")
            page.evaluate("() => window.__ttokttokV32.saveAccountNow()")
            page.wait_for_timeout(260)
            ok("live %d 저장 실패 띠 + 다시 저장" % w,
               page.query_selector("#ttAlertHost [data-retry='account-save']") is not None)
            page.evaluate("() => window.scrollTo(0, 0)")
            page.wait_for_timeout(200)
            page.screenshot(path=os.path.join(SHOT, "live_v32_%d_storage_alert.png" % w))
            ctx.close()
        browser.close()
    print("\nLIVE RESULT: %d passed, %d failed" % (passed, failed))
    for f in fails:
        print(" - " + f)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    run()
