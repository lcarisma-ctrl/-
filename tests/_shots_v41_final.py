#!/usr/bin/env python3
"""v41 최종 캡처 — after 스크린샷 + 모션 프레임/GIF.

preview/v41-audit/after/{width}_{state}.png
preview/v41-audit/motion/{intro,transition,sheet,tab}.gif  (+ frames/)
"""
import os, sys
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "file://" + os.path.join(ROOT, "index.html")
OUT = os.path.join(ROOT, "preview", "v41-audit")
AFTER = os.path.join(OUT, "after")
MOTION = os.path.join(OUT, "motion")
FRAMES = os.path.join(MOTION, "frames")
for d in (AFTER, MOTION, FRAMES):
    os.makedirs(d, exist_ok=True)

CUSTOMER = [
    ("home", "() => {}"),
    ("teachers", "() => document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]').click()"),
    ("teacher_detail", "() => { document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]').click(); setTimeout(()=>{const c=document.querySelector('[data-teacher]'); if(c)c.click();},260); }"),
    ("booking1", "() => { document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=booking]').click(); }"),
    ("journal", "() => document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=journal]').click()"),
    ("weekly", "() => { document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=journal]').click(); setTimeout(()=>{const b=document.querySelector('#weeklyOpen'); if(b)b.click();},300); }"),
    ("mypage", "() => document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=mypage]').click()"),
]
PARTNER = [
    ("tp_home", "() => {}"),
    ("tp_schedule", "() => document.querySelector('.tabbar[data-mode=therapist] .tabbtn[data-tab=tp-schedule]').click()"),
    ("tp_settle", "() => document.querySelector('.tabbar[data-mode=therapist] .tabbtn[data-tab=tp-settle]').click()"),
]
ADMIN = [("admin", "() => {}")]


def newpage(b, w, h, mob, dsf=2):
    ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=dsf,
                        is_mobile=mob, has_touch=mob, locale="ko-KR")
    return ctx, ctx.new_page()


def gif(paths, out, width=300, duration=90):
    imgs = [Image.open(p).convert("P", palette=Image.ADAPTIVE, colors=128) for p in paths]
    imgs = [im.resize((width, int(im.height * width / im.width)), Image.LANCZOS) for im in imgs]
    imgs[0].save(out, save_all=True, append_images=imgs[1:], duration=duration, loop=0, optimize=True)
    print("gif", out, len(imgs), "frames")


def run():
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--disable-dev-shm-usage"])

        # ── 1. after 스크린샷 ─────────────────────────────────────────
        for width, height, mob in [(390, 844, True), (1280, 900, False)]:
            ctx, pg = newpage(b, width, height, mob)
            pg.goto(URL)
            pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000)
            pg.wait_for_timeout(600)
            pg.screenshot(path=os.path.join(AFTER, "%d_gate.png" % width))
            ctx.close()

            for n, js in CUSTOMER:
                ctx, pg = newpage(b, width, height, mob)
                pg.goto(URL)
                pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000)
                pg.wait_for_timeout(400)
                pg.eval_on_selector('[data-login="customer"]', "el=>el.click()")
                pg.wait_for_timeout(900)
                pg.evaluate(js)
                pg.wait_for_timeout(2800)
                pg.screenshot(path=os.path.join(AFTER, "%d_%s.png" % (width, n)))
                if n in ("home", "teachers", "journal"):
                    pg.screenshot(path=os.path.join(AFTER, "%d_%s_full.png" % (width, n)), full_page=True)
                ctx.close()

            for n, js in PARTNER:
                ctx, pg = newpage(b, width, height, mob)
                pg.goto(URL)
                pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000)
                pg.wait_for_timeout(400)
                pg.eval_on_selector('[data-login="therapist"]', "el=>el.click()")
                pg.wait_for_timeout(900)
                pg.evaluate(js)
                pg.wait_for_timeout(2800)
                pg.screenshot(path=os.path.join(AFTER, "%d_%s.png" % (width, n)))
                ctx.close()

            for n, js in ADMIN:
                ctx, pg = newpage(b, width, height, mob)
                pg.goto(URL)
                pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000)
                pg.wait_for_timeout(400)
                pg.eval_on_selector('[data-login="admin"]', "el=>el.click()")
                pg.wait_for_timeout(2600)
                pg.screenshot(path=os.path.join(AFTER, "%d_%s.png" % (width, n)))
                ctx.close()

        # ── 2. 모션 GIF ───────────────────────────────────────────────
        # 2-1. 인트로 (로고 → 워드마크 → 카피 → 게이트 크로스페이드)
        ctx, pg = newpage(b, 390, 844, True)
        pg.goto(URL + "?intro=1")
        frames = []
        for i in range(20):
            pg.wait_for_timeout(90)
            f = os.path.join(FRAMES, "intro_%02d.png" % i)
            pg.screenshot(path=f)
            frames.append(f)
        ctx.close()
        gif(frames, os.path.join(MOTION, "01_intro.gif"), width=300, duration=90)

        # 2-2. 탭 전환(방향 전환 + 순차 등장)
        ctx, pg = newpage(b, 390, 844, True)
        pg.goto(URL)
        pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000)
        pg.wait_for_timeout(400)
        pg.eval_on_selector('[data-login="customer"]', "el=>el.click()")
        pg.wait_for_timeout(2600)
        pg.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab="teachers"]', "el=>el.click()")
        frames = []
        for i in range(14):
            pg.wait_for_timeout(45)
            f = os.path.join(FRAMES, "tab_%02d.png" % i)
            pg.screenshot(path=f)
            frames.append(f)
        ctx.close()
        gif(frames, os.path.join(MOTION, "02_tab.gif"), width=300, duration=70)

        # 2-3. 시트 열기/닫기(스프링 + 스크림)
        ctx, pg = newpage(b, 390, 844, True)
        pg.goto(URL)
        pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000)
        pg.wait_for_timeout(400)
        pg.eval_on_selector('[data-login="customer"]', "el=>el.click()")
        pg.wait_for_timeout(2200)
        pg.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab="teachers"]', "el=>el.click()")
        pg.wait_for_timeout(1600)
        pg.eval_on_selector("#teacherList .teacher", "el=>el.click()")
        frames = []
        for i in range(10):
            pg.wait_for_timeout(45)
            f = os.path.join(FRAMES, "sheet_%02d.png" % i)
            pg.screenshot(path=f)
            frames.append(f)
        pg.keyboard.press("Escape")
        for i in range(10, 18):
            pg.wait_for_timeout(45)
            f = os.path.join(FRAMES, "sheet_%02d.png" % i)
            pg.screenshot(path=f)
            frames.append(f)
        ctx.close()
        gif(frames, os.path.join(MOTION, "03_sheet.gif"), width=300, duration=70)

        b.close()


run()
