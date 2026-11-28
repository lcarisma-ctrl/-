#!/usr/bin/env python3
"""똑똑쌤 빌드: 템플릿의 __LOGODATA__ / __LOGODATA_SMALL__ 자리에 로고 base64를 넣어 index.html 생성.

v39: 첫 화면 성능 — 홈 화면 아이콘(180x180)과 본문 로고는 작은 PNG(180px)를 쓴다.
     512px 원본은 assets/logo-512.png 로 남겨 두고, 필요할 때만 쓴다.
"""
import base64
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
tpl = (ROOT / "src" / "app.template.html").read_text(encoding="utf-8")
logo = base64.b64encode((ROOT / "assets" / "logo-180.png").read_bytes()).decode("ascii")
small = base64.b64encode((ROOT / "assets" / "logo-180.png").read_bytes()).decode("ascii")
out = tpl.replace("__LOGODATA_SMALL__", "data:image/png;base64," + small)
out = out.replace("__LOGODATA__", "data:image/png;base64," + logo)
(ROOT / "index.html").write_text(out, encoding="utf-8")
print("built index.html:", len(out), "chars")
