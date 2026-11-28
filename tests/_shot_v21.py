import os, sys
ROOT = "/workspace/projects/ttokttok-app"
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")
from playwright.sync_api import sync_playwright
URL = "file://" + os.path.join(ROOT, "index.html")
with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="ko-KR")
    pg = ctx.new_page()
    pg.goto(URL); pg.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
    pg.eval_on_selector('[data-login="therapist"]', "el => el.click()")
    pg.wait_for_timeout(600)
    pg.eval_on_selector("#tpSettle", "el => el.scrollIntoView({block:'center'})")
    pg.wait_for_timeout(500)
    pg.screenshot(path=os.path.join(ROOT, "preview", "v21_partner_settle_note.png"))
    print("note:", pg.inner_text(".settle-note"))
    # 고객 내 예약 시트 — 지난 완료 방문 카드
    pg.eval_on_selector('[data-login="customer"]', "el => el.click()")
    pg.wait_for_timeout(400)
    pg.eval_on_selector("#homeTicketBtn", "el => el.click()")
    pg.wait_for_timeout(500)
    pg.eval_on_selector("#bookingList", "el => el.scrollIntoView({block:'center'})")
    pg.wait_for_timeout(400)
    pg.screenshot(path=os.path.join(ROOT, "preview", "v21_booking_past_visit.png"))
    print("cards:", pg.eval_on_selector_all("#bookingList .list-item", "els => els.map(e=>e.getAttribute('data-booking'))"))
    b.close()
