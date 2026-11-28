# CI 워크플로 등록 (한 단계 남음)

`ci/qa.yml`은 푸시·PR마다 **빌드 → jsdom → 대비(WCAG AA)** 를 돌리는 GitHub Actions 워크플로입니다.
지금은 저장소의 GitHub App 권한에 `workflows`가 없어 **`.github/workflows/qa.yml` 경로로 푸시할 수 없습니다**
(`refusing to allow a GitHub App to create or update workflow ... without workflows permission`).

켜는 방법 두 가지 — 둘 중 하나만 하면 됩니다.

1. **GitHub 웹에서 파일 추가** (권한 필요 없음)
   - https://github.com/lcarisma-ctrl/- → `Add file` → `Create new file`
   - 파일 이름: `.github/workflows/qa.yml`
   - 내용: 이 폴더의 `qa.yml` 전체를 붙여넣고 커밋
   - 커밋하면 바로 첫 실행이 돌고, 이후 푸시·PR마다 자동으로 돕니다.

2. **Pickle GitHub 연결에 Workflows 권한 추가**
   - GitHub → Settings → Applications → Pickle → Permissions 에서 `Workflows: Read and write`를 켜고,
     그 뒤 `git push`로 `.github/workflows/qa.yml`을 올리면 됩니다.

워크플로가 도는 세 단계는 로컬과 같은 명령입니다.

```bash
python3 tests/qa_gate.py --only build      # 템플릿 → index.html + app-version 일치
python3 tests/qa_gate.py --only jsdom      # app.test.js(part 1·2) + v32~v47
python3 tests/qa_gate.py --only contrast   # 라이트·다크 × 375·768·1024·1280
```
