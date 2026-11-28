import os, sys, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")
from playwright.sync_api import sync_playwright

URL = "file://" + os.path.join(ROOT, "index.html")
SHOT = os.path.join(ROOT, "preview")
EMPTY = json.dumps({"passes": [], "bookings": [], "receipts": [], "sessions": [], "myReviews": [], "profile": {"name": "현수"}}, ensure_ascii=False)


def run():
    out = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files"])
        for (w, h, mob) in [(320, 568, True), (375, 812, True), (1280, 800, False)]:
            ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if mob else 1,
                                      is_mobile=mob, has_touch=mob, locale="ko-KR")
            ctx.add_init_script("try{localStorage.setItem('ttokttok_account_v3', %s);}catch(e){}" % json.dumps(EMPTY))
            page = ctx.new_page()
            page.goto(URL)
            page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
            page.wait_for_timeout(400)
            page.eval_on_selector('[data-login="customer"]', "el => el.click()")
            page.wait_for_timeout(320)
            page.eval_on_selector('.tabbar[data-mode="customer"] .tabbtn[data-tab="mypage"]', "el => el.click()")
            page.wait_for_timeout(360)
            page.screenshot(path=os.path.join(SHOT, "v32_%d_empty_mypage.png" % w))
            page.eval_on_selector("#homeTicketBtn", "el => el.click()")
            page.wait_for_timeout(360)
            page.screenshot(path=os.path.join(SHOT, "v32_%d_empty_sheet.png" % w))
            # 빈 상태 CTA → 예약 화면
            page.eval_on_selector('[data-empty="booking-list"] [data-go="booking"]', "el => el.click()")
            page.wait_for_timeout(3000)   # 토스트가 사라진 뒤에 찍는다
            page.select_option("#bookProvince", "서울")
            page.select_option("#bookDistrict", "강남구")
            page.fill("#bookAddress", "대치동 123-4, 101동 1203호")
            page.eval_on_selector('#bookSyms [data-val="뇌졸중·편마비"]', "el => el.click()")
            page.eval_on_selector('[data-next="1"]', "el => el.click()")
            page.wait_for_timeout(240)
            page.eval_on_selector("#bookDates .date-chip", "el => el.click()")
            page.evaluate("() => { const b = [...document.querySelectorAll('#bookSlots .slot')].find(x => !x.disabled); if (b) b.click(); }")
            page.eval_on_selector('[data-next="2"]', "el => el.click()")
            page.wait_for_timeout(260)
            # 오류 + 재시도 — 4단계 결제 자리
            page.eval_on_selector('#passList [data-pass="p1"]', "el => el.click()")
            page.eval_on_selector('[data-next="3"]', "el => el.click()")
            page.wait_for_timeout(300)
            page.evaluate("""() => window.__ttokttokV32.showErrorTo('#bookError', 'booking-submit', '예약을 마무리하지 못했어요', '입력한 내용은 그대로 남아 있어요. 다시 시도해 주세요.')""")
            page.wait_for_timeout(160)
            page.eval_on_selector('#bookError', "el => el.scrollIntoView({block: 'center'})")
            page.wait_for_timeout(320)
            page.screenshot(path=os.path.join(SHOT, "v32_%d_error.png" % w))
            # 로딩 표시 — 이용권 목록 자리에 공통 로딩 블록
            page.eval_on_selector('[data-back="4"]', "el => el.click()")
            page.wait_for_timeout(280)
            page.evaluate("() => window.__ttokttokV32.showLoading('#passList', '이용권을 불러오는 중')")
            page.wait_for_timeout(150)
            page.eval_on_selector('#passList', "el => el.scrollIntoView({block: 'center'})")
            page.wait_for_timeout(320)
            page.screenshot(path=os.path.join(SHOT, "v32_%d_loading.png" % w))
            # 저장 실패 띠
            page.evaluate("() => window.__ttokttokV32.simulateStorageFailure(true)")
            page.evaluate("() => window.__ttokttokV32.saveAccountNow()")
            page.wait_for_timeout(260)
            page.evaluate("() => window.scrollTo(0, 0)")
            page.wait_for_timeout(200)
            page.screenshot(path=os.path.join(SHOT, "v32_%d_storage_alert.png" % w))
            m = page.evaluate("() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, alerts: window.__ttokttokV32.alerts()})")
            out[str(w)] = m
            ctx.close()
        browser.close()
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    run()
