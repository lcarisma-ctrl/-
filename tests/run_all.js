#!/usr/bin/env node
/*
 * `npm test` — jsdom 단위 검증을 두 조각으로 나눠 돌린다.
 *
 * app.test.js는 JSDOM 인스턴스를 수십 개 띄우기 때문에 한 프로세스에서 part 1·2를
 * 이어 돌리면 힙이 부족해 Aborted로 끝난다(게이트도 같은 이유로 APP_PART를 나눠 부른다).
 * 그래서 part 1 → part 2를 각각 별도 프로세스(힙 2600MB)로 돌리고, 하나라도 실패하면 1로 끝난다.
 *
 * 실행: cd projects/ttokttok-app/tests && npm test
 */
const { spawnSync } = require('child_process');
const path = require('path');

const parts = ['1', '2'];
const node = process.execPath;
let bad = 0;

for (const part of parts) {
  console.log('\n=== app.test.js APP_PART=' + part + ' ===');
  const r = spawnSync(node, ['--max-old-space-size=2600', path.join(__dirname, 'app.test.js')], {
    cwd: __dirname,
    env: Object.assign({}, process.env, { APP_PART: part }),
    stdio: 'inherit'
  });
  if (r.status !== 0) bad = 1;
}

process.exit(bad);
