#!/usr/bin/env python3
"""
똑똑쌤 v24 모바일·접근성·성능 QA (Chromium)
─────────────────────────────────────────
· 뷰포트 320×568 / 375×812 / 1280×800 에서 주요 화면·시트를 실제로 열어
  가로 넘침(scrollWidth > clientWidth), 버튼 클릭 가능 여부, 콘솔 오류를 본다.
· 접근성: 접근성 이름 없는 버튼, label 없는 입력, img alt, role=dialog/aria-modal,
  aria-labelledby 대상 존재, Escape 닫기·포커스 이동, aria-live 상태 알림.
· 성능: DOMContentLoaded / load, 파일 크기, localStorage 차단 폴백.
· 실행: python3 tests/qa_v24.py   (결과물 preview/v24_*.png)
"""
import os
import sys
import json
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
# 로컬(워크스페이스)에서만 쓰는 시스템 라이브러리 경로 — CI(Ubuntu)에는 없다
_LDLP_OK = os.path.isdir("/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu")
if _LDLP_OK:
    os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")

from playwright.sync_api import sync_playwright

URL = "file://" + os.path.join(ROOT, "index.html")
SHOT = os.path.join(ROOT, "preview")

passed, failed, failures = 0, 0, []
issues = {"overflow": [], "unnamed": [], "unlabeled": [], "noalt": [], "dialog": [], "refs": [],
          "target": [], "live": [], "escape": [], "focus": [], "headings": [], "blocked": [],
          "touch": [], "gap": [], "wrap": [], "dates": [], "dday": [], "badtext": [],
          "clip": [], "ell": []}
visited = {}


def ok(name, cond, extra=""):
    global passed, failed
    if cond:
        passed += 1
        print("  ✓ " + name)
    else:
        failed += 1
        failures.append(name + (" :: " + str(extra) if extra else ""))
        print("  ✗ " + name + (" :: " + str(extra) if extra else ""))


def shot(page, name):
    page.screenshot(path=os.path.join(SHOT, "v24_%s.png" % name))


# v40 · 화면 글자가 말하는 날짜·요일·D-day가 달력과 맞는지 본다.
#   예전 시드·마크업이 굳어 있으면(오늘 · 11월 25일 (수), 11.28 (금), 12/01 (월)) 여기서 걸린다.
#   연도가 없는 MM.DD 는 오늘에서 가장 가까운 해로 본다(연말·연초 대비).
TEXT_JS = r"""
() => {
  const out = {dates: [], dday: [], badtext: []};
  const WD = ['일', '월', '화', '수', '목', '금', '토'];
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const nearDate = (m, d) => {
    let best = null;
    [today.getFullYear() - 1, today.getFullYear(), today.getFullYear() + 1].forEach((y) => {
      const t = new Date(y, m - 1, d);
      if (t.getMonth() !== m - 1 || t.getDate() !== d) return;
      const diff = Math.abs(t.getTime() - today.getTime());
      if (!best || diff < best.diff) best = {diff, t};
    });
    return best ? best.t : null;
  };
  const vis = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return !(s.display === 'none' || s.visibility === 'hidden' || Number(s.opacity) === 0 || r.width < 1 || r.height < 1);
  };
  const seen = new Set();
  const push = (kind, msg) => { const k = kind + '|' + msg; if (seen.has(k)) return; seen.add(k); out[kind].push(msg); };
  const DATE = /(?<![\d.])(\d{1,2})[./](\d{1,2})\s*\((월|화|수|목|금|토|일)\)/g;
  const MD = /(?<![\d.])(\d{1,2})월\s*(\d{1,2})일\s*\((월|화|수|목|금|토|일)\)/g;
  const DDAY = /D-(\d+)/;
  const BAD = /(undefined|NaN|\[object |__LOGODATA|\{\{|Infinity|null원)/;
  document.querySelectorAll('body *').forEach((el) => {
    if (!vis(el)) return;
    const txt = (el.innerText || '').replace(/\s+/g, ' ').trim();
    if (!txt || txt.length > 160) return;
    let m;
    DATE.lastIndex = 0;
    while ((m = DATE.exec(txt))) {
      const t = nearDate(+m[1], +m[2]);
      if (!t) continue;
      const real = WD[t.getDay()];
      if (real !== m[3]) push('dates', m[0] + ' → 실제 ' + real + ' :: ' + txt.slice(0, 60));
    }
    MD.lastIndex = 0;
    while ((m = MD.exec(txt))) {
      const t = nearDate(+m[1], +m[2]);
      if (!t) continue;
      const real = WD[t.getDay()];
      if (real !== m[3].trim()) push('dates', m[0] + ' → 실제 ' + real + ' :: ' + txt.slice(0, 60));
      if (/오늘/.test(txt) && (t.getMonth() !== today.getMonth() || t.getDate() !== today.getDate())) {
        push('dates', '오늘인데 ' + m[0] + ' :: ' + txt.slice(0, 60));
      }
    }
    const dd = DDAY.exec(txt);
    if (dd) {
      /* v42: 카드 머리의 '11.27 기준'(오늘)과 방문 날짜가 한 문장에 같이 있다.
         D-day와 가장 가까이 있는 날짜를 그 D-day의 날짜로 본다. */
      const reAll = /(?<![\d.])(\d{1,2})[./](\d{1,2})(?!\d)/g;
      let best = null, mm;
      while ((mm = reAll.exec(txt))) {
        const dist = Math.abs(mm.index - dd.index);
        if (!best || dist < best.dist) best = { dist, m: mm[0], mo: +mm[1], d: +mm[2] };
      }
      if (best) {
        const t = nearDate(best.mo, best.d);
        if (t) {
          const diff = Math.round((t.getTime() - today.getTime()) / 86400000);
          if (String(diff) !== dd[1]) push('dday', 'D-' + dd[1] + ' vs ' + best.m + ' → 실제 D-' + diff + ' :: ' + txt.slice(0, 60));
        }
      }
    }
    const bad = BAD.exec(txt);
    if (bad) push('badtext', bad[0] + ' :: ' + txt.slice(0, 60));
  });
  return out;
}
"""


