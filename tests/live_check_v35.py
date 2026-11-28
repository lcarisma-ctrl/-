#!/usr/bin/env python3
"""v35 라이브 확인 — 디자인 토큰 통합·대비 AA·인라인 회수(실서비스 URL)."""
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ.get("LD_LIBRARY_PATH") if os.environ.get("LD_LIBRARY_PATH") else "")
from playwright.sync_api import sync_playwright  # noqa: E402

URL = "https://lcarisma-ctrl.github.io/-/?v=35"
SHOT = os.path.join(ROOT, "preview")
passed, failed, fails = 0, 0, []


def ok(name, cond, extra=""):
    global passed, failed
    if cond:
        passed += 1
        print("  ✓ " + name)
    else:
        failed += 1
        fails.append(name + (" :: " + str(extra) if extra else ""))
        print("  ✗ " + name + ((" :: " + str(extra)) if extra else ""))


CONTRAST_JS = r"""
() => {
  const parse = (c) => { const m = String(c).match(/rgba?\(([^)]+)\)/); if (!m) return null;
    const p = m[1].split(/[\s,\/]+/).map(Number); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; };
  const over = (t, b) => { const a = t.a + b.a * (1 - t.a); if (a === 0) return { r: 0, g: 0, b: 0, a: 0 };
    return { r: (t.r * t.a + b.r * b.a * (1 - t.a)) / a, g: (t.g * t.a + b.g * b.a * (1 - t.a)) / a, b: (t.b * t.a + b.b * b.a * (1 - t.a)) / a, a }; };
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const ratio = (a, b) => { const l1 = lum(a), l2 = lum(b); const hi = Math.max(l1, l2), lo = Math.min(l1, l2); return (hi + 0.05) / (lo + 0.05); };
  function stops(cs) { const img = cs.backgroundImage || ''; if (!img || img === 'none') return null;
    const f = img.match(/rgba?\([^)]+\)/g); if (!f) return null; return f.map(parse).filter((c) => c && c.a > 0.2); }
  const cache = new Map();
  function layers(el) {
    if (cache.has(el)) return cache.get(el);
    const below = (el === document.documentElement || el === document.body) ? [{ r: 11, g: 20, b: 36, a: 1 }] : layers(el.parentElement || document.documentElement)[0];
    const cs = getComputedStyle(el); const own = parse(cs.backgroundColor) || { r: 0, g: 0, b: 0, a: 0 };
    const st = stops(cs); let out;
    if (st && st.length) out = st.map((x) => over(x, below)); else if (own.a > 0) out = [over(own, below)]; else out = [below];
    cache.set(el, out); return out;
  }
  const bad = []; const seen = new Set();
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null); let n;
  while ((n = w.nextNode())) {
    const text = String(n.nodeValue || '').replace(/\s+/g, ' ').trim(); if (!text) continue;
    const el = n.parentElement; if (!el || seen.has(el)) continue;
    const cs = getComputedStyle(el); if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    const r = el.getBoundingClientRect(); if (r.width < 1 || r.height < 1) continue;
    if (el.closest('.sprite, [aria-hidden="true"], script, style, noscript')) continue;
    const op = parseFloat(cs.opacity); if (!isNaN(op) && op < 0.05) continue;
    const fg0 = parse(cs.color); if (!fg0) continue;
    let fgBase = fg0; if (op < 1) fgBase = { r: fg0.r, g: fg0.g, b: fg0.b, a: fg0.a * op };
    const size = parseFloat(cs.fontSize) || 14; const weight = parseInt(cs.fontWeight, 10) || 400;
    const need = (size >= 24 || (size >= 18.66 && weight >= 700)) ? 3 : 4.5;
    let worst = 99;
    layers(el).forEach((b) => { const f = fgBase.a < 1 ? over(fgBase, b) : fgBase; const c = ratio(f, b); if (c < worst) worst = c; });
    if (worst + 0.005 < need) { seen.add(el); bad.push((el.id || el.className || el.tagName) + ' ' + text.slice(0, 16) + ' ' + (Math.round(worst * 100) / 100)); }
  }
  return bad;
}
"""


