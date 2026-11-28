#!/usr/bin/env python3
"""v50 인쇄 줄 맞춤 검사 — 종이에 올리는 문서마다 좌우 세로선이 하나인지 실제 픽셀로 잰다.

검사 항목(문서마다 · 390px·794px 두 폭)
  1. 머리말 글자 왼쪽 = 카드 속 글자 왼쪽
  2. 머리말 오른쪽 글자 끝 = 카드 속 금액 끝
  3. 꼬리말 글자 왼쪽 = 카드 속 글자 왼쪽
  4. 본문 글자가 카드 테두리 밖으로 나간 줄 0(잘림 없음)
  5. 정산서: 회차 목록 글자·금액이 요약 카드와 같은 선
  6. 정산서 머리 카드: 발급줄·규칙줄이 각각 한 줄(‘(15일·말일) 지급’만 떨어지지 않음)

실행: python3 tests/print_align_v50.py
결과물: preview/v50-audit/{문서}_{폭}_print.png
"""
import os, sys
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "file://" + os.path.join(ROOT, "index.html")
OUT = os.path.join(ROOT, "preview", "v50-audit")
os.makedirs(OUT, exist_ok=True)

PROBE = r"""() => {
 const f = window.__ttokttokPrint && window.__ttokttokPrint.frame ? window.__ttokttokPrint.frame() : null;
 const content = document.querySelector('.sheet-backdrop.is-print .sheet-scroll') || document.querySelector('.screen.is-active');
 if (!content || !f) return {frame: null};
 // 본문 글자 상자 — 카드 테두리 밖으로 나간 줄
 const card = content.querySelector('.admin-card') || content.querySelector('.card') || content;
 const cb = card.getBoundingClientRect();
 const out = [];
 const w = document.createTreeWalker(content, NodeFilter.SHOW_TEXT);
 const range = document.createRange();
 let n;
 while ((n = w.nextNode())) {
   const t = (n.nodeValue || '').trim();
   if (!t) continue;
   const p = n.parentElement;
   if (!p || p.closest('#printRunner,#printFoot')) continue;
   const cs = getComputedStyle(p);
   if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) continue;
   range.selectNodeContents(n);
   const rs = range.getClientRects();
   for (let i = 0; i < rs.length; i++) {
     const r = rs[i];
     if (r.width < 2 || r.height < 2) continue;
     if (r.left < cb.left - 0.6 || r.right > cb.right + 0.6) out.push({l: Math.round(r.left), r: Math.round(r.right), s: t.slice(0, 16)});
   }
 }
 // 정산서 머리 카드: 두 줄이 각각 한 줄인지
 const fines = [...content.querySelectorAll('#settlementPrintBody .admin-card:first-child .fine')];
 const metas = fines.map((el) => {
   const rng = document.createRange(); rng.selectNodeContents(el);
   const tops = new Set([...rng.getClientRects()].filter((r) => r.width > 2).map((r) => Math.round(r.top)));
   return { text: el.textContent.trim(), lines: tops.size };
 });
 return {frame: f, outside: out, metas: metas, vw: document.documentElement.clientWidth};
}"""

def enter(page, role, tab=None, mode=None):
    page.wait_for_function("window.__ttokttokBooted === true", timeout=30000)
    page.wait_for_timeout(300)
    page.eval_on_selector('[data-login="%s"]' % role, "el=>el.click()")
    page.wait_for_timeout(700)
    if tab:
        page.eval_on_selector('.tabbar[data-mode="%s"] .tabbtn[data-tab="%s"]' % (mode or "customer", tab), "el=>el.click()")
        page.wait_for_timeout(600)

def settle_sheet(page):
    enter(page, "therapist", "tp-settle", "therapist")
    page.evaluate("() => { const b = document.querySelector('[data-stl-preview]'); if (b) b.click(); }")
    page.wait_for_timeout(700)