AUDIT_JS = r"""
() => {
  const out = {overflow: [], unnamed: [], unlabeled: [], noalt: [], dialog: [], refs: [], target: [], headings: []};
  const vw = document.documentElement.clientWidth;
  const vis = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    if (s.visibility === 'hidden' || s.display === 'none' || Number(s.opacity) === 0) return false;
    if (r.width < 1 || r.height < 1) return false;
    // 화면 밖 고정 요소(시트 백드롭 등)는 제외: 조상이 display:none이면 위에서 걸러진다
    return true;
  };
  const label = (el) => (el.id ? '#' + el.id : (typeof el.className === 'string' && el.className.trim() ? '.' + el.className.trim().split(/\s+/).join('.') : el.tagName.toLowerCase()));
  // 1) 가로 넘침: 문서 + 개별 요소
  if (document.documentElement.scrollWidth > vw + 1) {
    out.overflow.push('document.scrollWidth=' + document.documentElement.scrollWidth + ' > ' + vw);
    document.querySelectorAll('body *').forEach((el) => {
      if (!vis(el)) return;
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      if (s.position === 'fixed') return;
      if (r.right > vw + 1.5 && r.width <= vw + 1) out.overflow.push(label(el) + ' right=' + Math.round(r.right) + ' w=' + Math.round(r.width));
      if (r.left < -1.5) out.overflow.push(label(el) + ' left=' + Math.round(r.left));
    });
  }
  const nameOf = (el) => {
    let n = (el.getAttribute('aria-label') || '').trim();
    if (!n && el.getAttribute('aria-labelledby')) {
      n = el.getAttribute('aria-labelledby').split(/\s+/).map((id) => {
        const t = document.getElementById(id); return t ? t.textContent : '';
      }).join(' ').replace(/\s+/g, ' ').trim();
    }
    if (!n) n = (el.getAttribute('title') || '').trim();
    if (!n) n = (el.textContent || '').replace(/\s+/g, ' ').trim();
    if (!n && el.tagName === 'INPUT') {
      const t = el.getAttribute('type');
      if (t === 'submit' || t === 'button') n = (el.value || '').trim();
    }
    return n;
  };
  // 2) 접근성 이름 없는 조작 요소
  document.querySelectorAll('button, [role="button"], a[href], input[type="submit"], input[type="button"]').forEach((el) => {
    if (!vis(el)) return;
    if (!nameOf(el)) out.unnamed.push(label(el));
  });
  // 3) label 연결 없는 입력
  document.querySelectorAll('input:not([type="hidden"]), select, textarea').forEach((el) => {
    if (!vis(el)) return;
    const id = el.id;
    const has = (id && document.querySelector('label[for="' + id + '"]')) || el.closest('label') ||
      el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') || el.getAttribute('title') ||
      el.getAttribute('placeholder') && el.getAttribute('aria-describedby');
    if (!has) out.unlabeled.push(label(el));
  });
  // 4) img alt
  document.querySelectorAll('img').forEach((el) => { if (!el.hasAttribute('alt')) out.noalt.push(label(el)); });
  // 5) dialog 3종 속성
  document.querySelectorAll('[role="dialog"]').forEach((el) => {
    const lb = el.getAttribute('aria-labelledby');
    const al = (el.getAttribute('aria-label') || '').trim();
    if (!el.getAttribute('aria-modal') || !(lb || al)) out.dialog.push(label(el));
    if (lb) {
      const ids = el.getAttribute('aria-labelledby').split(/\s+/);
      const text = ids.map((id) => document.getElementById(id)).map((t) => t ? t.textContent.trim() : '').join('');
      if (!text && !al) out.dialog.push(label(el) + ' aria-labelledby 대상 없음/빈 값');
    }
  });
  // 6) aria-*·for 참조 대상 존재(aria-label 대체 이름이 있으면 통과)
  ['aria-labelledby', 'aria-describedby', 'aria-controls'].forEach((attr) => {
    document.querySelectorAll('[' + attr + ']').forEach((el) => {
      if (!el.getAttribute(attr)) return;
      if (attr === 'aria-labelledby' && (el.getAttribute('aria-label') || '').trim()) return;
      el.getAttribute(attr).split(/\s+/).forEach((id) => {
        if (!document.getElementById(id)) out.refs.push(label(el) + ' ' + attr + '=' + id);
      });
    });
  });
  document.querySelectorAll('label[for]').forEach((el) => {
    if (!document.getElementById(el.getAttribute('for'))) out.refs.push(label(el) + ' for=' + el.getAttribute('for'));
  });
  // 7) 320px 터치 목표(24px 미만) — 아이콘 버튼 위주
  document.querySelectorAll('button, [role="button"], a[href]').forEach((el) => {
    if (!vis(el)) return;
    const r = el.getBoundingClientRect();
    if (r.width < 24 || r.height < 24) out.target.push(label(el) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
  });
  // 8) 화면마다 h1
  document.querySelectorAll('section.screen.is-active').forEach((el) => {
    if (!el.querySelector('h1, h2')) out.headings.push(label(el) + ' 제목 없음');
  });
  // 9) 버튼이 다른 요소에 가려져 있지 않은지(중심점 히트 테스트)
  out.blocked = [];
  var openDialogs = [].slice.call(document.querySelectorAll('.sheet-backdrop.is-open, .backdrop.is-open, .gate.is-open'));
  var topDialog = openDialogs.length ? openDialogs[openDialogs.length - 1] : null;
  document.querySelectorAll('button, [role="button"], a[href]').forEach((el) => {
    if (!vis(el) || el.disabled) return;
    if (topDialog && !topDialog.contains(el)) return; /* 열린 시트 뒤 배경은 가려지는 게 정상 */
    const r = el.getBoundingClientRect();
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    if (cx < 0 || cy < 0 || cx > window.innerWidth || cy > window.innerHeight) return;
    const hit = document.elementFromPoint(cx, cy);
    if (!hit) return;
    if (hit.closest('.tabbar')) return; /* 스크롤로 고정 탭바 아래 지나가는 것은 정상 */
    const hs = getComputedStyle(hit);
    if (hs.position === 'fixed') return;
    if (hit !== el && !el.contains(hit) && !(hit.closest && hit.closest('button,[role="button"],a[href]') === el) &&
        !(el.tagName === 'LABEL' && hit.closest('label') === el)) {
      out.blocked.push(label(el) + ' ← ' + label(hit));
    }
  });
  /* 10) v31 · 터치 영역 44px·인접 간격 8px·CTA 두 줄 접힘(앱 자체 감사 훅) */
  out.touch = []; out.gap = []; out.wrap = [];
  if (window.__ttokttokTouch) {
    (window.__ttokttokTouch.violations() || []).forEach((v) => {
      out.touch.push((v.id || v.cls || '?') + ' ' + v.w + 'x' + v.h + ' "' + (v.text || '') + '"');
    });
    (window.__ttokttokTouch.gapViolations() || []).forEach((g) => {
      out.gap.push(g.parent + ' ' + g.a + '↔' + g.b + '=' + g.gap + 'px');
    });
  }
  document.querySelectorAll('.btn, .wiz-nav button, .sheet-foot button').forEach((el) => {
    const st = getComputedStyle(el);
    if (st.display === 'none' || st.visibility === 'hidden') return;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return;
    const range = document.createRange();
    range.selectNodeContents(el);
    const tops = [];
    [...range.getClientRects()].filter((x) => x.width > 1 && x.height > 1)
      .forEach((x) => { if (!tops.some((y) => Math.abs(y - x.top) < 7)) tops.push(x.top); });
    if (tops.length >= 2) {
      /* v42: 글자 크기 '아주 크게'에서 긴 문구가 버튼 폭을 가득 채우면 두 줄을 허용한다.
         (잘리지 않고 읽히는 것이 우선. 버튼 높이는 내용만큼 늘어난다)
         나란히 놓인 버튼은 글자가 커지면 세로로 서므로 여기 걸리지 않는다. */
      const big = !!document.documentElement.getAttribute('data-textsize');
      const longFull = big && el.textContent.trim().length > 12;
      if (!longFull) out.wrap.push((el.id || el.className) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height) + ' "' + el.textContent.trim().slice(0, 20) + '"');
    }
  });
  /* 11) v41 · 글자 잘림 / 말줄임: 글자가 상자 밖으로 잘렸거나 …로 가려진 곳 */
  out.clip = []; out.ell = [];
  document.querySelectorAll('body *').forEach((el) => {
    if (!vis(el)) return;
    const st = getComputedStyle(el);
    const own = Array.from(el.childNodes).some((n) => n.nodeType === 3 && n.textContent.trim());
    if (!own) return;
    if (el.scrollWidth > el.clientWidth + 1) {
      if (st.textOverflow === 'ellipsis') out.ell.push(label(el) + ' "' + el.textContent.trim().slice(0, 26) + '"');
      else if (st.overflowX === 'hidden' || st.overflowX === 'clip') out.clip.push(label(el) + ' "' + el.textContent.trim().slice(0, 26) + '"');
    }
    if (el.scrollHeight > el.clientHeight + 2 && (st.overflowY === 'hidden' || st.overflowY === 'clip')
        && st.display !== 'inline' && st.lineHeight !== 'normal') {
      out.clip.push(label(el) + ' h ' + el.scrollHeight + '>' + el.clientHeight + ' "' + el.textContent.trim().slice(0, 22) + '"');
    }
  });
  return out;
}
"""


