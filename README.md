# 똑똑쌤 (ttokttok)

방문재활 플랫폼 '똑똑쌤'의 웹앱입니다. 서버·결제·외부 발송과 연결하지 않고, 데이터는 이 브라우저에만 저장합니다(시연용).

- 라이브: https://lcarisma-ctrl.github.io/-/ (`gh-pages` 브랜치)
- 이 브랜치(`main`): 앱 원본과 검증 스크립트

## 구성

| 경로 | 내용 |
|---|---|
| `src/app.template.html` | 앱 전체(HTML·CSS·JS 한 파일). 로고 자리만 비어 있다 |
| `assets/` | 로고 PNG(180·512) |
| `build.py` | 템플릿의 로고 자리에 base64를 넣어 `index.html` 생성 |
| `index.html` | 빌드 결과 — `gh-pages`에 올라가는 파일과 같다 |
| `tests/` | jsdom 단위 검증·대비(WCAG AA)·E2E·전수 QA |
| `.github/workflows/qa.yml` | 푸시·PR마다 빌드 → jsdom → 대비 자동 검증 |

## 검증

```bash
npm ci --prefix tests                      # jsdom
pip install playwright && playwright install chromium   # 대비 검증용

python3 tests/qa_gate.py                    # build → jsdom → e2e → qa → contrast 전부
python3 tests/qa_gate.py --only build,jsdom,contrast    # CI가 도는 세 단계
```

- `tests/qa_gate.py --only contrast`는 라이트·다크 × 375·768·1024·1280에서 WCAG AA 위반이 있으면 0이 아닌 코드로 끝납니다.
- `tests/e2e_chromium.py`(흐름 2,200여 검증)와 `tests/qa_v24.py`(전수 QA)는 로컬 전용입니다.

## 배포

```bash
python3 build.py
# index.html을 gh-pages 브랜치에 올린다
git subtree push --prefix . origin gh-pages   # 또는 gh-pages 체크아웃 후 index.html만 커밋
```

단가·수수료·정산 규칙(90,000/70,000원 · 수수료 22.2% · D+3·15일/말일)과 시드 예약번호(`TT-261021-7302`)·백업 스키마(`ttokttok.v23`)는 테스트로 고정되어 있습니다.
