#!/usr/bin/env python3
"""v31 라이브 확인: https://lcarisma-ctrl.github.io/-/?v=31 실브라우저 점검."""
import os
os.environ.setdefault("LD_LIBRARY_PATH","/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu")
from playwright.sync_api import sync_playwright
URL="https://lcarisma-ctrl.github.io/-/?v=31"
SHOT=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),"preview")
res=[]
def ok(n,c,e=""):
    res.append((n,bool(c),e)); print(("  ✓ " if c else "  ✗ ")+n+(" :: "+str(e) if e and not c else ""))
with sync_playwright() as p:
    b=p.chromium.launch(args=["--no-sandbox","--font-render-hinting=none"])
    ctx=b.new_context(viewport={"width":320,"height":568},device_scale_factor=2,is_mobile=True,has_touch=True,locale="ko-KR",
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
    pg=ctx.new_page(); errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console:"+m.text) if m.type=="error" else None)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__ttokttokBooted === true", timeout=15000); pg.wait_for_timeout(600)
    ok("라이브 v31 메타", pg.evaluate("() => document.querySelector('meta[name=app-version]').content")=="v31")
    ok("터치 훅 노출", pg.evaluate("() => !!window.__ttokttokTouch && window.__ttokttokTouch.min===44"))
    ok("시작 화면 터치 44px 위반 0", pg.evaluate("() => window.__ttokttokTouch.violations().length")==0)
    ok("시작 화면 간격 위반 0", pg.evaluate("() => window.__ttokttokTouch.gapViolations().length")==0)
    pg.screenshot(path=os.path.join(SHOT,"live_v31_gate_320.png"))
    pg.eval_on_selector('[data-login="customer"]',"el=>el.click()"); pg.wait_for_timeout(500)
    ok("홈 터치 44px 위반 0", pg.evaluate("() => window.__ttokttokTouch.violations().length")==0)
    ok("홈 가로 넘침 없음", pg.evaluate("() => document.documentElement.scrollWidth<=document.documentElement.clientWidth+1"))
    pg.screenshot(path=os.path.join(SHOT,"live_v31_home_320.png"))
    pg.eval_on_selector('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]',"el=>el.click()"); pg.wait_for_timeout(450)
    ok("선생님 화면 터치 44px 위반 0", pg.evaluate("() => window.__ttokttokTouch.violations().length")==0)
    ok("선생님 카드 클릭 동작", (pg.eval_on_selector("#teacherList .teacher","el=>el.click()") or True) and (pg.wait_for_timeout(400) or pg.eval_on_selector("#teacherSheet","el=>el.classList.contains('is-open')")))
    ok("상세 시트 터치 44px 위반 0", pg.evaluate("() => window.__ttokttokTouch.violations().length")==0)
    pg.screenshot(path=os.path.join(SHOT,"live_v31_teacher_sheet_320.png"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
    pg.eval_on_selector('.tabbar[data-mode="customer"] .tabbtn[data-tab="booking"]',"el=>el.click()"); pg.wait_for_timeout(400)
    ok("320 예약 화면 터치 44px 위반 0", pg.evaluate("() => window.__ttokttokTouch.violations().length")==0)
    ok("라이브 콘솔 오류 0", not errs, errs[:3])
    # 375·1280
    for w,h,mob in [(375,812,True),(1280,800,False)]:
        c2=b.new_context(viewport={"width":w,"height":h},device_scale_factor=1,is_mobile=mob,has_touch=mob,locale="ko-KR")
        p2=c2.new_page(); p2.goto(URL, wait_until="load"); p2.wait_for_function("window.__ttokttokBooted === true",timeout=15000); p2.wait_for_timeout(600)
        ok("%d 시작 화면 터치 44px 위반 0"%w, p2.evaluate("() => window.__ttokttokTouch.violations().length")==0)
        (p2.eval_on_selector('[data-login=\"customer\"]',"el=>el.click()") if True else None); p2.wait_for_timeout(500)
        ok("%d 홈 터치 44px 위반 0"%w, p2.evaluate("() => window.__ttokttokTouch.violations().length")==0)
        p2.screenshot(path=os.path.join(SHOT,"live_v31_home_%d.png"%w))
        c2.close()
    ctx.close(); b.close()
f=[r for r in res if not r[1]]
print("\nRESULT: %d passed, %d failed"%(len(res)-len(f),len(f)))
for r in f: print(" -",r[0],r[2])