def audit(page, state, tag, buckets):
    # v33 · 화면을 열 때 도는 입장 애니메이션(.pick.is-on springPop 0.28s 등) 중에 치수를 재면
    #   44px 칩이 43px로 측정된다. 측정 전에 진행 중인 애니메이션(무한 반복 제외)이 끝나기를 기다린다.
    #   애니메이션이 없으면 즉시 돌아오고, 있어도 최대 400ms만 기다린다(기준 44px은 그대로).
    try:
        page.evaluate("""() => Promise.race([
          Promise.all(document.getAnimations()
            .filter(a => { const t = (a.effect && a.effect.getTiming) ? a.effect.getTiming() : {}; return t.iterations !== Infinity; })
            .map(a => a.finished.catch(() => {}))),
          new Promise(r => setTimeout(r, 400))
        ])""")
    except Exception:
        pass
    visited.setdefault(tag.strip(), []).append(state)
    r = page.evaluate(AUDIT_JS)
    try:
        t = page.evaluate(TEXT_JS)
        for k in ('dates', 'dday', 'badtext'):
            for item in t.get(k, []):
                buckets[k].append(state + ' :: ' + item)
    except Exception:
        pass
    for k, v in r.items():
        if k == 'overflow':
            for item in v:
                buckets['overflow'].append(state + ' :: ' + item)
        elif k in ('unnamed', 'unlabeled', 'noalt', 'dialog', 'target', 'headings', 'blocked',
                   'touch', 'gap', 'wrap', 'clip', 'ell'):
            for item in v:
                buckets[k].append(state + ' :: ' + item)
        elif k == 'refs':
            for item in v:
                buckets['refs'].append(state + ' :: ' + item)
    for m in r.get('unnamed', []):
        pass


def open_sheet(page, sid):
    page.evaluate("(id) => { const s = document.getElementById(id); if (s) s.classList.add('is-open'); }", sid)


def close_sheet(page, sid):
    page.evaluate("(id) => { const s = document.getElementById(id); if (s) s.classList.remove('is-open'); }", sid)


def nav_tab(page, tab):
    page.eval_on_selector('.tabbar .tabbtn[data-tab="%s"]' % tab, "el => el.click()")
    page.wait_for_timeout(220)


