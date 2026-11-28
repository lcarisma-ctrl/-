#!/usr/bin/env python3
"""똑똑쌤 배포 전 QA 게이트 — 한 번에 돌려 하나라도 실패하면 멈춘다.

v46에서 만든 이유
  v45까지는 대비(WCAG AA) 검사를 손으로 돌려야 했다. 그래서 '라이트 0 / 다크 0'이
  다음 빌드에서도 지켜졌는지 자동으로 확인되는 곳이 없었다. 이 게이트는
    build → jsdom 단위 → Chromium E2E → 전수 QA → 대비(라이트·다크 × 모바일·데스크톱)
  을 정해진 순서로 돌리고, 하나라도 0 failed가 아니면 0이 아닌 코드로 끝난다.

실행:
  cd projects/ttokttok-app && python3 tests/qa_gate.py              # 전부
  python3 tests/qa_gate.py --only contrast                          # 대비만
  python3 tests/qa_gate.py --skip e2e                               # E2E 빼고(빠른 확인)
  python3 tests/qa_gate.py --list                                   # 단계 목록

단계:
  build     템플릿 → index.html (python3 build.py) + 버전 표기 확인
  jsdom     app.test.js(APP_PART=1·2) + app.v32~v51 (node)
  e2e       Chromium E2E 흐름 (E2E_ONLY 묶음)
  qa        qa_v24.py 전수 QA (QA_PART=1~7 — 6은 v46 태블릿 768, 7은 v47 1024·1280 다크)
  contrast  contrast_v45.py 라이트·다크 × 375·768·1024·1280
  print     인쇄 줄 맞춤(print_align_v50) + Chromium PDF 백지 감사(print_pdf_v51)
  format    표기 전수 스캔(format_scan_v51 --gate) — 날짜·시간·금액·전화 규칙 위반 0
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

JSDOM_SUITES = ["app.v32.test.js", "app.v33.test.js", "app.v34.test.js", "app.v35.test.js",
                "app.v36.test.js", "app.v37.test.js", "app.v38.test.js", "app.v39.test.js",
                "app.v40.test.js", "app.v42.test.js", "app.v43.test.js", "app.v44.test.js",
                "app.v45.test.js", "app.v46.test.js", "app.v47.test.js", "app.v48.test.js",
                "app.v49.test.js",
                "app.v50.test.js",
                "app.v51.test.js"]

E2E_CHUNKS = [
    "base,v17,v18",
    "v19,v20,v21",
    "v22,v23,v24",
    "v25,v26,v27",
    "v28,v29,v31",
    "v32,v33,v34",
    "v35,v36,v37",
    "v38,v39,v40",
    "v42,v43,v45",
    "v46,v47,v48,v49,v50,v51",
]

QA_PARTS = ["1", "2", "3", "4", "5", "6", "7", "8"]
CONTRAST = [("light", "375"), ("dark", "375"), ("light", "768"), ("dark", "768"),
            ("light", "1024"), ("dark", "1024"), ("light", "1280"), ("dark", "1280")]

steps_order = ["build", "jsdom", "e2e", "qa", "contrast", "print", "format"]


def node_bin():
    env = os.environ.get("NODE_BIN")
    if env and os.path.exists(env):
        return env
    found = shutil.which("node")
    if found:
        return found
    for base in ("/workspace/.tools", os.path.expanduser("~/.tools")):
        if not os.path.isdir(base):
            continue
        for name in sorted(os.listdir(base), reverse=True):
            cand = os.path.join(base, name, "bin", "node")
            if os.path.exists(cand):
                return cand
    return None


def run(cmd, env=None, cwd=None, label=""):
    e = dict(os.environ)
    if env:
        e.update(env)
    t = time.time()
    print("\n▶ " + (label or " ".join(cmd)), flush=True)
    p = subprocess.run(cmd, cwd=cwd or ROOT, env=e)
    took = time.time() - t
    print("  → exit %d (%.0fs)" % (p.returncode, took), flush=True)
    return p.returncode


def step_build():
    code = run([sys.executable, "build.py"], label="build.py")
    if code:
        return code
    html = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    m = re.search(r'<meta name="app-version" content="(v\d+)">', html)
    tpl = open(os.path.join(ROOT, "src", "app.template.html"), encoding="utf-8").read()
    mt = re.search(r'<meta name="app-version" content="(v\d+)">', tpl)
    if not m or not mt or m.group(1) != mt.group(1):
        print("  ✗ 템플릿과 빌드 결과의 버전 표기가 다릅니다", m and m.group(1), mt and mt.group(1))
        return 1
    print("  ✓ app-version " + m.group(1) + " · " + str(len(html.encode())) + " bytes")
    return 0


def step_jsdom():
    node = node_bin()
    if not node:
        print("  ✗ node 실행 파일을 찾지 못했습니다 (NODE_BIN 환경변수로 지정)")
        return 1
    bad = 0
    for part in ("1", "2"):
        bad |= run([node, "--max-old-space-size=2600", "app.test.js"], {"APP_PART": part},
                   cwd=HERE, label="jsdom app.test.js APP_PART=" + part)
    for suite in JSDOM_SUITES:
        bad |= run([node, "--max-old-space-size=2600", suite], cwd=HERE, label="jsdom " + suite)
    return 1 if bad else 0


def step_e2e():
    bad = 0
    for chunk in E2E_CHUNKS:
        bad |= run([sys.executable, "e2e_chromium.py"], {"E2E_ONLY": chunk},
                   cwd=HERE, label="e2e " + chunk)
    return 1 if bad else 0


def step_qa():
    bad = 0
    for part in QA_PARTS:
        bad |= run([sys.executable, "qa_v24.py"], {"QA_PART": part}, cwd=HERE, label="qa_v24 QA_PART=" + part)
    return 1 if bad else 0


def step_contrast():
    bad = 0
    for theme, viewport in CONTRAST:
        bad |= run([sys.executable, "contrast_v45.py"], {"THEME": theme, "VIEWPORT": viewport},
                   cwd=HERE, label="contrast %s @%s" % (theme, viewport))
    return 1 if bad else 0


def step_print():
    """인쇄 검사 — 줄 맞춤(print_align_v50) + 실제 PDF 백지 판정(print_pdf_v51)."""
    bad = run([sys.executable, "print_align_v50.py"], cwd=HERE, label="print_align_v50")
    bad |= run([sys.executable, "print_pdf_v51.py"], cwd=HERE, label="print_pdf_v51")
    return 1 if bad else 0


def step_format():
    """표기 전수 스캔 — 날짜·시간·금액·전화가 v51 규칙에서 벗어난 곳 0."""
    return run([sys.executable, "format_scan_v51.py", "--gate"], cwd=HERE, label="format_scan_v51")


STEPS = {"build": step_build, "jsdom": step_jsdom, "e2e": step_e2e, "qa": step_qa, "contrast": step_contrast,
         "print": step_print, "format": step_format}


def main():
    ap = argparse.ArgumentParser(description="똑똑쌤 배포 전 QA 게이트")
    ap.add_argument("--only", default="", help="이 단계만 (쉼표 구분): " + ",".join(steps_order))
    ap.add_argument("--skip", default="", help="이 단계는 건너뛴다: " + ",".join(steps_order))
    ap.add_argument("--list", action="store_true", help="단계 목록 출력")
    a = ap.parse_args()
    if a.list:
        for s in steps_order:
            print(s, "—", (STEPS[s].__doc__ or "").strip() or s)
        return 0
    only = [x for x in a.only.split(",") if x]
    skip = [x for x in a.skip.split(",") if x]
    plan = [s for s in steps_order if (not only or s in only) and s not in skip]
    if not plan:
        print("실행할 단계가 없습니다.")
        return 2
    print("QA GATE — " + " → ".join(plan))
    results = []
    t0 = time.time()
    for s in plan:
        code = STEPS[s]()
        results.append((s, code))
        if code:
            print("\n✗ %s 단계에서 실패 — 뒤 단계는 건너뜁니다." % s, flush=True)
            break
    print("\n===== QA GATE 요약 (%.1f분) =====" % ((time.time() - t0) / 60.0))
    for s, code in results:
        print("  %-9s %s" % (s, "OK" if code == 0 else "FAILED"))
    failed = [s for s, code in results if code]
    if failed or len(results) != len(plan):
        print("결과: 실패 (" + ", ".join(failed or ["중단"]) + ")")
        return 1
    print("결과: 전 단계 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
