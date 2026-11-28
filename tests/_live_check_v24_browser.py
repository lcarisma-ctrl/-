"""v24 라이브 실브라우저 점검 — 320px 레이아웃·Escape·포커스·접근성 속성."""
import os
ROOT = "/workspace/projects/ttokttok-app"
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ.get("LD_LIBRARY_PATH") if os.environ.get("LD_LIBRARY_PATH") else "")
from playwright.sync_api import sync_playwright

URL = "https://lcarisma-ctrl.github.io/-/?v=24&live=1"
ok = fail = 0


def check(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1; print("  OK " + name)
    else:
        fail += 1; print("  NG " + name + (" :: " + str(extra)))


def overflow(pg):
    m = pg.evaluate("() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})")
    return m["sw"] <= m["cw"] + 1, m


with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--font-render-hinting=none"])
    ctx = b.new_context(viewport={"width": 320, "height": 568}, device_scale_factor=2,
                        is_mobile=True, has_touch=True, locale="ko-KR")
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__ttokttokBooted === true", timeout=20000)
    check("라이브 부팅", True)
    check("앱 버전 v24", pg.evaluate("() => document.querySelector('meta[name=app-version]').content") == "v24")
    check("QA 훅 노출", pg.evaluate("() => [window.__ttokttokModel.qaVersion, window.__ttokttokModel.a11y.version]") == ["v24", "v24"])
    check("320px 뷰포트", pg.evaluate("() => document.documentElement.clientWidth") == 320)
    check("시작 화면 320px 넘침 없음", overflow(pg)[0], overflow(pg)[1])
    pg.screenshot(path=os.path.join(ROOT, "preview", "live_v24_gate_320.png"))

    pg.tap("#gateCta"); pg.wait_for_timeout(400)
    check("휴대폰 시트 넘침 없음", overflow(pg)[0], overflow(pg)[1])
    pg.keyboard.press("Escape"); pg.wait_for_timeout(350)
    check("Escape로 휴대폰 시트 닫힘", not pg.eval_on_selector("#gateSheet", "el => el.classList.contains('is-open')"))

    pg.tap("#gateCta"); pg.wait_for_timeout(300)
    pg.eval_on_selector('[data-login="customer"]', "el => el.click()"); pg.wait_for_timeout(400)
    for tab in ["home", "teachers", "booking", "journal", "mypage"]:
        pg.eval_on_selector('.tabbar[data-mode="customer"] [data-tab="%s"]' % tab, "el => el.click()")
        pg.wait_for_timeout(280)
        o = overflow(pg)
        check("고객 %s 320px 넘침 없음" % tab, o[0], o[1])
    check("접근성 이름 없는 버튼 0", pg.evaluate("() => window.__ttokttokModel.a11y.unnamedControls()") == [],
          pg.evaluate("() => window.__ttokttokModel.a11y.unnamedControls().slice(0,3)"))
    check("label 없는 입력 0", pg.evaluate("() => window.__ttokttokModel.a11y.unlabeledFields()") == [])
    check("dialog 이름 20/20", pg.evaluate("() => [window.__ttokttokModel.a11y.labelledDialogs(), window.__ttokttokModel.a11y.dialogCount()]")[0] ==
          pg.evaluate("() => window.__ttokttokModel.a11y.dialogCount()"),
          pg.evaluate("() => [window.__ttokttokModel.a11y.labelledDialogs(), window.__ttokttokModel.a11y.dialogCount()]"))
    pg.screenshot(path=os.path.join(ROOT, "preview", "live_v24_320_mypage.png"))

    # 시트 7종 Escape
    bad = []
    for opener, sheet in [("#mpBookLink", "accountSheet"), ("#mpNotifRow", "notifSheet"), ("#mpCouponRow", "couponSheet"),
                          ("#mpPayRow", "paySheet"), ("#mpRoleRow", "roleSheet"), ("#mpFaqRow", "faqSheet"),
                          ("#mpRegionRow", "regionSheet")]:
        pg.tap(opener); pg.wait_for_timeout(320)
        o = overflow(pg)
        if not o[0]:
            bad.append(sheet + " 넘침")
        pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
        if pg.eval_on_selector("#" + sheet, "el => el.classList.contains('is-open')"):
            bad.append(sheet + " Escape 안 닫힘")
    check("보호자 시트 7종 넘침·Escape", not bad, bad)

    # 포커스 이동·복귀
    pg.eval_on_selector('.tabbar[data-mode="customer"] [data-tab="teachers"]', "el => el.click()"); pg.wait_for_timeout(320)
    pg.tap("#teacherList .teacher"); pg.wait_for_timeout(450)
    check("시트 열면 초점이 시트 안으로", pg.evaluate("() => window.__ttokttokModel.a11y.focusInside('#teacherSheet')"))
    pg.screenshot(path=os.path.join(ROOT, "preview", "live_v24_320_teacher_sheet.png"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(400)
    check("닫으면 초점이 카드로 복귀", pg.evaluate("() => document.activeElement && document.activeElement.classList.contains('teacher')"),
          pg.evaluate("() => document.activeElement && (document.activeElement.id || document.activeElement.className)"))

    pg.evaluate("() => document.getElementById('entryGate').classList.add('is-open')"); pg.wait_for_timeout(200)
    pg.eval_on_selector('[data-login="admin"]', "el => el.click()"); pg.wait_for_timeout(600)
    o = overflow(pg)
    check("관리자 콘솔 320px 넘침 없음", o[0], o[1])
    pg.screenshot(path=os.path.join(ROOT, "preview", "live_v24_320_admin.png"))
    check("JS 오류 0", not errs, errs[:2])
    b.close()

print("\nLIVE v24: %d ok, %d ng" % (ok, fail))