def run_viewport(p, label, w, h, mobile=True, storage_blocked=False, textsize=None, theme=None):
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    ctx = browser.new_context(
        viewport={"width": w, "height": h}, device_scale_factor=1,
        is_mobile=mobile, has_touch=mobile, locale="ko-KR",
        user_agent=("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
                    if mobile else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    )
    if storage_blocked:
        ctx.add_init_script("""
          Object.defineProperty(window, 'localStorage', {
            configurable: true,
            get() { throw new DOMException('SecurityError', 'SecurityError'); }
          });
        """)
    if textsize:
        # v42 · 사용자 글자 크기(보통·크게·아주 크게)로 열어 같은 전수 점검을 다시 돈다.
        ctx.add_init_script("try{localStorage.setItem('ttokttok_textsize_v1','%s')}catch(e){}" % textsize)
    if theme:
        # v45 · 화면 테마(light/dark). 부트 스크립트가 첫 페인트 전에 적용한다.
        ctx.add_init_script("try{localStorage.setItem('ttokttok_theme_v1','%s')}catch(e){}" % theme)
    page = ctx.new_page()
    errors = []
    net = []
    page.on("pageerror", lambda e: errors.append("pageerror:" + str(e)))
    page.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
    page.on("requestfailed", lambda r: net.append(r.url))
    page.on("response", lambda r: net.append(str(r.status) + " " + r.url) if r.status >= 400 else None)
    page.goto(URL)
    page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
    tag = "[%s] " % label
    buckets = {k: [] for k in issues.keys()}

    perf = page.evaluate("""() => {
      const n = performance.getEntriesByType('navigation')[0] || {};
      const res = performance.getEntriesByType('resource') || [];
      return {dcl: Math.round(n.domContentLoadedEventEnd || 0), load: Math.round(n.loadEventEnd || 0),
              req: res.length, transfer: Math.round(res.reduce((a, b) => a + (b.transferSize || 0), 0))};
    }""")

    # ── 시작 화면·게이트 시트
    audit(page, "gate", tag, buckets)
    ok(tag + "시작 화면 가로 넘침 없음", not [x for x in buckets['overflow'] if x.startswith('gate ::')],
       [x for x in buckets['overflow'] if x.startswith('gate ::')][:3])
    page.eval_on_selector("#gateCta", "el => el.click()")
    page.wait_for_timeout(250)
    audit(page, "gateSheet", tag, buckets)
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    ok(tag + "Escape로 휴대폰 번호 시트 닫힘", page.eval_on_selector("#gateSheet", "el => !el.classList.contains('is-open')"))
    page.eval_on_selector("#gateRegionBtn", "el => el.click()")
    page.wait_for_timeout(250)
    audit(page, "regionSheet", tag, buckets)
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    ok(tag + "Escape로 서비스 지역 시트 닫힘", page.eval_on_selector("#regionSheet", "el => !el.classList.contains('is-open')"))

    if storage_blocked:
        # 저장 차단 폴백: 부팅·로그인·예약 화면까지 동작
        page.eval_on_selector('[data-login="customer"]', "el => el.click()")
        page.wait_for_timeout(300)
        nav_tab(page, "booking")
        ok(tag + "저장 차단 상태에서도 예약 화면 렌더", page.is_visible("#bookingWizard"))
        audit(page, "storage-blocked/booking", tag, buckets)
        ok(tag + "저장 차단 상태 JS 오류 없음", not errors, errors[:2])
        for k in ('overflow', 'unnamed', 'unlabeled', 'noalt', 'dialog', 'refs', 'target', 'headings', 'touch', 'gap', 'wrap', 'dates', 'dday', 'badtext'):
            if buckets[k]:
                issues[k].extend(buckets[k])
        browser.close()
        return perf

    # ── 고객 모드
    page.eval_on_selector('[data-login="customer"]', "el => el.click()")
    page.wait_for_timeout(300)
    for tab in ["home", "teachers", "booking", "journal", "mypage"]:
        nav_tab(page, tab)
        audit(page, "customer/" + tab, tag, buckets)
    ok(tag + "고객 5개 화면 가로 넘침 없음",
       not [x for x in buckets['overflow'] if x.startswith('customer/')], [x for x in buckets['overflow'] if x.startswith('customer/')][:3])

    # 선생님 찾기: 목록 → 상세 시트 → 내 주변
    nav_tab(page, "teachers")
    page.eval_on_selector("#teacherList .teacher", "el => el.click()")
    page.wait_for_timeout(300)
    # v46 · 1280px 이상은 카드를 누르면 오른쪽 상세 열이 열린다(시트는 '전체 프로필 보기'에서).
    #        시트 자체의 이름·넘침·초점 검사는 그대로 하기 위해, 닫혀 있으면 열어서 본다.
    pane_open = page.evaluate("() => { const p = document.getElementById('teacherPane'); return !!p && !p.hidden; }")
    if pane_open:
        audit(page, "teacherPane", tag, buckets)
    if not page.evaluate("() => document.getElementById('teacherSheet').classList.contains('is-open')"):
        page.evaluate("() => document.getElementById('teacherSheet').classList.add('is-open')")
        page.wait_for_timeout(260)
    audit(page, "teacherSheet", tag, buckets)
    ok(tag + "시트 열면 초점이 시트 안으로", page.evaluate("() => window.__ttokttokModel.a11y.focusInside('#teacherSheet')"))
    ok(tag + "선생님 상세 시트 가로 넘침 없음", not [x for x in buckets['overflow'] if x.startswith('teacherSheet ::')],
       [x for x in buckets['overflow'] if x.startswith('teacherSheet ::')][:3])
    page.eval_on_selector("#sheetChat", "el => el.click()")
    page.wait_for_timeout(320)
    audit(page, "chatSheet", tag, buckets)
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    ok(tag + "Escape로 1:1 문의 시트 닫힘", page.eval_on_selector("#chatSheet", "el => !el.classList.contains('is-open')"))
    page.keyboard.press("Escape")
    page.wait_for_timeout(220)
    ok(tag + "Escape로 선생님 시트 닫힘 후 초점이 원래 버튼으로", page.evaluate(
        "() => document.activeElement && document.activeElement.classList.contains('teacher')"))
    page.eval_on_selector('#teacherViewTabs [data-view="near"]', "el => el.click()")
    page.wait_for_timeout(350)
    audit(page, "teachers/near", tag, buckets)
    page.eval_on_selector('#teacherViewTabs [data-view="list"]', "el => el.click()")
    page.wait_for_timeout(200)

    # 예약 1~3단계
    nav_tab(page, "booking")
    page.eval_on_selector('#provinceQuick [data-prov="서울"]', "el => el.click()")
    page.select_option("#bookDistrict", "강남구")
    page.fill("#bookAddress", "대치동 123-4, 101동 1203호")
    page.eval_on_selector('#bookSyms [data-val="뇌졸중·편마비"]', "el => el.click()")
    page.eval_on_selector('[data-next="1"]', "el => el.click()")
    page.wait_for_timeout(300)
    audit(page, "booking/step2", tag, buckets)
    page.eval_on_selector("#bookDates .date-chip", "el => el.click()")
    page.wait_for_timeout(150)
    page.eval_on_selector("#bookSlots .slot:not([disabled])", "el => el.click()")
    page.eval_on_selector('[data-next="2"]', "el => el.click()")
    page.wait_for_timeout(300)
    audit(page, "booking/step3", tag, buckets)
    page.eval_on_selector('#passList [data-pass="p8"]', "el => el.click()")
    page.wait_for_timeout(200)
    audit(page, "booking/step3-pass", tag, buckets)
    page.eval_on_selector('[data-next="3"]', "el => el.click()")
    page.wait_for_timeout(300)
    audit(page, "booking/step4", tag, buckets)
    ok(tag + "예약 4단계 가로 넘침 없음", not [x for x in buckets['overflow'] if x.startswith('booking/')],
       [x for x in buckets['overflow'] if x.startswith('booking/')][:3])

    # 고객 시트: 내 정보·알림·쿠폰·FAQ·안전·가이드·모드전환·결제수단
    nav_tab(page, "mypage")
    page.eval_on_selector("#mpBookLink", "el => el.click()")
    page.wait_for_timeout(250)
    audit(page, "accountSheet", tag, buckets)
    page.eval_on_selector("[data-manage]", "el => el.click()")
    page.wait_for_timeout(280)
    audit(page, "manageSheet", tag, buckets)
    page.keyboard.press("Escape")
    page.wait_for_timeout(180)
    ok(tag + "Escape로 내역 시트 닫힘", page.eval_on_selector("#manageSheet", "el => !el.classList.contains('is-open')"))
    if page.eval_on_selector_all("#accountSheet [data-review]", "els => els.length"):
        page.eval_on_selector("#accountSheet [data-review]", "el => el.click()")
        page.wait_for_timeout(280)
        audit(page, "reviewSheet", tag, buckets)
        page.keyboard.press("Escape")
        page.wait_for_timeout(180)
        ok(tag + "Escape로 후기 시트 닫힘", page.eval_on_selector("#reviewSheet", "el => !el.classList.contains('is-open')"))
    # v29 · 방문 완료 예약 기준 후기 시트(별점·태그 5종·1회 1후기 안내)
    if page.eval_on_selector_all("#accountSheet [data-review-booking]", "els => els.length"):
        page.eval_on_selector("#accountSheet [data-review-booking]", "el => el.click()")
        page.wait_for_timeout(280)
        audit(page, "reviewSheet/v29", tag, buckets)
        ok(tag + "v29 예약 후기 시트 가로 넘침 없음",
           not [x for x in buckets['overflow'] if x.startswith('reviewSheet/v29 ::')],
           [x for x in buckets['overflow'] if x.startswith('reviewSheet/v29 ::')][:3])
        ok(tag + "v29 예약 후기 시트(태그 5·1회 1후기 안내)",
           page.eval_on_selector_all("#reviewTags [data-rtag]", "els => els.length") == 5 and
           page.is_visible("#reviewRuleNote"))
        page.keyboard.press("Escape")
        page.wait_for_timeout(180)
        ok(tag + "Escape로 예약 후기 시트 닫힘",
           page.eval_on_selector("#reviewSheet", "el => !el.classList.contains('is-open')"))
    # v29 · 원클릭 재예약 → 예약 1단계(미리 채움)
    if page.eval_on_selector_all("#accountSheet [data-rebook]", "els => els.length"):
        page.eval_on_selector("#accountSheet [data-rebook]", "el => el.click()")
        page.wait_for_timeout(320)
        audit(page, "booking/rebook", tag, buckets)
        ok(tag + "v29 재예약 1단계 넘침 없음",
           not [x for x in buckets['overflow'] if x.startswith('booking/rebook ::')],
           [x for x in buckets['overflow'] if x.startswith('booking/rebook ::')][:3])
        ok(tag + "v29 재예약 배너·1회권 선택",
           page.is_visible("#rebookBanner") and
           page.eval_on_selector('#passList [data-pass="p1"]', "el => el.classList.contains('is-on')"))
        nav_tab(page, "mypage")
        page.wait_for_timeout(220)
    page.keyboard.press("Escape")
    page.wait_for_timeout(180)
    ok(tag + "Escape로 예약 내역 시트 닫힘", page.eval_on_selector("#accountSheet", "el => !el.classList.contains('is-open')"))
    page.eval_on_selector("#mpNotifRow", "el => el.click()")
    page.wait_for_timeout(250)
    audit(page, "notifSheet", tag, buckets)
    page.keyboard.press("Escape")
    page.wait_for_timeout(180)
    ok(tag + "Escape로 알림 시트 닫힘", page.eval_on_selector("#notifSheet", "el => !el.classList.contains('is-open')"))
    # v27 · 알림 문구 미리보기 시트
    page.evaluate("""() => window.__ttokttokModel.openNotifPreview({
        id: 'qa-v27', kind: 'visit', title: 'QA 알림 문구 확인', body: 'QA 미리보기 본문입니다.', audience: 'customer' })""")
    page.wait_for_timeout(300)
    audit(page, "notifPreviewSheet", tag, buckets)
    ok(tag + "알림 미리보기 시트 가로 넘침 없음",
       not [x for x in buckets['overflow'] if x.startswith('notifPreviewSheet ::')],
       [x for x in buckets['overflow'] if x.startswith('notifPreviewSheet ::')][:3])
    ok(tag + "알림 미리보기 초점이 시트 안으로",
       page.evaluate("() => window.__ttokttokModel.a11y.focusInside('#notifPreviewSheet')"))
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    ok(tag + "Escape로 알림 미리보기 시트 닫힘",
       page.eval_on_selector("#notifPreviewSheet", "el => !el.classList.contains('is-open')"))
    page.eval_on_selector("#mpCouponRow", "el => el.click()")
    page.wait_for_timeout(250)
    audit(page, "couponSheet", tag, buckets)
    page.keyboard.press("Escape")
    page.wait_for_timeout(180)
    page.eval_on_selector("#mpGuideLink", "el => el.click()")
    page.wait_for_timeout(250)
    audit(page, "guideSheet", tag, buckets)
    page.keyboard.press("Escape")
    page.wait_for_timeout(180)
    page.eval_on_selector("#mpRoleRow", "el => el.click()")
    page.wait_for_timeout(250)
    audit(page, "roleSheet", tag, buckets)
    page.keyboard.press("Escape")
    page.wait_for_timeout(180)
    page.eval_on_selector("#mpPayRow", "el => el.click()")
    page.wait_for_timeout(250)
    audit(page, "paySheet", tag, buckets)
    page.keyboard.press("Escape")
    page.wait_for_timeout(180)
    ok(tag + "Escape로 결제수단 시트 닫힘", page.eval_on_selector("#paySheet", "el => !el.classList.contains('is-open')"))

    nav_tab(page, "journal")
    page.eval_on_selector("[data-safety-open]", "el => el.click()")
    page.wait_for_timeout(250)
    audit(page, "safetySheet", tag, buckets)
    ok(tag + "안전 안내 시트 가로 넘침 없음", not [x for x in buckets['overflow'] if x.startswith('safetySheet ::')],
       [x for x in buckets['overflow'] if x.startswith('safetySheet ::')][:3])
    page.keyboard.press("Escape")
    page.wait_for_timeout(180)
    ok(tag + "Escape로 안전 안내 시트 닫힘", page.eval_on_selector("#safetySheet", "el => !el.classList.contains('is-open')"))
    if page.is_visible("#weeklyOpen"):
        page.eval_on_selector("#weeklyOpen", "el => el.click()")
        page.wait_for_timeout(280)
        audit(page, "weeklySheet", tag, buckets)
        page.keyboard.press("Escape")
        page.wait_for_timeout(180)
        ok(tag + "Escape로 주간 리포트 시트 닫힘", page.eval_on_selector("#weeklySheet", "el => !el.classList.contains('is-open')"))
    if page.is_visible("#reportOpen"):
        page.eval_on_selector("#reportOpen", "el => el.click()")
        page.wait_for_timeout(300)
        audit(page, "reportSheet", tag, buckets)
        page.keyboard.press("Escape")
        page.wait_for_timeout(180)
        ok(tag + "Escape로 성장 리포트 시트 닫힘", page.eval_on_selector("#reportSheet", "el => !el.classList.contains('is-open')"))

    # FAQ/약관 시트
    nav_tab(page, "mypage")
    page.eval_on_selector("#mpFaqRow", "el => el.click()")
    page.wait_for_timeout(280)
    audit(page, "faqSheet", tag, buckets)
    page.keyboard.press("Escape")
    page.wait_for_timeout(180)
    ok(tag + "Escape로 FAQ·약관 시트 닫힘", page.eval_on_selector("#faqSheet", "el => !el.classList.contains('is-open')"))

    # ────────────────────────────────────────
    # 선생님 모드
    page.evaluate("() => document.getElementById('entryGate').classList.add('is-open')")
    page.wait_for_timeout(120)
    page.eval_on_selector('[data-login="therapist"]', "el => el.click()")
    page.wait_for_timeout(320)
    for tab in ["tp-home", "tp-schedule", "tp-journal", "tp-settle", "tp-mypage"]:
        nav_tab(page, tab)
        audit(page, "partner/" + tab, tag, buckets)
    # v26 · 정산 명세서 미리보기 시트
    nav_tab(page, "tp-settle")
    page.eval_on_selector("#tpsScreen [data-stl-preview]", "el => el.click()")
    page.wait_for_timeout(340)
    audit(page, "settlementPrintSheet", tag, buckets)
    ok(tag + "정산 명세서 미리보기 시트 가로 넘침 없음",
       not [x for x in buckets['overflow'] if x.startswith('settlementPrintSheet ::')],
       [x for x in buckets['overflow'] if x.startswith('settlementPrintSheet ::')][:3])
    ok(tag + "정산 명세서 미리보기 초점이 시트 안으로",
       page.evaluate("() => window.__ttokttokModel.a11y.focusInside('#settlementPrintSheet')"))
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    ok(tag + "Escape로 정산서 미리보기 시트 닫힘",
       page.eval_on_selector("#settlementPrintSheet", "el => !el.classList.contains('is-open')"))
    # v27 · 선생님 알림함 전체 보기 시트
    page.eval_on_selector("[data-tp-noti-open]", "el => el.click()")
    page.wait_for_timeout(320)
    audit(page, "tpNotiSheet", tag, buckets)
    ok(tag + "선생님 알림 시트 가로 넘침 없음",
       not [x for x in buckets['overflow'] if x.startswith('tpNotiSheet ::')],
       [x for x in buckets['overflow'] if x.startswith('tpNotiSheet ::')][:3])
    ok(tag + "선생님 알림 시트 초점이 시트 안으로",
       page.evaluate("() => window.__ttokttokModel.a11y.focusInside('#tpNotiSheet')"))
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    ok(tag + "Escape로 선생님 알림 시트 닫힘",
       page.eval_on_selector("#tpNotiSheet", "el => !el.classList.contains('is-open')"))
    # 가능 시간·지역 편집기 렌더
    page.evaluate("() => { const b = document.querySelector('[data-tp-avail-edit]'); if (b) b.click(); }")
    page.wait_for_timeout(250)
    audit(page, "partner/avail", tag, buckets)
    ok(tag + "선생님 5개 화면 가로 넘침 없음", not [x for x in buckets['overflow'] if x.startswith('partner/')],
       [x for x in buckets['overflow'] if x.startswith('partner/')][:3])

    # ────────────────────────────────────────
    # 관리자
    page.evaluate("() => document.getElementById('entryGate').classList.add('is-open')")
    page.wait_for_timeout(120)
    page.eval_on_selector('[data-login="admin"]', "el => el.click()")
    page.wait_for_timeout(420)
    audit(page, "admin", tag, buckets)
    ok(tag + "관리자 콘솔 가로 넘침 없음", not [x for x in buckets['overflow'] if x.startswith('admin ::')],
       [x for x in buckets['overflow'] if x.startswith('admin ::')][:3])
    ok(tag + "관리자 백업 카드·큐 렌더", page.is_visible("#adminBackupSec") and page.is_visible("#adminResvSec"))
    ok(tag + "v27 관리자 리마인드 미리보기 보드 렌더",
       page.is_visible("#adminReminderSec") and page.eval_on_selector_all("#adminReminderQueue [data-reminder]", "els => els.length") >= 1)
    # v28 · 운영 지표 대시보드(기간 칩·KPI·지역·SLA)
    ok(tag + "v28 운영 지표 섹션·KPI 6장", page.is_visible("#adminMetricsSec") and
       page.eval_on_selector_all("#adminMetricsKpis [data-kpi]", "els => els.length") == 6 and
       page.eval_on_selector_all("#adminMetricsPeriods [data-metrics-period]", "els => els.length") == 3)
    page.eval_on_selector('#adminMetricsPeriods [data-metrics-period="7d"]', "el => el.click()")
    page.wait_for_timeout(260)
    ok(tag + "v28 기간 칩 7일 전환", page.evaluate("() => window.__ttokttokModel.adminMetricsState().period") == "7d")
    audit(page, "adminMetrics/7d", tag, buckets)
    ok(tag + "v28 운영 지표 7일 화면 가로 넘침 없음",
       not [x for x in buckets['overflow'] if x.startswith('adminMetrics/7d ::')],
       [x for x in buckets['overflow'] if x.startswith('adminMetrics/7d ::')][:3])
    page.eval_on_selector('#adminMetricsPeriods [data-metrics-period="all"]', "el => el.click()")
    page.wait_for_timeout(220)

    # 화면별 스크린샷(320만)
    if label == "320":
        shot(page, "320_admin")
        nav_tab(page, "tp-home") if page.is_visible('.tabbar[data-mode="therapist"]') else None

    ok(tag + "전 화면 콘솔·페이지 오류 0", not errors, errors[:3])
    ok(tag + "네트워크 실패·5xx 0", not net, net[:3])
    for k in ('overflow', 'unnamed', 'unlabeled', 'noalt', 'dialog', 'refs', 'target', 'headings', 'blocked',
              'touch', 'gap', 'wrap'):
        if buckets[k]:
            issues[k].extend(buckets[k])
    browser.close()
    return perf


def run_v32_states(p):
    """v32 · 빈 상태·오류 띠 화면을 뷰포트별로 열어 넘침·감사·구조를 본다."""
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files"])
    for label, w, h, mobile in [("320", 320, 568, True), ("375", 375, 812, True), ("1280", 1280, 800, False)]:
        tag = "[v32 %s] " % label
        ctx = browser.new_context(viewport={"width": w, "height": h}, is_mobile=mobile, has_touch=mobile, locale="ko-KR")
        ctx.add_init_script("""try {
          localStorage.setItem('ttokttok_account_v3', JSON.stringify({
            passes: [], bookings: [], receipts: [], sessions: [], myReviews: [], profile: { name: '현수' } }));
        } catch (e) {}""")
        page = ctx.new_page()
        errors, net = [], []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
        page.on("response", lambda r: net.append("%s %s" % (r.status, r.url)) if r.status >= 400 else None)
        page.goto(URL)
        page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
        page.wait_for_timeout(320)

        # ① 데이터가 빈 계정(초기 스크립트로 시드) → 통일 빈 상태 4곳
        page.eval_on_selector('[data-login="customer"]', "el => el.click()")
        page.wait_for_timeout(260)
        page.eval_on_selector("#homeTicketBtn", "el => el.click()")
        page.wait_for_timeout(320)

        buckets = {k: [] for k in ('overflow', 'unnamed', 'unlabeled', 'noalt', 'dialog', 'refs', 'target',
                                   'headings', 'blocked', 'touch', 'gap', 'wrap', 'clip', 'ell')}
        audit(page, "empty/account", tag, buckets)

        empty = page.evaluate("""() => {
          const out = [];
          document.querySelectorAll('.empty[data-empty]').forEach((el) => {
            const r = el.getBoundingClientRect();
            out.push({key: el.getAttribute('data-empty'), cta: !!el.querySelector('.btn'),
                      desc: !!el.querySelector('p'), vis: r.width > 1 && r.height > 1 && !el.hidden});
          });
          return out;
        }""")
        keys = [x["key"] for x in empty]
        ok(tag + "빈 계정 통일 빈 상태 4곳", all(k in keys for k in ("wallet-passes", "booking-list", "receipts", "journal-timeline")), keys)
        ok(tag + "빈 상태 모두 한 줄 설명 + CTA", len(empty) >= 4 and all(x["cta"] and x["desc"] for x in empty), empty[:4])
        ok(tag + "앱 자체 빈 상태 감사 위반 0", page.evaluate("() => window.__ttokttokUI.audit().length") == 0,
           page.evaluate("() => window.__ttokttokUI.audit().slice(0, 3)"))
        ok(tag + "빈 상태 화면 가로 넘침 없음", not [x for x in buckets['overflow'] if x.startswith('empty/account ::')],
           [x for x in buckets['overflow'] if x.startswith('empty/account ::')][:3])
        ok(tag + "빈 상태 터치 영역·간격 위반 0", not buckets['touch'] and not buckets['gap'],
           (buckets['touch'] + buckets['gap'])[:3])
        if label in ("320", "375"):
            page.screenshot(path=os.path.join(SHOT, "v32_%s_empty_account.png" % label))

        # ② 저장 실패 띠 레이아웃(가로 넘침·버튼 터치)
        page.evaluate("() => { document.querySelector('#accountSheet').classList.remove('is-open'); }")
        page.evaluate("() => window.__ttokttokV32.simulateStorageFailure(true)")
        page.evaluate("() => window.__ttokttokV32.saveAccountNow()")
        page.wait_for_timeout(260)
        buckets2 = {k: [] for k in ('overflow', 'unnamed', 'unlabeled', 'noalt', 'dialog', 'refs', 'target',
                                    'headings', 'blocked', 'touch', 'gap', 'wrap')}
        audit(page, "alert/banner", tag, buckets2)
        ok(tag + "저장 실패 띠 표시 + 다시 저장 버튼",
           page.query_selector('#ttAlertHost [data-retry="account-save"]') is not None)
        ok(tag + "띠 화면 가로 넘침 없음", not [x for x in buckets2['overflow'] if x.startswith('alert/banner ::')],
           [x for x in buckets2['overflow'] if x.startswith('alert/banner ::')][:3])
        if label in ("320", "375"):
            page.screenshot(path=os.path.join(SHOT, "v32_%s_storage_banner.png" % label))
        ok(tag + "v32 화면 콘솔·페이지 오류 0", not errors, errors[:3])
        ok(tag + "v32 네트워크 실패·5xx 0", not net, net[:3])
        for k in buckets:
            if buckets[k]:
                issues[k].extend(buckets[k])
        for k in buckets2:
            if buckets2[k]:
                issues[k].extend(buckets2[k])
        ctx.close()
    browser.close()


def run_v33_states(p):
    """v33 · 첫 방문 전 홈(빈 계정)을 뷰포트별로 열어 넘침·터치·구조를 본다."""
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files"])
    for label, w, h, mobile in [("320", 320, 568, True), ("375", 375, 812, True), ("1280", 1280, 800, False)]:
        tag = "[v33 %s] " % label
        ctx = browser.new_context(viewport={"width": w, "height": h}, is_mobile=mobile, has_touch=mobile, locale="ko-KR")
        ctx.add_init_script("""try {
          localStorage.setItem('ttokttok_account_v3', JSON.stringify({
            passes: [], bookings: [], receipts: [], sessions: [], myReviews: [], profile: { name: '현수' } }));
        } catch (e) {}""")
        page = ctx.new_page()
        errors, net = [], []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
        page.on("response", lambda r: net.append("%s %s" % (r.status, r.url)) if r.status >= 400 else None)
        page.goto(URL)
        page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
        page.wait_for_timeout(320)
        page.eval_on_selector('[data-login="customer"]', "el => el.click()")
        page.wait_for_timeout(360)

        buckets = {k: [] for k in ('overflow', 'unnamed', 'unlabeled', 'noalt', 'dialog', 'refs', 'target',
                                   'headings', 'blocked', 'touch', 'gap', 'wrap', 'clip', 'ell')}
        audit(page, "v33/first-visit", tag, buckets)
        st = page.evaluate("() => window.__ttokttokModel.homeStageState()")
        ok(tag + "첫 방문 전 홈 — 첫 카드가 첫 방문 안내",
           st["firstCardVisible"] and not st["summaryVisible"] and st["firstElement"] == "homeFirstVisitCard",
           json.dumps(st, ensure_ascii=False)[:120])
        ok(tag + "첫 방문 안내 가로 넘침 없음",
           not [x for x in buckets['overflow'] if x.startswith('v33/first-visit ::')],
           [x for x in buckets['overflow'] if x.startswith('v33/first-visit ::')][:3])
        ok(tag + "첫 방문 안내 터치·간격 위반 0", not buckets['touch'] and not buckets['gap'],
           (buckets['touch'] + buckets['gap'])[:3])
        ok(tag + "첫 방문 안내 CTA 두 줄 접힘 0", not [x for x in buckets['wrap'] if x.startswith('v33/first-visit ::')],
           [x for x in buckets['wrap'] if x.startswith('v33/first-visit ::')][:3])
        ok(tag + "빈 상태 감사 위반 0(첫 방문 전)", page.evaluate("() => window.__ttokttokUI.audit().length") == 0,
           page.evaluate("() => window.__ttokttokUI.audit().slice(0, 3)"))
        if label in ("320", "375"):
            page.screenshot(path=os.path.join(SHOT, "v33_%s_first_visit_home.png" % label))
        # 이용 중(기본 시드)으로 바꿔 요약 카드가 첫 카드인지 — 미리보기 경로로 데이터를 건드리지 않고 확인
        page.evaluate("() => window.__ttokttokModel.setStagePreview('active')")
        page.wait_for_timeout(260)
        st2 = page.evaluate("() => window.__ttokttokModel.homeStageState()")
        ok(tag + "미리보기(active) — 요약 카드가 앞으로",
           st2["summaryVisible"] and not st2["firstCardVisible"] and st2["firstElement"] == "homeSummaryCard")
        page.evaluate("() => window.__ttokttokModel.setStagePreview('')")
        page.wait_for_timeout(200)
        ok(tag + "v33 화면 콘솔·페이지 오류 0", not errors, errors[:3])
        ok(tag + "v33 네트워크 실패·5xx 0", not net, net[:3])
        for k in buckets:
            if buckets[k]:
                issues[k].extend(buckets[k])
        ctx.close()
    browser.close()


def run_v34_states(p):
    """v34 · 시트가 열려 배경이 inert일 때 320/375/1280에서 넘침·터치·이름을 다시 본다."""
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files"])
    cases = [("320", 320, 568, True, "#teacherList .teacher", "#teacherSheet"),
             ("375", 375, 812, True, "#btnNotif", "#notifSheet"),
             ("1280", 1280, 800, False, "#homeTicketBtn", "#accountSheet")]
    for label, w, h, mobile, opener, sheet in cases:
        tag = "[v34 %s] " % label
        ctx = browser.new_context(viewport={"width": w, "height": h}, is_mobile=mobile, has_touch=mobile, locale="ko-KR")
        page = ctx.new_page()
        errors, net = [], []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
        page.on("response", lambda r: net.append("%s %s" % (r.status, r.url)) if r.status >= 400 else None)
        page.goto(URL)
        page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
        page.wait_for_timeout(320)
        # 게이트가 열린 상태(배경 inert)에서도 넘침·이름 감사
        buckets = {k: [] for k in ('overflow', 'unnamed', 'unlabeled', 'noalt', 'dialog', 'refs', 'target',
                                   'headings', 'blocked', 'touch', 'gap', 'wrap', 'clip', 'ell')}
        audit(page, "v34/gate", tag, buckets)
        ok(tag + "게이트 열림 — 배경 inert·이름 감사 0",
           page.evaluate("() => window.__ttokttokModel.a11y.backgroundLocked()") is True and
           not buckets['unnamed'] and not buckets['unlabeled'],
           (buckets['unnamed'] + buckets['unlabeled'])[:3])
        page.eval_on_selector('[data-login="customer"]', "el => el.click()")
        page.wait_for_timeout(380)
        if "teacher" in opener:
            page.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]', "el => el.click()")
            page.wait_for_timeout(320)
        page.eval_on_selector(opener, "el => el.click()")
        page.wait_for_timeout(400)
        state = "v34/sheet-open"
        audit(page, state, tag, buckets)
        ok(tag + "시트 열림 — 최상위·배경 잠금",
           page.evaluate("(s) => window.__ttokttokModel.a11y.topDialog() === s", sheet) and
           page.evaluate("() => window.__ttokttokModel.a11y.backgroundLocked()") is True)
        ok(tag + "시트 열림 — 가로 넘침 0",
           not [x for x in buckets['overflow'] if x.startswith(state + ' ::')],
           [x for x in buckets['overflow'] if x.startswith(state + ' ::')][:3])
        ok(tag + "시트 열림 — 터치·간격 위반 0",
           not [x for x in buckets['touch'] if x.startswith(state + ' ::')] and
           not [x for x in buckets['gap'] if x.startswith(state + ' ::')],
           ([x for x in buckets['touch'] if x.startswith(state + ' ::')] +
            [x for x in buckets['gap'] if x.startswith(state + ' ::')])[:3])
        ok(tag + "시트 열림 — 이름 없는 버튼 0",
           not [x for x in buckets['unnamed'] if x.startswith(state + ' ::')],
           [x for x in buckets['unnamed'] if x.startswith(state + ' ::')][:3])
        if label in ("320", "375"):
            page.screenshot(path=os.path.join(SHOT, "v34_%s_sheet_open.png" % label))
        page.keyboard.press("Escape")
        page.wait_for_timeout(260)
        ok(tag + "닫힌 뒤 배경 잠금 해제", page.evaluate("() => window.__ttokttokModel.a11y.backgroundLocked()") is False)
        ok(tag + "v34 화면 콘솔·페이지 오류 0", not errors, errors[:3])
        ok(tag + "v34 네트워크 실패·5xx 0", not net, net[:3])
        for k in buckets:
            if buckets[k]:
                issues[k].extend(buckets[k])
        ctx.close()
    browser.close()

