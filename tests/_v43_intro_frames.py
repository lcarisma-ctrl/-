#!/usr/bin/env python3
"""v43 인트로 컷신 프레임 — 애니메이션을 시각별로 멈춰 세고 찍는다."""
import os
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "file://" + os.path.join(ROOT, "index.html") + "?intro=1"
OUT = os.path.join(ROOT, "preview", "v43-audit", "motion")
os.makedirs(OUT, exist_ok=True)
STOPS = [0, 120, 300, 480, 700, 900, 1100, 1300, 1550, 1800, 2100]
with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="ko-KR")
    ctx.add_init_script("try{sessionStorage.removeItem('ttokttok_intro_v41')}catch(e){}")
    pg = ctx.new_page()
    pg.goto(URL)
    pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000)
    # 모든 인트로 애니메이션을 멈춰 세우고 시각만 옮겨 가며 찍는다.
    pg.evaluate("""() => {
      const el = document.getElementById('intro');
      el.hidden = false;
      el.getAnimations({subtree:true}).forEach(a => a.pause());
    }""")
    frames = []
    for i, ms in enumerate(STOPS):
        pg.evaluate("""(ms) => {
          const el = document.getElementById('intro');
          el.hidden = false;
          el.classList.remove('is-done');
          el.getAnimations({subtree:true}).forEach(a => { a.pause(); a.currentTime = ms; });
        }""", ms)
        pg.wait_for_timeout(60)
        f = os.path.join(OUT, "intro2_%02d_%d.png" % (i, ms))
        pg.screenshot(path=f)
        frames.append(f)
    ctx.close(); b.close()
imgs = [Image.open(f).convert("RGB") for f in frames]
w = 300
imgs = [im.resize((w, int(im.height * w / im.width)), Image.LANCZOS) for im in imgs]
imgs[0].save(os.path.join(OUT, "01_intro.gif"), save_all=True, append_images=imgs[1:], duration=180, loop=0, optimize=True)
cols, rows = 3, 2
seq = [0, 3, 5, 6, 8, 10]
thumb = [Image.open(frames[i]).convert("RGB") for i in seq]
tw = 300; th = int(thumb[0].height * tw / thumb[0].width)
sheet = Image.new("RGB", (tw * cols, th * rows), "white")
for k, im in enumerate(thumb):
    sheet.paste(im.resize((tw, th), Image.LANCZOS), ((k % cols) * tw, (k // cols) * th))
sheet.save(os.path.join(OUT, "01_intro_sequence.png"))
print("intro frames done", len(frames))
