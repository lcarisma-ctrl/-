#!/usr/bin/env python3
"""v17 운영자 예약 접수 큐 화면 캡처(디자인 확인용).

실행: python3 tests/_shot_v17.py
결과물: preview/v17_queue_top.png (섹션 상단) · preview/v17_queue_notice.png (로컬 데모 고지)
"""
import json
import os

os.environ["LD_LIBRARY_PATH"] = (
    "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu:"
    + os.environ.get("LD_LIBRARY_PATH", "")
)

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOT = os.path.join(ROOT, "preview")


def row(no, status, extra):
    r = {"id": "res-" + no.lower(), "no": no, "userId": "usr-demo", "date": "11.28", "day": "토",
         "time": "10:00", "teacher": "", "teacherId": "", "region": "서울 강남구 대치동",
         "regionId": "reg-서울-강남구", "status": status, "passId": "p8", "walletId": "seed-pass",
         "dateIso": "2026-11-28", "amount": 74000, "paymentStatus": "paid"}
    r.update(extra or {})
    return r


SEED = {
    "profile": {"name": "현수"},
    "passes": [{"id": "seed-pass", "userId": "usr-demo", "passId": "p8", "name": "8회 방문권", "total": 8,
                "remaining": 5, "purchased": "2026.10.28", "expire": "2027.01.27", "status": "active"}],
    "receipts": [],
    "bookings": [
        row("TT-261126-1001", "received", {"dateIso": "2026-11-28", "time": "10:00"}),
        row("TT-261126-1002", "assigned", {"teacher": "이하늘 선생님", "teacherId": "lee", "dateIso": "2026-11-28", "time": "14:00"}),
        row("TT-261126-1003", "confirmed", {"teacher": "박서준 선생님", "teacherId": "park", "dateIso": "2026-11-29", "time": "10:00", "amount": 0}),
        row("TT-261126-1004", "canceled", {"dateIso": "2026-11-27", "time": "09:00", "paymentStatus": "refund_pending"}),
    ],
}

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files"])
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                        is_mobile=True, has_touch=True, locale="ko-KR")
    ctx.add_init_script("window.localStorage.setItem('ttokttok_account_v3', %s);"
                        % json.dumps(json.dumps(SEED, ensure_ascii=False)))
    page = ctx.new_page()
    page.goto("file://" + os.path.join(ROOT, "index.html"))
    page.wait_for_function("window.__ttokttokBooted === true")
    page.eval_on_selector('[data-login="customer"]', "el => el.click()")
    page.wait_for_timeout(300)
    page.eval_on_selector("[data-admin-open]", "el => el.click()")
    page.wait_for_timeout(400)
    page.eval_on_selector("#adminResvSec", "el => el.scrollIntoView({block:'start'})")
    page.wait_for_timeout(400)
    page.screenshot(path=os.path.join(SHOT, "v17_queue_top.png"))
    print("saved", os.path.join(SHOT, "v17_queue_top.png"))
    b.close()