CONTRAST_JS_V35 = r"""
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
    if (worst + 0.005 < need) { seen.add(el); bad.push((el.id || el.className || el.tagName) + ' ' + text.slice(0, 18) + ' ' + (Math.round(worst * 100) / 100)); }
  }
  return bad;
}
"""


def run_v35_states(p):
    """v35 · 디자인 토큰·대비 — 320/375/1280에서 주요 화면·시트의 넘침·대비를 다시 본다."""
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files"])
    cases = [
        ("320", 320, 568, True),
        ("375", 375, 812, True),
        ("1280", 1280, 800, False),
    ]
    states = [
        ("home", "() => {}"),
        ("teachers", "() => document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]').click()"),
        ("journal", "() => document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=journal]').click()"),
        ("account", "() => document.querySelector('#homeTicketBtn').click()"),
    ]
    for label, w, h, mobile in cases:
        tag = "[v35 %s] " % label
        ctx = browser.new_context(viewport={"width": w, "height": h}, is_mobile=mobile, has_touch=mobile, locale="ko-KR")
        page = ctx.new_page()
        errors, net = [], []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
        page.on("response", lambda r: net.append("%s %s" % (r.status, r.url)) if r.status >= 400 else None)
        page.goto(URL)
        page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
        page.wait_for_timeout(320)
        # 게이트도 대비 검사 대상(로그인 전 화면)
        gate_bad = page.evaluate(CONTRAST_JS_V35)
        ok(tag + "게이트 화면 글자 대비 AA 미달 0", gate_bad == [], gate_bad[:3])
        page.eval_on_selector('[data-login="customer"]', "el => el.click()")
        page.wait_for_timeout(400)
        ok(tag + "토큰이 해석됨(:root 하나)", page.evaluate("""() => {
            const css = document.documentElement.innerHTML.match(/<style>([\\s\\S]*?)<\\/style>/)[1];
            return (css.match(/:root\\{/g) || []).length === 1 &&
              getComputedStyle(document.documentElement).getPropertyValue('--text-caption').trim() === '#626B7A';
          }"""))
        for name, prep in states:
            page.evaluate(prep)
            page.wait_for_timeout(420)
            over = page.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
            ok(tag + "%s 가로 넘침 0" % name, over <= 0, over)
            bad = page.evaluate(CONTRAST_JS_V35)
            ok(tag + "%s 글자 대비 AA 미달 0" % name, bad == [], bad[:3])
            if name == "account":
                page.keyboard.press("Escape")
                page.wait_for_timeout(240)
        ok(tag + "화면 콘솔·페이지 오류 0", not errors, errors[:3])
        ok(tag + "네트워크 실패·5xx 0", not net, net[:3])
        ctx.close()
    browser.close()


