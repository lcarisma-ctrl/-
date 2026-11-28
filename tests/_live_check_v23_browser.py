"""v23 라이브 실브라우저 점검 — 운영 데이터 백업/복원(JSON)·저장소 어댑터."""
import os
ROOT = "/workspace/projects/ttokttok-app"
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")
from playwright.sync_api import sync_playwright

URL = "https://lcarisma-ctrl.github.io/-/?v=23&live=1"
ok = fail = 0


def check(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1; print("  OK " + name)
    else:
        fail += 1; print("  NG " + name + (" :: " + str(extra)))


with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--font-render-hinting=none"])
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                        is_mobile=True, has_touch=True, locale="ko-KR", accept_downloads=True)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__ttokttokBooted === true", timeout=20000)
    check("라이브 부팅", True)
    check("앱 버전 v23", pg.evaluate("() => document.querySelector('meta[name=app-version]').content") == "v23")
    check("모델 노출(백업·어댑터)",
          pg.evaluate("() => [window.__ttokttokModel.backupVersion, window.__ttokttokModel.snapshotSchema, window.__ttokttokModel.storageAdapter().kind]")
          == ["v23", "ttokttok.v23", "local"])

    # 관리자 콘솔 → 백업 카드
    pg.eval_on_selector('[data-login="customer"]', "el => el.click()")
    pg.wait_for_timeout(300)
    pg.eval_on_selector("[data-admin-open]", "el => el.click()")
    pg.wait_for_timeout(450)
    check("관리자 콘솔 진입", pg.eval_on_selector(".screen.is-active", "el => el.id") == "screen-admin")
    check("백업 카드·버튼 2개", pg.is_visible("#adminBackupCard") and pg.is_visible("#adminBackupExport") and pg.is_visible("#adminBackupPick"))
    counts = pg.inner_text("#adminBackupCounts")
    check("현재 데이터 요약", all(t in counts for t in ["예약", "일지", "정산", "알림", "프로필"]), counts)
    pg.eval_on_selector("#adminBackupCard", "el => el.scrollIntoView({block:'center'})")
    pg.wait_for_timeout(400)
    pg.screenshot(path=os.path.join(ROOT, "preview", "live_v23_admin_backup.png"))

    # 백업 다운로드(실제 파일)
    path = os.path.join(ROOT, "preview", "live_v23_backup.json")
    with pg.expect_download(timeout=8000) as dl:
        pg.tap("#adminBackupExport")
    dl.value.save_as(path)
    check("백업 파일 다운로드", os.path.exists(path) and os.path.getsize(path) > 200, os.path.getsize(path) if os.path.exists(path) else 0)
    hook = pg.evaluate("() => window.__ttokttokBackup || null")
    check("백업 파일 이름·스키마", bool(hook) and hook["schemaVersion"] == "ttokttok.v23" and hook["name"].startswith("ttokttok-backup-"), (hook or {}).get("name"))
    counts_at_export = hook["counts"]

    # 데이터 변경(확정 → 방문 완료) 후 복원
    pg.eval_on_selector('#adminResvFilters [data-admin-resv-filter="confirmed"]', "el => el.click()")
    pg.wait_for_timeout(350)
    before = pg.evaluate("() => (window.__ttokttokModel.reservations().filter(b=>b.no==='TT-261021-7302')[0]||{}).status")
    nbtn = pg.eval_on_selector_all('#adminResvQueue [data-resv="TT-261021-7302"] [data-admin-resv-to="completed"]', "els => els.length")
    if nbtn:
        pg.eval_on_selector('#adminResvQueue [data-resv="TT-261021-7302"] [data-admin-resv-to="completed"]', "el => el.click()")
        pg.wait_for_timeout(450)
    after = pg.evaluate("() => (window.__ttokttokModel.reservations().filter(b=>b.no==='TT-261021-7302')[0]||{}).status")
    check("복원 전 상태 변경", before == "confirmed" and after == "completed", "%s → %s" % (before, after))

    pg.set_input_files("#adminBackupFile", path)
    pg.wait_for_timeout(700)
    check("파일 확인 단계(아직 그대로)",
          pg.eval_on_selector("#adminBackupConfirmBox", "el => el.hidden") is False and
          pg.evaluate("() => !!window.__ttokttokModel.pendingRestore()") and
          pg.evaluate("() => (window.__ttokttokModel.reservations().filter(b=>b.no==='TT-261021-7302')[0]||{}).status") == "completed")
    pg.eval_on_selector("#adminBackupCard", "el => el.scrollIntoView({block:'center'})")
    pg.wait_for_timeout(300)
    pg.screenshot(path=os.path.join(ROOT, "preview", "live_v23_restore_confirm.png"))
    pg.tap("#adminBackupConfirm")
    pg.wait_for_timeout(600)
    check("복원 실행 → 백업 시점 상태", pg.evaluate("() => (window.__ttokttokModel.reservations().filter(b=>b.no==='TT-261021-7302')[0]||{}).status") == "confirmed")
    check("복원 결과 문구", "복원했어요" in pg.inner_text("#adminBackupResult"), pg.inner_text("#adminBackupResult")[:80])
    check("복원 항목 수 = 파일", (pg.evaluate("() => window.__ttokttokRestore.counts") or {}).get("reservations") == counts_at_export.get("reservations"))
    pg.screenshot(path=os.path.join(ROOT, "preview", "live_v23_after_restore.png"))

    # 손상 파일 거부
    broken = os.path.join(ROOT, "preview", "live_v23_backup_broken.json")
    with open(broken, "w", encoding="utf-8") as fp:
        fp.write('{"schemaVersion":"ttokttok.v23","data":{"journals":"x"}}')
    pg.set_input_files("#adminBackupFile", broken)
    pg.wait_for_timeout(700)
    check("손상 파일 거부", "복원하지 않았어요" in pg.inner_text("#adminBackupResult") and
          pg.evaluate("() => (window.__ttokttokModel.reservations().filter(b=>b.no==='TT-261021-7302')[0]||{}).status") == "confirmed",
          pg.inner_text("#adminBackupResult")[:90])

    # 새로고침 유지
    pg.reload(wait_until="load")
    pg.wait_for_function("window.__ttokttokBooted === true", timeout=20000)
    check("새로고침 후 복원값 유지", pg.evaluate("() => (window.__ttokttokModel.reservations().filter(b=>b.no==='TT-261021-7302')[0]||{}).status") == "confirmed")
    check("JS 오류 없음", not errs, errs[:2])
    b.close()

print("\nLIVE RESULT: %d ok, %d ng" % (ok, fail))