def settle_screen(page):
    enter(page, "therapist", "tp-settle", "therapist")

def admin(page):
    enter(page, "admin")

def journal(page):
    enter(page, "customer", "journal")

def weekly(page):
    enter(page, "customer", "journal")
    page.evaluate("""() => { const b = document.querySelector('#weeklyOpen, [data-weekly-open], [data-summary="report"]');
       if (b) b.click(); else if (window.__ttokttokModel && window.__ttokttokModel.weeklyReport) window.__ttokttokModel.weeklyReport(); }""")
    page.wait_for_timeout(700)

CASES = [("settle", settle_sheet), ("settle_screen", settle_screen), ("admin", admin), ("journal", journal), ("weekly", weekly)]
pass_n = 0
fails = []

def ok(name, cond, extra=""):
    global pass_n
    if cond:
        pass_n += 1
    else:
        fails.append("%s :: %s" % (name, extra))
        print("  ✗", name, "::", extra)

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    for width, height, dsf in ((390, 844, 2), (794, 1123, 1)):
        for name, steps in CASES:
            ctx = b.new_context(viewport={"width": width, "height": height}, device_scale_factor=dsf,
                                is_mobile=width < 900, has_touch=width < 900, locale="ko-KR")
            page = ctx.new_page()
            errs = []
            page.on("pageerror", lambda e: errs.append(str(e)))
            page.goto(URL + "?intro=0")
            steps(page)
            page.emulate_media(media="print")
            page.evaluate("() => window.dispatchEvent(new Event('beforeprint'))")
            page.wait_for_timeout(400)
            d = page.evaluate(PROBE)
            tag = "%s@%d" % (name, width)
            f = d["frame"]
            ok(tag + " 인쇄 대상이 있다", bool(f), d)
            if f:
                ok(tag + " 머리말 글자 = 카드 속 글자(왼쪽)", abs(f["runner"]["l"] - f["card"]["l"]) <= 1,
                   [f["runner"]["l"], f["card"]["l"]])
                ok(tag + " 머리말 오른쪽 끝 = 카드 속 금액 끝", abs(f["note"] - f["card"]["r"]) <= 1,
                   [f["note"], f["card"]["r"]])
                ok(tag + " 꼬리말 글자 = 카드 속 글자(왼쪽)", abs(f["foot"]["l"] - f["card"]["l"]) <= 1,
                   [f["foot"]["l"], f["card"]["l"]])
                ok(tag + " 본문이 잘린 줄 0", len(d["outside"]) == 0, d["outside"][:3])
                if name == "settle":
                    ok(tag + " 회차 글자 = 카드 속 글자", abs(f["rowText"] - f["card"]["l"]) <= 1, [f["rowText"], f["card"]["l"]])
                    ok(tag + " 회차 금액 끝 = 카드 속 금액 끝", abs(f["row"]["r"] - f["card"]["r"]) <= 1, [f["row"]["r"], f["card"]["r"]])
                    ok(tag + " 회차 줄이 카드와 같은 폭", abs(f["row"]["boxL"] - f["card"]["boxL"]) <= 1 and abs(f["row"]["boxR"] - f["card"]["boxR"]) <= 1,
                       [f["row"], f["card"]])
                    ok(tag + " 머리 카드 발급줄 한 줄", bool(d["metas"]) and d["metas"][0]["lines"] == 1, d["metas"][:1])
                    ok(tag + " 머리 카드 규칙줄 한 줄", len(d["metas"]) > 1 and d["metas"][1]["lines"] == 1, d["metas"][1:])
            ok(tag + " 페이지 오류 0", not errs, errs[:2])
            page.screenshot(path=os.path.join(OUT, "%s_%d_print.png" % (name, width)), full_page=True)
            ctx.close()
    b.close()

print("\nRESULT: %d 통과 / %d 실패" % (pass_n, len(fails)))
if fails:
    raise SystemExit(1)