def run():
    # 원본 HTML(정적 인라인 검사용) — 라이브 URL
    src = urllib.request.urlopen(URL, timeout=30).read().decode("utf-8")
    statics = [x for x in re.findall(r'style="([^"]*)"', src) if "' +" not in x]
    ok("live 정적 인라인 style 474 → 200개 이하", len(statics) <= 200, len(statics))
    banned = ["margin-top", "margin-bottom", "margin-left", "margin-right", "font-size", "font-weight"]
    bad = [x for x in statics if any(re.search(r"(^|;)\s*" + b + r"\s*:", x) for b in banned)]
    ok("live 여백·글자 인라인 0(클래스로 회수)", bad == [], bad[:2])
    ok("live v35 유틸리티 클래스 포함", ".mt-10{margin-top:10px!important}" in src and ".c-cap{color:var(--text-caption)!important}" in src)

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files"])
        for (w, h, mob) in [(320, 568, True), (375, 812, True), (1280, 800, False)]:
            ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if mob else 1,
                                      is_mobile=mob, has_touch=mob, locale="ko-KR")
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
            page.goto(URL, wait_until="load")
            page.wait_for_function("window.__ttokttokBooted === true", timeout=20000)
            page.wait_for_timeout(500)
            ok("live %d 앱 버전 v35" % w, page.evaluate("() => document.querySelector('meta[name=app-version]').content") == "v35")
            ok("live %d :root 한 곳" % w, page.evaluate("""() => {
                const css = document.documentElement.innerHTML.match(/<style>([\\s\\S]*?)<\\/style>/)[1];
                return (css.match(/:root\\{/g) || []).length === 1;
              }"""))
            tok = page.evaluate("""() => { const cs = getComputedStyle(document.documentElement);
                return { cap: cs.getPropertyValue('--text-caption').trim(), muted: cs.getPropertyValue('--text-muted').trim(),
                         sp4: cs.getPropertyValue('--sp-4').trim(), fs11h: cs.getPropertyValue('--fs-11h').trim(),
                         pill: cs.getPropertyValue('--r-pill').trim(), zs: cs.getPropertyValue('--z-sheet').trim() }; }""")
            ok("live %d 토큰 값(캡션 #626B7A·보조 #58617A·16px·11.5px·999px·130)" % w,
               tok == {"cap": "#626B7A", "muted": "#58617A", "sp4": "16px", "fs11h": "11.5px", "pill": "999px", "zs": "130"}, tok)
            gate_bad = page.evaluate(CONTRAST_JS)
            ok("live %d 게이트 화면 대비 AA 미달 0" % w, gate_bad == [], gate_bad[:2])
            page.screenshot(path=os.path.join(SHOT, "live_v35_%d_gate.png" % w))
            page.eval_on_selector('[data-login="customer"]', "el => el.click()")
            page.wait_for_timeout(520)
            for name, prep in [("home", "() => {}"),
                               ("teachers", "() => document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]').click()"),
                               ("journal", "() => document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=journal]').click()")]:
                page.evaluate(prep)
                page.wait_for_timeout(460)
                ok("live %d %s 대비 AA 미달 0" % (w, name), page.evaluate(CONTRAST_JS) == [], page.evaluate(CONTRAST_JS)[:2])
                if name == "home":
                    page.screenshot(path=os.path.join(SHOT, "live_v35_%d_home.png" % w))
            m = page.evaluate("() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})")
            ok("live %d 가로 넘침 없음" % w, m["sw"] <= m["cw"] + 1, m)
            cnt = page.evaluate("() => document.querySelectorAll('[style]').length")
            ok("live %d 인라인 style 최소화(동적 포함 %d개)" % (w, cnt), cnt < 900, cnt)
            ok("live %d JS 오류 없음" % w, not errors, errors[:2])
            ctx.close()
        browser.close()

    print("\nLIVE RESULT: %d passed, %d failed" % (passed, failed))
    for f in fails:
        print(" - " + f)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())