def run_perf(p):
    """로컬 초기 로딩 지표 + 저장 차단 폴백."""
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files"])
    ctx = browser.new_context(viewport={"width": 375, "height": 812}, is_mobile=True, has_touch=True)
    page = ctx.new_page()
    page.goto(URL)
    page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
    m = page.evaluate("""() => {
      const n = performance.getEntriesByType('navigation')[0] || {};
      return {dcl: Math.round(n.domContentLoadedEventEnd || 0), load: Math.round(n.loadEventEnd || 0),
              dom: Math.round(n.domInteractive || 0), nodes: document.querySelectorAll('*').length};
    }""")
    size = os.path.getsize(os.path.join(ROOT, "index.html"))
    ok("초기 로딩 DOMContentLoaded 1.5초 이내", m["dcl"] < 1500, m)
    ok("초기 로딩 load 2초 이내", m["load"] < 2000, m)
    # v27 알림·리마인드 센터 코드 추가로 상한을 1.2MB → 1.3MB로 조정(2026-11-26).
    # v29 후기 신뢰 배지·재예약 UI 추가로 1.3MB → 1.45MB로 조정(2026-11-26, v29~v30 대비).
    ok("index.html 1.45MB 이하", size <= 1450 * 1024, size)
    print("    · index.html {:,} bytes · nodes {:,} · DCL {}ms · load {}ms".format(size, m["nodes"], m["dcl"], m["load"]))
    browser.close()
    return size, m


