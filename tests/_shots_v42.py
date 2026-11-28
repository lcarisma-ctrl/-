#!/usr/bin/env python3
"""v42 before/after 캡처.

before = v41 (`.work/index_v41.html`), after = 현재 `index.html`.
preview/v42-audit/{before,after}/{width}_{state}.png
preview/v42-audit/motion/sheet_drag_frames/…
"""
import os
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V41 = "file://" + os.path.join(ROOT, ".work", "index_v41.html")
V42 = "file://" + os.path.join(ROOT, "index.html")
OUT = os.path.join(ROOT, "preview", "v42-audit")


def shot_set(b, url, outdir, width, height, mobile, label, xl=False, extra=None):
    os.makedirs(os.path.join(OUT, outdir), exist_ok=True)
    ctx = b.new_context(viewport={"width": width, "height": height}, device_scale_factor=2,
                        is_mobile=mobile, has_touch=mobile, locale="ko-KR")
    if xl:
        ctx.add_init_script("try{localStorage.setItem('ttokttok_textsize_v1','xl')}catch(e){}")
    pg = ctx.new_page()
    pg.goto(url)
    pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000)
    pg.wait_for_timeout(400)

    def snap(name):
        pg.screenshot(path=os.path.join(OUT, outdir, "%d_%s_%s.png" % (width, label, name)))

    # 게이트 → 보호자
    pg.eval_on_selector('[data-login="customer"]', "el=>el.click()")
    pg.wait_for_timeout(2200)
    snap("home")

    # 선생님 → 상세 시트(스와이프 대상)
    pg.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]', "el=>el.click()")
    pg.wait_for_timeout(700)
    pg.eval_on_selector('#teacherList [data-teacher]', "el=>el.click()")
    pg.wait_for_timeout(600)
    snap("teacher_sheet")
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(300)

    # 예약 3단계 · 4단계
    pg.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=booking]', "el=>el.click()")
    pg.wait_for_timeout(500)
    pg.eval_on_selector('#provinceQuick [data-prov="서울"]', "el=>el.click()")
    pg.wait_for_timeout(150)
    pg.select_option("#bookDistrict", "강남구")
    pg.fill("#bookAddress", "대치동 123-4, 101동 1203호")
    pg.eval_on_selector('#bookSyms [data-val="뇌졸중·편마비"]', "el=>el.click()")
    pg.eval_on_selector('[data-next="1"]', "el=>el.click()")
    pg.wait_for_timeout(300)
    pg.eval_on_selector('#bookDates .date-chip', "el=>el.click()")
    pg.wait_for_timeout(120)
    pg.eval_on_selector('#bookSlots .slot:not([disabled])', "el=>el.click()")
    pg.eval_on_selector('[data-next="2"]', "el=>el.click()")
    pg.wait_for_timeout(300)
    pg.eval_on_selector('#passList [data-pass="p8"]', "el=>el.click()")
    pg.wait_for_timeout(400)
    snap("booking_step3")
    pg.eval_on_selector('[data-next="3"]', "el=>el.click()")
    pg.wait_for_timeout(400)
    snap("booking_step4")
    pg.evaluate("()=>window.scrollTo(0, document.documentElement.scrollHeight)")
    pg.wait_for_timeout(400)
    snap("booking_step4_bottom")

    # 내 정보(글자 크기 카드)
    pg.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=mypage]', "el=>el.click()")
    pg.wait_for_timeout(600)
    pg.evaluate("()=>{const e=document.querySelector('#mpTextCard'); if(e) e.scrollIntoView({block:'center'});}")
    pg.wait_for_timeout(400)
    snap("mypage_textsize")

    # 관리자 운영 지표
    pg.eval_on_selector('#rolePill', "el=>el.click()")
    pg.wait_for_timeout(400)
    pg.eval_on_selector('[data-role-switch="admin"], [data-admin-open]', "el=>el.click()")
    pg.wait_for_timeout(1600)
    pg.eval_on_selector('#adminMetricsKpiCard', "el=>el.scrollIntoView({block:'start'})")
    pg.wait_for_timeout(600)
    snap("admin_kpi")
    pg.eval_on_selector('#adminMetricsFunnel', "el=>el.scrollIntoView({block:'start'})")
    pg.wait_for_timeout(500)
    snap("admin_table")
    pg.eval_on_selector('#adminMetricsRegions', "el=>el.scrollIntoView({block:'start'})")
    pg.wait_for_timeout(500)
    snap("admin_region")
    ctx.close()


def sheet_drag(b, url, outdir):
    """시트를 끌어 내리는 중간 프레임과 닫힌 뒤."""
    os.makedirs(os.path.join(OUT, outdir), exist_ok=True)
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="ko-KR")
    pg = ctx.new_page()
    pg.goto(url)
    pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000)
    pg.wait_for_timeout(400)
    pg.eval_on_selector('[data-login="customer"]', "el=>el.click()")
    pg.wait_for_timeout(1200)
    pg.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]', "el=>el.click()")
    pg.wait_for_timeout(800)
    pg.eval_on_selector('#teacherList [data-teacher]', "el=>el.click()")
    pg.wait_for_timeout(700)
    hb = pg.evaluate("""() => { const h = document.querySelector('#teacherSheet .sheet-handle'); const r = h.getBoundingClientRect(); return {x: r.x + r.width / 2, y: r.y + r.height / 2}; }""")
    pg.mouse.move(hb["x"], hb["y"])
    pg.mouse.down()
    for i, step in enumerate([12, 26, 44, 62, 80, 96]):
        pg.mouse.move(hb["x"], hb["y"] + step)
        pg.wait_for_timeout(40)
        pg.screenshot(path=os.path.join(OUT, outdir, "drag_%d.png" % i))
    pg.mouse.up()
    pg.wait_for_timeout(700)
    pg.screenshot(path=os.path.join(OUT, outdir, "drag_closed.png"))
    ctx.close()


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--disable-dev-shm-usage"])
        for label, url in [("before", V41), ("after", V42)]:
            for w, h, mob in [(390, 844, True), (320, 568, True), (1280, 900, False)]:
                shot_set(b, url, label, w, h, mob, "main")
        # 글자 크기 '아주 크게' (v42에만 있는 기능 — before는 대조군)
        shot_set(b, V42, "after", 390, 844, True, "xl", xl=True)
        sheet_drag(b, V42, "motion")
        sheet_drag(b, V41, "motion_before")
        b.close()
    print("shots done")


main()
