#!/usr/bin/env python3
"""
똑똑쌤 v51 · 인쇄/PDF 출력 호환성 검사 (Chromium → 실제 PDF)
─────────────────────────────────────────────────────────────
화면을 인쇄 상태로 바꾼 뒤 Chromium이 만든 **실제 PDF 파일**을 열어 페이지마다
  1) 글자가 있는지(빈 쪽 0)
  2) 그림이 실제로 그려졌는지(픽셀 분산 — 백지 판정)
  3) 반복 머리말·꼬리말이 쪽마다 있는지
를 본다. 함께 인쇄 상태에서 '백지 위험' 계산 스타일(그림자·backdrop-filter·mask·filter·
불투명도<1·fixed)이 글자 요소에 남아 있는지 센다.

실행:  python3 tests/print_pdf_v51.py
결과:  preview/v51-print/{문서}_{폭}.pdf · {문서}_{폭}_p{n}.png
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
if os.path.isdir("/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu"):
    os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")

from playwright.sync_api import sync_playwright
import pymupdf

URL = "file://" + os.path.join(ROOT, "index.html")
OUT = os.path.join(ROOT, "preview", "v51-print")
os.makedirs(OUT, exist_ok=True)

RISK_JS = r"""
() => {
  const risk = {shadow: [], blur: [], mask: [], filter: [], opacity: [], fixed: [], blend: [], transform: []};
  const vis = (el) => {
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden') return false;
    const r = el.getBoundingClientRect();
    return r.width >= 1 && r.height >= 1;
  };
  const hasText = (el) => Array.from(el.childNodes).some((n) => n.nodeType === 3 && n.textContent.trim());
  document.querySelectorAll('body *').forEach((el) => {
    if (!hasText(el) || !vis(el)) return;
    if (el.closest('[data-print-hide], .sprite')) return;
    const s = getComputedStyle(el);
    const tag = (el.id ? '#' + el.id : el.tagName.toLowerCase() + '.' + String(el.className || '').trim().split(/\s+/).slice(0, 2).join('.'));
    if (s.boxShadow && s.boxShadow !== 'none') risk.shadow.push(tag);
    if ((s.backdropFilter && s.backdropFilter !== 'none') || (s.webkitBackdropFilter && s.webkitBackdropFilter !== 'none')) risk.blur.push(tag);
    if ((s.maskImage && s.maskImage !== 'none') || (s.webkitMaskImage && s.webkitMaskImage !== 'none')) risk.mask.push(tag);
    if (s.filter && s.filter !== 'none') risk.filter.push(tag);
    if (parseFloat(s.opacity) < 1) risk.opacity.push(tag + ' ' + s.opacity);
    if (s.position === 'fixed') risk.fixed.push(tag);
    if (s.mixBlendMode && s.mixBlendMode !== 'normal') risk.blend.push(tag);
    if (s.transform && s.transform !== 'none') risk.transform.push(tag);
  });
  Object.keys(risk).forEach((k) => { risk[k] = Array.from(new Set(risk[k])).slice(0, 8); });
  return risk;
}
"""

RUNNER_JS = r"""
() => {
  const r = document.getElementById('printRunner');
  const f = document.getElementById('printFoot');
  const vis = (el) => {
    if (!el) return null;
    const s = getComputedStyle(el);
    const b = el.getBoundingClientRect();
    return {display: s.display, pos: s.position, text: (el.textContent || '').trim().slice(0, 60),
            h: Math.round(b.height), top: Math.round(b.top), bottom: Math.round(b.bottom)};
  };
  return {runner: vis(r), foot: vis(f), pages: window.__ttokttokPrintPages || null};
}
"""


def enter(page, role, tab=None, mode=None):
    page.wait_for_function("window.__ttokttokBooted === true", timeout=30000)
    page.wait_for_timeout(300)
    page.eval_on_selector('[data-login="%s"]' % role, "el=>el.click()")
    page.wait_for_timeout(700)
    if tab:
        page.eval_on_selector('.tabbar[data-mode="%s"] .tabbtn[data-tab="%s"]' % (mode or "customer", tab), "el=>el.click()")
        page.wait_for_timeout(700)


def settle_sheet(page):
    enter(page, "therapist", "tp-settle", "therapist")
    page.evaluate("() => { const b = document.querySelector('[data-stl-preview]'); if (b) b.click(); }")
    page.wait_for_timeout(800)


def settle_screen(page):
    enter(page, "therapist", "tp-settle", "therapist")


def admin(page):
    enter(page, "admin")


def journal(page):
    enter(page, "customer", "journal")


def weekly(page):
    enter(page, "customer", "journal")
    page.evaluate("() => { const b = document.querySelector('#weeklyOpen'); if (b) b.click(); }")
    page.wait_for_timeout(700)


CASES = [("settle", settle_sheet), ("settle_screen", settle_screen), ("admin", admin), ("journal", journal), ("weekly", weekly)]

passed, failed, failures = 0, 0, []


def ok(name, cond, extra=""):
    global passed, failed
    if cond:
        passed += 1
        print("  ✓ " + name)
    else:
        failed += 1
        failures.append(name + (" :: " + str(extra) if extra else ""))
        print("  ✗ " + name + (" :: " + str(extra) if extra else ""))


def page_stats(pdf_path, tag):
    doc = pymupdf.open(pdf_path)
    rows = []
    for i, pg in enumerate(doc):
        text = pg.get_text("text").strip()
        pix = pg.get_pixmap(dpi=72, colorspace=pymupdf.csGRAY)
        samples = pix.samples
        total = max(1, len(samples))
        # 흰 바탕(#fff)이 아닌 픽셀 비율 — 백지는 0에 가깝다
        ink = sum(1 for b in samples if b < 250) / total
        rows.append({"page": i + 1, "chars": len(text), "ink": round(ink, 5),
                     "head": text.split("\n")[0][:40]})
    doc.close()
    return rows


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
        for width, height, mobile in ((390, 844, True), (794, 1123, False), (1280, 900, False)):
            for name, steps in CASES:
                ctx = b.new_context(viewport={"width": width, "height": height}, device_scale_factor=1,
                                    is_mobile=mobile, has_touch=mobile, locale="ko-KR")
                page = ctx.new_page()
                errs = []
                page.on("pageerror", lambda e: errs.append(str(e)))
                page.goto(URL + "?intro=0")
                steps(page)
                page.emulate_media(media="print")
                page.evaluate("() => window.dispatchEvent(new Event('beforeprint'))")
                page.wait_for_timeout(500)
                tag = "%s@%d" % (name, width)
                risk = page.evaluate(RISK_JS)
                runner = page.evaluate(RUNNER_JS)
                pdf_path = os.path.join(OUT, "%s_%d.pdf" % (name, width))
                page.pdf(path=pdf_path, format="A4", print_background=True,
                         margin={"top": "12mm", "bottom": "12mm", "left": "0mm", "right": "0mm"})
                rows = page_stats(pdf_path, tag)
                ok(tag + " PDF 쪽 있음", len(rows) >= 1, len(rows))
                blank = [r for r in rows if r["chars"] < 10 and r["ink"] < 0.002]
                ok(tag + " 빈 쪽 0 (글자·잉크)", not blank, blank[:3])
                ok(tag + " 머리말·꼬리말 인쇄 상태", bool(runner["runner"]) and runner["runner"]["display"] != "none"
                   and bool(runner["runner"]["text"]), runner)
                ok(tag + " 위험 스타일(그림자·블러·마스크) 0",
                   not risk["shadow"] and not risk["blur"] and not risk["mask"] and not risk["filter"],
                   {k: risk[k] for k in ("shadow", "blur", "mask", "filter") if risk[k]})
                ok(tag + " 글자 요소 불투명도 1", not risk["opacity"], risk["opacity"])
                ok(tag + " 페이지 오류 0", not errs, errs[:2])
                for r in rows:
                    doc = pymupdf.open(pdf_path)
                    pix = doc[r["page"] - 1].get_pixmap(dpi=96)
                    pix.save(os.path.join(OUT, "%s_%d_p%d.png" % (name, width, r["page"])))
                    doc.close()
                print("    · %s: %d쪽 글자 %s · 잉크 %s" % (tag, len(rows), [r["chars"] for r in rows], [r["ink"] for r in rows]))
                ctx.close()
        b.close()

    print("\nRESULT: %d 통과 / %d 실패" % (passed, len(failures)))
    if failures:
        for f in failures:
            print("  -", f)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