def main():
    """QA_PART=1 → 320/375/1280 전 화면 순회, QA_PART=2 → 저장차단·v32 상태·성능.
    (한 번에 5분을 넘겨 실행 도구 시간 한도에 걸리는 환경이 있어 나눠 돌릴 수 있게 한다.
     나누지 않으면 기본값 all 로 전부 돈다.)"""
    part = os.environ.get("QA_PART", "all").strip() or "all"
    with sync_playwright() as p:
        perf = {}
        if part in ("all", "1"):
            for label, w, h, mobile in [("320", 320, 568, True), ("375", 375, 812, True), ("1280", 1280, 800, False)]:
                perf[label] = run_viewport(p, label, w, h, mobile=mobile)
        if part in ("all", "3"):
            # v40 · 아이폰 14/15 기준 폭(390)도 같은 순서로 돈다.
            perf["390"] = run_viewport(p, "390", 390, 844, mobile=True)
        if part in ("all", "4"):
            # v42 · 글자 크기 '아주 크게'(1.3)에서도 같은 점검을 통과해야 한다.
            perf["390-xl"] = run_viewport(p, "390-xl", 390, 844, mobile=True, textsize="xl")
            perf["320-xl"] = run_viewport(p, "320-xl", 320, 568, mobile=True, textsize="xl")
        if part in ("all", "5"):
            # v45 · 다크 모드에서도 같은 전수 점검(넘침·터치·이름·오류)을 통과해야 한다.
            perf["390-dark"] = run_viewport(p, "390-dark", 390, 844, mobile=True, theme="dark")
            perf["320-dark"] = run_viewport(p, "320-dark", 320, 568, mobile=True, theme="dark")
        if part in ("all", "6"):
            # v46 · 태블릿 768(세로) — 앱 폭 720·카드 두 열·시트 640에서도 같은 점검을 통과해야 한다.
            perf["768"] = run_viewport(p, "768", 768, 1024, mobile=True)
        if part in ("all", "7"):
            # v47 · 작은 데스크톱 1024(레일 + 카드 두 열)와 다크 1280(3칸·스켈레톤)도 같은 점검을 통과해야 한다.
            perf["1024"] = run_viewport(p, "1024", 1024, 900, mobile=False)
            perf["1280-dark"] = run_viewport(p, "1280-dark", 1280, 900, mobile=False, theme="dark")
        if part in ("all", "8"):
            # v48 · 휴대폰 가로모드(짧은 화면) — 430px 우편함을 없애고 헤더·탭바를 줄인 뒤에도
            #        전 화면이 가로로 넘치지 않고, 시트·버튼이 화면 안에서 눌리는지 본다.
            perf["844x390"] = run_viewport(p, "844x390", 844, 390, mobile=True)
            perf["667x375"] = run_viewport(p, "667x375", 667, 375, mobile=True)
        if part in ("all", "2"):
            run_viewport(p, "375-blocked", 375, 812, mobile=True, storage_blocked=True)
            run_v32_states(p)
            run_v33_states(p)
            run_v34_states(p)
            run_v35_states(p)
            size, m = run_perf(p)
            perf["size"] = size

    print("\n=== 접근성·레이아웃 지적 사항 ===")
    for k in ('overflow', 'unnamed', 'unlabeled', 'noalt', 'dialog', 'refs', 'target', 'headings', 'blocked',
              'touch', 'gap', 'wrap', 'dates', 'dday', 'badtext', 'clip', 'ell'):
        uniq = sorted(set(issues[k]))
        print("· %s: %d%s" % (k, len(uniq), ("" if not uniq else "\n    " + "\n    ".join(uniq[:25]))))

    # 수집된 지적 사항을 판정으로 전환(회귀 시 실패)
    for k, name in [('overflow', '가로 넘침 0'), ('unnamed', '접근성 이름 없는 버튼 0'),
                    ('unlabeled', 'label 없는 입력 0'), ('noalt', 'alt 없는 이미지 0'),
                    ('dialog', 'role=dialog·aria-modal·이름 누락 0'), ('refs', '깨진 aria·for 참조 0'),
                    ('headings', '제목 없는 화면 0')]:
        ok(name, len(set(issues[k])) == 0, sorted(set(issues[k]))[:5])
    print("· blocked(정보·실클릭은 E2E에서 전수 확인): %d" % len(set(issues['blocked'])))
    # v31 · 터치 영역 44px·간격 8px·CTA 한 줄 (전 화면 × 320/375/1280)
    ok("터치 영역 44px 미만 요소 0", len(set(issues['touch'])) == 0, sorted(set(issues['touch']))[:6])
    ok("인접 컨트롤 간격 8px 미만 0", len(set(issues['gap'])) == 0, sorted(set(issues['gap']))[:6])
    ok("주요 CTA 두 줄 접힘 0", len(set(issues['wrap'])) == 0, sorted(set(issues['wrap']))[:6])
    tap = sorted(set(x.split(' :: ', 1)[1] for x in issues['target']))
    ok("24px 미만 텍스트 요소는 12개 이하(기존 디자인 유지)", len(tap) <= 12, tap[:5])
    # v40 · 화면 글자의 날짜·요일·D-day가 달력과 일치
    ok("날짜-요일 불일치 0", len(set(issues['dates'])) == 0, sorted(set(issues['dates']))[:6])
    ok("D-day-날짜 불일치 0", len(set(issues['dday'])) == 0, sorted(set(issues['dday']))[:6])
    ok("깨진 글자(undefined·NaN 등) 0", len(set(issues['badtext'])) == 0, sorted(set(issues['badtext']))[:6])
    # v41 · 텍스트 붕괴: 잘린 글자 0 · 말줄임으로 가려진 이름/주소 0
    ok("글자 잘림(overflow로 가려진 글자) 0", len(set(issues['clip'])) == 0, sorted(set(issues['clip']))[:6])
    ok("말줄임으로 가려진 글자 0", len(set(issues['ell'])) == 0, sorted(set(issues['ell']))[:6])

    print("\nPERF: " + json.dumps(perf, ensure_ascii=False))
    print("STATES: " + json.dumps({k: len(v) for k, v in visited.items()}, ensure_ascii=False))
    for k, v in visited.items():
        print("  %s(%d): %s" % (k, len(v), ", ".join(v)))

    print("\nRESULT: %d passed, %d failed" % (passed, failed))
    if failures:
        print("FAILURES:")
        for f in failures:
            print(" - " + f)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(2)
