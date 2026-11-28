import os
ROOT = "/workspace/projects/ttokttok-app"
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")
from playwright.sync_api import sync_playwright

URL = "https://lcarisma-ctrl.github.io/-/?v=21"
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
    pg.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
    check("라이브 부팅", True)
    check("앱 버전 v21", pg.evaluate("() => document.querySelector('meta[name=app-version]').content") == "v21")
    check("정산 규칙(D+3·15·말일)", all(x in pg.evaluate("() => window.__ttokttokModel.settlementRuleText") for x in ["D+3", "15일", "말일"]))
    check("지급일 11/26→11/30", pg.evaluate("() => window.__ttokttokModel.nextPayoutDue('2026-11-26')") == "2026-11-30")
    check("푸터 사업자 표기", all(x in pg.inner_text("#gateBizInfo") for x in ["상호 똑똑쌤", "대표 임현수", "사업자등록번호", "031-919-8577"]),
          pg.inner_text("#gateBizInfo"))
    pg.screenshot(path=os.path.join(ROOT, "preview", "live_v21_gate.png"))
    pg.eval_on_selector('[data-login="admin"]', "el => el.click()")
    pg.wait_for_timeout(500)
    check("관리자 4주 재평가 1건", "4주 재평가 1" in pg.inner_text("#adminOpsCounts"), pg.inner_text("#adminOpsCounts"))
    check("재평가 카드 due", pg.eval_on_selector_all('#adminReevalBoard [data-reeval-state="due"]', "els => els.length") == 1)
    pg.eval_on_selector("#adminReevalBoard", "el => el.scrollIntoView({block:'center'})")
    pg.wait_for_timeout(400)
    pg.screenshot(path=os.path.join(ROOT, "preview", "live_v21_admin_reeval.png"))
    pg.eval_on_selector('[data-login="therapist"]', "el => el.click()")
    pg.wait_for_timeout(500)
    check("파트너 정산 11.30·D+3·15일·말일", all(x in pg.inner_text("#tpSettle") for x in ["11.30", "D+3", "15일·말일"]),
          pg.inner_text("#tpSettle")[:150])
    check("JS 오류 없음", not errs, errs[:2])
    b.close()
print("\nLIVE RESULT: %d passed, %d failed" % (ok, fail))
