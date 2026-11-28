import os
ROOT = "/workspace/projects/ttokttok-app"
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")
from playwright.sync_api import sync_playwright

URL = "https://lcarisma-ctrl.github.io/-/?v=22"
ok = fail = 0
def check(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1; print("  OK " + name)
    else:
        fail += 1; print("  NG " + name + (" :: " + str(extra)))

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--font-render-hinting=none"])
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                        is_mobile=True, has_touch=True, locale="ko-KR")
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__ttokttokBooted === true", timeout=20000)
    check("라이브 부팅", True)
    check("앱 버전 v22", pg.evaluate("() => document.querySelector('meta[name=app-version]').content") == "v22")
    check("모델 노출(nearVersion·photoVersion)",
          pg.evaluate("() => [window.__ttokttokModel.nearVersion, window.__ttokttokModel.photoVersion]") == ["v22", "v22"])
    # 고객 → 내 주변
    pg.eval_on_selector('[data-login="customer"]', "el => el.click()")
    pg.wait_for_timeout(300)
    pg.eval_on_selector('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]', "el => el.click()")
    pg.wait_for_timeout(400)
    check("보기 탭 2개", pg.eval_on_selector_all("#teacherViewTabs [data-view]", "els => els.length") == 2)
    pg.tap('#teacherViewTabs [data-view="near"]')
    pg.wait_for_timeout(450)
    near = pg.evaluate("() => window.__ttokttokNear || null")
    check("동네 클러스터 카드", bool(near) and pg.eval_on_selector_all("#dongClusterList [data-dong-cluster]", "els => els.length") >= 1, near)
    check("카드 요약(활동·바로 가능)", all(x in pg.inner_text("#dongClusterList") for x in ["활동 선생님", "바로 가능"]))
    pg.screenshot(path=os.path.join(ROOT, "preview", "live_v22_near_dong.png"))
    pg.eval_on_selector('[data-dong-pick="dong:reg-서울-강남구-대치동"]', "el => el.click()")
    pg.wait_for_timeout(400)
    rows = pg.evaluate("() => Array.from(document.querySelectorAll('#teacherList .teacher')).map(el => el.dataset.teacher)")
    check("대치동 → 박서준 1명", rows == ["park"], rows)
    pg.eval_on_selector("#teacherQueryBar", "el => el.scrollIntoView({block:'center'})")
    pg.wait_for_timeout(300)
    pg.screenshot(path=os.path.join(ROOT, "preview", "live_v22_near_pick.png"))
    # 파트너 → 사진
    pg.eval_on_selector('[data-login="therapist"]', "el => el.click()")
    pg.wait_for_timeout(400)
    pg.eval_on_selector('.tabbtn[data-tab="tp-journal"]', "el => el.click()")
    pg.wait_for_timeout(400)
    pg.set_input_files("#qlPhoto", os.path.join(ROOT, "tests", "fixtures", "pose_sample.png"))
    pg.wait_for_selector("#qlPhotoPreview img", timeout=8000)
    pg.wait_for_timeout(300)
    pv = pg.evaluate("() => window.__ttokttokModel.quickPhotoPreview()")
    check("사진 미리보기·안내·빼기", bool(pv) and pv.get("visible") and pv.get("hasRemove") and "운동 부위·자세" in (pv.get("note") or ""), pv)
    pg.eval_on_selector("#qlPhotoPreview", "el => el.scrollIntoView({block:'center'})")
    pg.wait_for_timeout(350)
    pg.screenshot(path=os.path.join(ROOT, "preview", "live_v22_quick_photo.png"))
    for sel in ['[data-ql-pain="3"]', '[data-ql-cond="4"]', '[data-ql-act="walk"]']:
        pg.tap(sel)
    pg.tap("#qlSave")
    pg.wait_for_timeout(600)
    q = pg.evaluate("() => window.__ttokttokQuickLog || null")
    check("사진 붙인 일지 저장", bool(q) and q.get("hasPhoto") is True, q)
    pg.eval_on_selector('[data-login="customer"]', "el => el.click()")
    pg.wait_for_timeout(400)
    pg.eval_on_selector('.tabbar[data-mode="customer"] .tabbtn[data-tab="journal"]', "el => el.click()")
    pg.wait_for_timeout(500)
    check("보호자 최근 일지에 사진", pg.eval_on_selector("#journalLatestCard", "el => el.hidden") is False and
          pg.eval_on_selector_all("#journalLatestBody [data-journal-photo]", "els => els.length") == 1)
    pg.eval_on_selector("#journalLatestCard", "el => el.scrollIntoView({block:'center'})")
    pg.wait_for_timeout(400)
    pg.screenshot(path=os.path.join(ROOT, "preview", "live_v22_guardian_photo.png"))
    check("JS 오류 없음", not errs, errs[:2])
    b.close()
print("\nLIVE RESULT: %d passed, %d failed" % (ok, fail))
