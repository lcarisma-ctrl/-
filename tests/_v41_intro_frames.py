#!/usr/bin/env python3
"""인트로 모션 프레임 — 스크린샷 지연에 영향받지 않도록 애니메이션을 직접 멈춰 세고 찍는다."""
import os
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "file://" + os.path.join(ROOT, "index.html") + "?intro=1"
MOTION = os.path.join(ROOT, "preview", "v41-audit", "motion")
FR = os.path.join(MOTION, "frames")

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files"])
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1,
                        is_mobile=True, has_touch=True, locale="ko-KR",
                        reduced_motion="no-preference")
    pg = ctx.new_page()
    pg.goto(URL)
    pg.wait_for_timeout(120)
    # 인트로가 스스로 끝나지 않게 타이머를 무력화하고, 애니메이션을 멈춰 세운다
    pg.evaluate("""() => {
      window.__savedST = window.setTimeout;
      window.setTimeout = function (fn, ms) { if (ms && ms >= 1000) return 0; return window.__savedST(fn, ms); };
      document.getAnimations().forEach(a => { try { a.pause(); } catch (e) {} });
    }""")
    frames = []
    for i, t in enumerate([0, 90, 170, 250, 330, 410, 500, 620, 760, 900, 1050, 1200, 1350, 1450]):
        pg.evaluate("""(t) => { document.getAnimations().forEach(a => { try { a.currentTime = t; } catch (e) {} }); }""", t)
        pg.wait_for_timeout(40)
        f = os.path.join(FR, "intro2_%02d.png" % i)
        pg.screenshot(path=f)
        frames.append(f)
    ctx.close()
    b.close()

# GIF
imgs = [Image.open(f).convert("P", palette=Image.ADAPTIVE, colors=96) for f in frames]
imgs = [im.resize((300, int(im.height * 300 / im.width)), Image.LANCZOS) for im in imgs]
imgs[0].save(os.path.join(MOTION, "01_intro.gif"), save_all=True, append_images=imgs[1:], duration=110, loop=0, optimize=True)

# 연속 프레임 한 장(정지 이미지로도 순서가 보이게)
pick = [frames[0], frames[2], frames[4], frames[7], frames[13]]
thumbs = [Image.open(f) for f in pick]
w = 300
thumbs = [im.resize((w, int(im.height * w / im.width)), Image.LANCZOS) for im in thumbs]
sheet = Image.new("RGB", (w * len(thumbs), thumbs[0].height), "#0B1424")
for i, im in enumerate(thumbs):
    sheet.paste(im, (i * w, 0))
sheet.save(os.path.join(MOTION, "01_intro_sequence.png"))
print("frames", len(frames), "->", MOTION)
