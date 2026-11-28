#!/usr/bin/env python3
"""v11 라이브 검증: HTTP 200 + 로컬 index.html 과 md5 일치 + app-version 확인.

실행: python3 tests/_live_check_v11.py        (한 번)
     python3 tests/_live_check_v11.py --wait 900   (최대 15분, 30초 간격 재시도)

GitHub Pages 장애로 배포 반영이 늦어질 때 이 스크립트로 재확인하면 된다.
"""
import hashlib
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL = os.path.join(ROOT, "index.html")
URL = "https://lcarisma-ctrl.github.io/-/?v=11"


def local_md5():
    with open(LOCAL, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def fetch(url):
    req = urllib.request.Request(url, headers={"Cache-Control": "no-cache", "Pragma": "no-cache"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read()


def check():
    want = local_md5()
    try:
        code, body = fetch(URL)
    except Exception as e:
        print("FETCH FAILED:", type(e).__name__, e)
        return False
    got = hashlib.md5(body).hexdigest()
    version = ""
    for line in body.decode("utf-8", "replace").splitlines()[:40]:
        if 'name="app-version"' in line:
            version = line.strip()
            break
    print("HTTP", code)
    print("local md5", want)
    print("live  md5", got)
    print("version   ", version)
    ok = code == 200 and got == want
    print("RESULT:", "MATCH" if ok else "MISMATCH (아직 이전 파일이 서빙 중)")
    return ok


def main():
    wait = 0
    if "--wait" in sys.argv:
        wait = int(sys.argv[sys.argv.index("--wait") + 1])
    deadline = time.time() + wait
    while True:
        if check():
            return 0
        if time.time() >= deadline:
            return 1
        print("... 30초 후 재시도\n")
        time.sleep(30)


if __name__ == "__main__":
    sys.exit(main())
