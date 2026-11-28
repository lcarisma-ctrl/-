import os
import sys
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")
from playwright.sync_api import sync_playwright
from datetime import datetime, timedelta, timezone

URL = "file://" + os.path.join(ROOT, "index.html")
SHOT = os.path.join(ROOT, "preview")

kst = datetime.now(timezone.utc) + timedelta(hours=9)
today = kst.strftime("%Y-%m-%d")
tomorrow = (kst + timedelta(days=1)).strftime("%Y-%m-%d")


def lbl(iso):
    y, m, d = iso.split("-")
    return "%d.%s" % (int(m), d)


recent = (kst - timedelta(hours=20)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
bookings = [
    {"id": "res-z1", "no": "TT-270001-9001", "userId": "usr-demo", "status": "confirmed", "date": lbl(tomorrow), "day": "목",
     "time": "10:30", "teacher": "박서준 선생님", "teacherId": "park", "region": "서울 강남구 대치동", "regionId": "reg-서울-강남구",
     "dateIso": tomorrow, "amount": 90000, "paymentStatus": "paid"},
    {"id": "res-z2", "no": "TT-270001-9002", "userId": "usr-demo", "status": "rescheduled", "date": lbl(today), "day": "수",
     "time": "14:00", "teacher": "박서준 선생님", "teacherId": "park", "region": "서울 서초구 반포동", "regionId": "reg-서울-서초구",
     "dateIso": today, "amount": 90000, "paymentStatus": "paid",
     "statusHistory": [{"status": "confirmed", "at": (kst - timedelta(days=3)).strftime("%Y-%m-%dT01:00:00.000Z")},
                       {"status": "rescheduled", "at": recent, "by": "customer", "reason": "보호자 요청"}]},
    {"id": "res-z3", "no": "TT-270001-9003", "userId": "usr-demo", "status": "canceled", "date": lbl(today), "day": "수",
     "time": "11:00", "teacher": "박서준 선생님", "teacherId": "park", "region": "서울 송파구 잠실동", "regionId": "reg-서울-송파구",
     "dateIso": today, "amount": 90000, "refund": 90000, "paymentStatus": "paid",
     "statusHistory": [{"status": "confirmed", "at": (kst - timedelta(days=4)).strftime("%Y-%m-%dT01:00:00.000Z")},
                       {"status": "canceled", "at": recent, "by": "customer", "reason": "보호자 취소"}]},
    {"id": "res-z4", "no": "TT-270001-9004", "userId": "usr-demo", "status": "received", "date": lbl(today), "day": "수",
     "time": "09:00", "teacher": "이하늘 선생님", "teacherId": "lee", "region": "서울 마포구 성산동", "regionId": "reg-서울-마포구",
     "dateIso": today, "amount": 90000, "paymentStatus": "paid",
     "statusHistory": [{"status": "assigned", "at": (kst - timedelta(days=3)).strftime("%Y-%m-%dT01:00:00.000Z")},
                       {"status": "received", "at": recent, "by": "operator", "reason": "선생님 사정"}]},
]
seed = {"profile": {"name": "현수"}, "passes": [], "bookings": bookings, "receipts": [], "sessions": [], "myReviews": []}

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="ko-KR")
    ctx.add_init_script("window.localStorage.setItem('ttokttok_account_v3', %s);" % json.dumps(json.dumps(seed, ensure_ascii=False)))
    page = ctx.new_page()
    page.goto(URL)
    page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
    page.eval_on_selector('[data-login="admin"]', "el => el.click()")
    page.wait_for_timeout(600)
    page.evaluate("() => document.getElementById('adminReminderSec').scrollIntoView({block:'start'})")
    page.wait_for_timeout(400)
    page.screenshot(path=os.path.join(SHOT, "v27_admin_reminder_section.png"))
    page.set_viewport_size({"width": 320, "height": 568})
    page.wait_for_timeout(400)
    page.evaluate("() => document.getElementById('adminReminderSec').scrollIntoView({block:'start'})")
    page.wait_for_timeout(300)
    page.screenshot(path=os.path.join(SHOT, "v27_320_admin_reminder_section.png"))
    # 알림 시트(칩 줄바꿈 확인)
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(300)
    page.evaluate("() => document.getElementById('entryGate').classList.add('is-open')")
    page.wait_for_timeout(200)
    page.eval_on_selector('[data-login="customer"]', "el => el.click()")
    page.wait_for_timeout(400)
    page.tap("#btnNotif")
    page.wait_for_timeout(500)
    page.screenshot(path=os.path.join(SHOT, "v27_notif_sheet_390.png"))
    b.close()
print("done")
