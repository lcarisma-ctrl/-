#!/usr/bin/env python3
"""화면별 글자 크기 분포 — 어떤 클래스가 어떤 크기로 그려지는지 센다(v41 타이포 진단)."""
import os, json
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "file://" + os.path.join(ROOT, "index.html")

JS = r"""
() => {
  const out = {};
  const add = (k) => { out[k] = (out[k]||0)+1; };
  document.querySelectorAll('body *').forEach((el) => {
    const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    if (r.width < 1 || r.height < 1 || s.visibility === 'hidden' || s.display === 'none') return;
    const own = Array.from(el.childNodes).filter(n => n.nodeType === 3).map(n => n.textContent.trim()).join('');
    if (!own) return;
    const cls = (typeof el.className === 'string' ? el.className : '').trim().split(/\s+/).slice(0,2).join('.') || el.tagName.toLowerCase();
    add(s.fontSize + ' :: ' + cls);
  });
  return out;
}
"""

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files"])
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, is_mobile=True, has_touch=True, locale="ko-KR")
    pg = ctx.new_page(); pg.goto(URL); pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000)
    res = {}
    pg.eval_on_selector('[data-login="customer"]', "el=>el.click()"); pg.wait_for_timeout(600)
    for tab in ["home", "teachers", "booking", "journal", "mypage"]:
        pg.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab="%s"]' % tab, "el=>el.click()")
        pg.wait_for_timeout(400)
        res["customer/" + tab] = pg.evaluate(JS)
    ctx.close()
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, is_mobile=True, has_touch=True, locale="ko-KR")
    pg = ctx.new_page(); pg.goto(URL); pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000)
    pg.eval_on_selector('[data-login="therapist"]', "el=>el.click()"); pg.wait_for_timeout(600)
    for tab in ["tp-home", "tp-schedule", "tp-journal", "tp-settle", "tp-mypage"]:
        pg.eval_on_selector('.tabbar[data-mode=therapist] .tabbtn[data-tab="%s"]' % tab, "el=>el.click()")
        pg.wait_for_timeout(400)
        res["partner/" + tab] = pg.evaluate(JS)
    b.close()

agg = {}
for screen, d in res.items():
    for k, n in d.items():
        agg.setdefault(k, {"n": 0, "screens": set()})
        agg[k]["n"] += n
        agg[k]["screens"].add(screen)
rows = sorted(agg.items(), key=lambda kv: -kv[1]["n"])
print("=== 가장 많이 쓰이는 (크기 :: 클래스) ===")
for k, v in rows[:45]:
    print("%4d  %-42s %d개 화면" % (v["n"], k, len(v["screens"])))
sizes = {}
for k, v in agg.items():
    sz = k.split(' :: ')[0]
    sizes[sz] = sizes.get(sz, 0) + v["n"]
print("\n=== 크기별 글자 수 ===")
for sz, n in sorted(sizes.items(), key=lambda kv: -float(kv[0].replace('px',''))):
    print("%8s  %4d" % (sz, n))
