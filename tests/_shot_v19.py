import os, json
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB="/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"]=LIB+(":"+os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")
from playwright.sync_api import sync_playwright
URL="file://"+os.path.join(ROOT,"index.html"); SHOT=os.path.join(ROOT,"preview")
def mk(no,status,extra=None):
    row={"id":"res-"+no.lower(),"no":no,"userId":"usr-demo","date":"11.27","day":"금","time":"10:30","teacher":"박서준 선생님","teacherId":"park","region":"서울 강남구 대치동","regionId":"reg-서울-강남구","status":status,"passId":"p8","walletId":"seed-pass","dateIso":"2026-11-27","amount":74000,"paymentStatus":"paid","symptomCodes":["stroke"]}
    row.update(extra or {}); return row
seed={"profile":{"name":"현수"},"passes":[{"id":"seed-pass","userId":"usr-demo","passId":"p8","name":"8회 방문권","total":8,"remaining":5,"purchased":"2026.10.28","expire":"2027.01.27","status":"active"}],
 "bookings":[mk("TT-261128-2003","rescheduled"),mk("TT-261128-2005","no_show"),mk("TT-261128-2001","received",{"teacher":"","teacherId":""})],"receipts":[]}
with sync_playwright() as p:
    b=p.chromium.launch(args=["--no-sandbox","--allow-file-access-from-files","--font-render-hinting=none"])
    for w,name in [(390,"v19_booking_390"),(320,"v19_booking_320")]:
        ctx=b.new_context(viewport={"width":w,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True,locale="ko-KR")
        ctx.add_init_script("window.localStorage.setItem('ttokttok_account_v3', %s);"%json.dumps(json.dumps(seed,ensure_ascii=False)))
        pg=ctx.new_page(); pg.goto(URL); pg.wait_for_function("window.__ttokttokBooted === true",timeout=8000)
        pg.eval_on_selector('[data-login="customer"]',"el=>el.click()"); pg.wait_for_timeout(300)
        pg.eval_on_selector('.tabbar[data-mode="customer"] .tabbtn[data-tab="mypage"]',"el=>el.click()"); pg.wait_for_timeout(400)
        pg.eval_on_selector('#bookingList [data-booking="TT-261128-2003"]',"el=>el.scrollIntoView({block:'center'})"); pg.wait_for_timeout(300)
        pg.screenshot(path=os.path.join(SHOT,"shots_%s.png"%name))
        ctx.close()
    b.close()
print("done")
