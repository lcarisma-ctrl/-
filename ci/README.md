# CI — 푸시마다 빌드 → jsdom → 대비를 자동으로 (등록 완료 · 2026-11-28 기준)

`ci/qa.yml`은 푸시·PR마다 **빌드 → jsdom → 대비(WCAG AA)** 를 돌리는 GitHub Actions 워크플로입니다.
v47에서 이 파일을 `.github/workflows/qa.yml`로 **저장소에 등록했고, 지금 정상 동작 중**입니다.
(등록은 GitHub 웹에서 파일을 추가하는 방식으로 했습니다 — 아래 '등록 상태' 참조.)

## 지금 상태

| 항목 | 값 |
|---|---|
| 경로 | `.github/workflows/qa.yml` (이 폴더의 `qa.yml`과 **같은 내용**, sha `202bdac8`) |
| 상태 | `active` · 워크플로 id `433349940` |
| 도는 때 | `main` 푸시 · PR · 수동 실행(`workflow_dispatch`) |
| 최근 실행 | [#46141335266](https://github.com/lcarisma-ctrl/-/actions/runs/46141335266) — v51 `e860c27`(2026-11-28 20:45 KST) · success 11분 39초 |
| 단계 | 체크아웃 → Node 20 → Python 3.12 → jsdom 의존성 → Chromium → **빌드** → **jsdom** → **대비** → 결과 요약 |
| 실패할 때 | 빨간 X로 멈춥니다. 대비가 0건이 아니면 다음 빌드에서 바로 드러납니다 |

실행 기록: `gh run list -R lcarisma-ctrl/-` 또는 저장소 → Actions 탭.

## 워크플로가 도는 세 단계 (로컬과 같은 명령)

```bash
python3 tests/qa_gate.py --only build      # 템플릿 → index.html + app-version 일치
python3 tests/qa_gate.py --only jsdom      # app.test.js(part 1·2) + v32~v51
python3 tests/qa_gate.py --only contrast   # 라이트·다크 × 375·768·1024·1280
```

- `e2e_chromium.py`(2,499검증)·`qa_v24.py`(793검증)는 Actions 시간이 커서 **로컬 전용**입니다.
- 로컬에서 전부 돌리려면 `python3 tests/qa_gate.py`(e2e·qa·print·format 포함, 20분 안팎).
- v51에서 **`print`**(인쇄 줄 맞춤 + 실제 PDF 백지 감사)와 **`format`**(날짜·시간·금액·전화 표기 전수 스캔) 단계가 늘었습니다.
  CI는 시간 때문에 build·jsdom·contrast만 돕니다(워크플로 파일은 수정하지 않음). 배포 전에는 이것도 한 번 돌립니다.

```bash
python3 tests/qa_gate.py --only print      # print_align_v50 + print_pdf_v51
python3 tests/qa_gate.py --only format     # format_scan_v51 --gate
```

## 이 파일을 고칠 때

워크플로는 **권한 때문에 `git push`로 올리지 못합니다** — 저장소의 GitHub App 권한에 `workflows`가 없습니다
(`refusing to allow a GitHub App to create or update workflow ... without workflows permission`).
그래서 고칠 때는:

1. 이 폴더의 `qa.yml`을 고친다(내용은 그대로 GitHub에 올라갈 파일).
2. GitHub 웹에서 `.github/workflows/qa.yml`을 열어 **같은 내용으로 커밋**한다
   (`https://github.com/lcarisma-ctrl/-/edit/main/.github/workflows/qa.yml`).
3. 또는 GitHub → Settings → Applications → Pickle → Permissions 에서 `Workflows: Read and write`를 켜면
   다음부터는 `git push`로 함께 올릴 수 있다.

## v49에서 달라진 것

- jsdom 단계에 **`app.v49.test.js`(66검증)** 가 들어갔습니다 — 카드 열기/찜 버튼 분리(중첩 인터랙티브 0), 정지점 2개, `.btn-sm` 경계, 인쇄 쪽나눔·머리/꼬리, 긴 글 마감.
- E2E 묶음 마지막이 `v46,v47,v48,v49`가 됐습니다(로컬 전용, Actions에서는 돌지 않음).
- 대비 단계는 그대로 라이트·다크 × 375·768·1024·1280이며, v49에서 **본문 0건 · UI 경계 0건**입니다.
