#!/usr/bin/env python3
"""v48 라이브 실브라우저 확인 — 로빙 탭인덱스·경계 3:1·가로모드·인쇄·정산서 시트.

실행: python3 tests/live_check_v48.py
결과물: preview/live_v48_*.png
"""
import hashlib
import os
import urllib.request

os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://lcarisma-ctrl.github.io/-/"
URL = BASE + "?v=48"
OUT = os.path.join(ROOT, "preview")
ok_n = 0
fails = []


def ok(name, cond, extra=""):
    global ok_n
    if cond:
        ok_n += 1
        print("  ✓", name)
    else:
        fails.append("%s :: %s" % (name, extra))
        print("  ✗", name, "::", extra)


def box(pg, sel):
    return pg.evaluate("""(s) => { const el = document.querySelector(s); if (!el) return null;
      const r = el.getBoundingClientRect(); return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width),
      h: Math.round(r.height), r: Math.round(r.right), b: Math.round(r.bottom)}; }""", sel)


# 0) 파일 자체 — HTTP 200 · 로컬과 같은 바이트
local = open(os.path.join(ROOT, "index.html"), "rb").read()
live = urllib.request.urlopen(URL, timeout=30).read()
ok("live ?v=48 HTTP 200 · byte 동일", len(live) == len(local), "%d vs %d" % (len(live), len(local)))
md5 = hashlib.md5(live).hexdigest()
ok("live md5 로컬과 일치", md5 == hashlib.md5(local).hexdigest(), md5)
ok("live meta v48", b'content="v48"' in live)
ok("live 로빙 훅 포함", b"__ttokttokRoving" in live and b"__ttokttokPrint" in live)
for v in (47, 46, 45):
    try:
        r = urllib.request.urlopen(BASE + "?v=%d" % v, timeout=30)
        ok("이전 버전 ?v=%d HTTP 200" % v, r.status == 200, r.status)
    except Exception as e:
        ok("이전 버전 ?v=%d HTTP 200" % v, False, str(e)[:60])

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])

    def make(w, h, mob, theme=None):
        ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if w < 900 else 1,
                            is_mobile=mob, has_touch=mob, locale="ko-KR")
        if theme:
            ctx.add_init_script("try{localStorage.setItem('ttokttok_theme_v1','%s')}catch(e){}" % theme)
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
        pg.goto(URL)
        pg.wait_for_function("window.__ttokttokBooted === true", timeout=30000)
        pg.wait_for_timeout(500)
        return ctx, pg, errs

    def enter(pg, role="customer", tab=None, mode="customer"):
        pg.eval_on_selector('[data-login="%s"]' % role, "el => el.click()")
        pg.wait_for_timeout(650)
        if tab:
            pg.eval_on_selector('.tabbar[data-mode="%s"] .tabbtn[data-tab="%s"]' % (mode, tab), "el => el.click()")
            pg.wait_for_timeout(450)
        try:
            pg.evaluate("() => { const t = document.querySelector('.toast'); if (t) t.style.display = 'none'; }")
        except Exception:
            pass

    # ── 1) 1280 — 로빙 탭인덱스 ──────────────────────────────
    ctx, pg, errs = make(1280, 900, False)
    enter(pg, tab="teachers")
    st = pg.evaluate("""() => { const cs = [...document.querySelectorAll('#teacherList .teacher')];
      return {n: cs.length, stops: cs.filter((c) => c.getAttribute('tabindex') === '0').length,
              hook: !!(window.__ttokttokRoving && window.__ttokttokRoving.version === 'v48')}; }""")
    ok("1280 카드 8장 · Tab 정지점 1개", st["n"] == 8 and st["stops"] == 1, st)
    ok("1280 로빙 훅 v48", st["hook"])
    pg.evaluate("() => { const c = [...document.querySelectorAll('#regionFilters .chip')]; c[c.length - 1].focus(); }")
    pg.keyboard.press("Tab")
    pg.wait_for_timeout(250)
    ok("1280 필터에서 Tab 한 번이면 목록 진입", pg.evaluate(
        "() => !!(document.activeElement.closest && document.activeElement.closest('#teacherList'))"))
    ok("1280 들어오면 낭독 안내", "선생님 목록 8명" in pg.inner_text("#teacherNavLive"), pg.inner_text("#teacherNavLive")[:50])
    pg.keyboard.press("ArrowDown")
    pg.wait_for_timeout(350)
    ok("1280 ↓ 다음 카드 + 프로필 열", pg.evaluate(
        "() => document.activeElement.getAttribute('data-teacher')") == "lee" and
        not pg.evaluate("() => document.getElementById('teacherPane').hidden"))
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(300)
    ok("1280 Enter는 프로필 열 안으로", pg.evaluate(
        "() => document.getElementById('teacherPane').contains(document.activeElement)"))
    ok("1280 오류 0", not errs, errs[:2])
    pg.screenshot(path=os.path.join(OUT, "live_v48_1280_roving.png"))
    ctx.close()

    # ── 2) 375 라이트/다크 — 경계 3:1 실측 ───────────────────
    for theme in ("light", "dark"):
        ctx, pg, errs = make(375, 812, True, theme)
        enter(pg, tab="teachers")
        edge = pg.evaluate("""() => {
          const parse = (c) => { const m = String(c).match(/rgba?\\(([^)]+)\\)/); if (!m) return null;
            const p = m[1].split(/[\\s,\\/]+/).map(Number); return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1}; };
          const lin = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
          const lum = (c) => 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b);
          const bgOf = (el) => { let cur = el; while (cur && cur !== document.documentElement) {
              const c = parse(getComputedStyle(cur).backgroundColor); if (c && c.a > 0.5) return c; cur = cur.parentElement; }
            return parse('rgb(247,248,250)'); };
          const ratio = (a, b) => { const l1 = lum(a), l2 = lum(b); const hi = Math.max(l1, l2), lo = Math.min(l1, l2); return (hi + 0.05) / (lo + 0.05); };
          const pick = (sel) => { for (const el of document.querySelectorAll(sel)) { const r = el.getBoundingClientRect();
              const cs = getComputedStyle(el); if (cs.display === 'none' || r.width < 2 || r.height < 2) continue;
              if (parseFloat(cs.borderTopWidth) < 0.5) continue; const bc = parse(cs.borderTopColor); if (!bc || bc.a === 0) continue;
              return Math.round(ratio(bc, bgOf(el.parentElement || document.body)) * 100) / 100; } return null; };
          return {chip: pick('.chip'), card: pick('.card'),
                  token: getComputedStyle(document.documentElement).getPropertyValue('--edge-ctl').trim()};
        }""")
        ok("%s 칩 테두리 3:1 이상" % theme, edge["chip"] is not None and edge["chip"] >= 3, edge)
        ok("%s 카드는 낮은 대비 선을 그리지 않는다" % theme, edge["card"] is None, edge["card"])
        ok("%s 경계 토큰" % theme, edge["token"] in ("#7E8592", "#6A7280"), edge["token"])
        ok("%s 오류 0" % theme, not errs, errs[:2])
        pg.screenshot(path=os.path.join(OUT, "live_v48_375_%s_teachers.png" % theme))
        ctx.close()

    # ── 3) 가로모드 ─────────────────────────────────────────
    for w, h in [(844, 390), (667, 375)]:
        ctx, pg, errs = make(w, h, True)
        gate = pg.evaluate("""() => { const g = document.getElementById('gateCta').getBoundingClientRect();
          return {b: Math.round(g.bottom), h: Math.round(g.height), vh: innerHeight}; }""")
        ok("%dx%d 시작 화면 CTA가 첫 화면 안" % (w, h), gate["b"] <= gate["vh"] + 2, gate)
        pg.screenshot(path=os.path.join(OUT, "live_v48_land_%d_gate.png" % w))
        enter(pg, tab="teachers")
        m = pg.evaluate("""() => { const q = (s) => { const el = document.querySelector(s); if (!el) return null;
            const r = el.getBoundingClientRect(); return {y: Math.round(r.y), h: Math.round(r.height), w: Math.round(r.width)}; };
          return {vw: innerWidth, vh: innerHeight, docW: document.documentElement.scrollWidth,
            clientW: document.documentElement.clientWidth, app: q('.app'), header: q('.app-header'),
            tabbar: q('.tabbar'), card: q('#teacherList .teacher')}; }""")
        ok("%dx%d 앱이 가로 폭 전체" % (w, h), abs(m["app"]["w"] - m["vw"]) <= 2, m["app"])
        ok("%dx%d 헤더 52px 이하" % (w, h), m["header"]["h"] <= 52, m["header"])
        ok("%dx%d 탭바 52px 이하" % (w, h), m["tabbar"]["h"] <= 52, m["tabbar"])
        ok("%dx%d 가로 넘침 0" % (w, h), m["docW"] <= m["clientW"] + 1, [m["docW"], m["clientW"]])
        ok("%dx%d 첫 카드가 화면 안(y<170)" % (w, h), m["card"] and m["card"]["y"] < 170, m["card"])
        ok("%dx%d 오류 0" % (w, h), not errs, errs[:2])
        pg.screenshot(path=os.path.join(OUT, "live_v48_land_%d_teachers.png" % w))
        ctx.close()

    # ── 4) 인쇄 ─────────────────────────────────────────────
    ctx, pg, errs = make(390, 844, True)
    enter(pg, tab="journal")
    pg.emulate_media(media="print")
    pg.evaluate("() => window.dispatchEvent(new Event('beforeprint'))")
    pg.wait_for_timeout(250)
    pr = pg.evaluate("""() => { const d = (s) => { const el = document.querySelector(s); return el ? getComputedStyle(el).display : 'missing'; };
      return {header: d('.app-header'), tabbar: d('.tabbar'), screen: d('#screen-journal'), tabs: d('.role-switch')}; }""")
    ok("인쇄 — 헤더·탭바 숨김", pr["header"] == "none" and pr["tabbar"] == "none", pr)
    ok("인쇄 — 지금 화면만·보기 탭 제외", pr["screen"] == "block" and pr["tabs"] == "none", pr)
    pg.screenshot(path=os.path.join(OUT, "live_v48_print_journal.png"), full_page=True)
    pg.emulate_media(media="screen")
    ctx.close()

    ctx, pg, errs = make(1280, 900, False)
    enter(pg, role="therapist", tab="tp-settle", mode="therapist")
    pg.evaluate("() => { const b = document.querySelector('[data-stl-preview]'); if (b) b.click(); }")
    pg.wait_for_timeout(500)
    pg.emulate_media(media="print")
    pg.evaluate("() => window.dispatchEvent(new Event('beforeprint'))")
    pg.wait_for_timeout(300)
    pr2 = pg.evaluate("""() => { const d = (s) => { const el = document.querySelector(s); return el ? getComputedStyle(el).display : 'missing'; };
      return {sheet: d('#settlementPrintSheet'), mark: window.__ttokttokPrint.target(),
              shown: [...document.querySelectorAll('.screen')].filter((el) => getComputedStyle(el).display !== 'none').length}; }""")
    ok("인쇄 — 정산서 시트만", pr2["sheet"] == "block" and pr2["mark"] == "settlementPrintSheet", pr2)
    ok("인쇄 — 화면 본문 0", pr2["shown"] == 0, pr2["shown"])
    pg.screenshot(path=os.path.join(OUT, "live_v48_print_settle.png"), full_page=True)
    pg.emulate_media(media="screen")
    ctx.close()
    b.close()

print("\nRESULT: %d passed, %d failed" % (ok_n, len(fails)))
for f in fails:
    print(" - " + f)
raise SystemExit(0 if not fails else 1)
