const fs = require('fs'), path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');
const HTML = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const vc = new VirtualConsole();
const dom = new JSDOM(HTML, { runScripts: 'dangerously', url: 'https://t.test/', virtualConsole: vc, pretendToBeVisual: true });
const w = dom.window, d = w.document;
(async () => {
  for (let i = 0; i < 400 && !w.__ttokttokBooted; i++) await new Promise((r) => setTimeout(r, 20));
  await new Promise((r) => setTimeout(r, 300));
  const list = d.querySelectorAll('.t-avatar');
  console.log('count', list.length);
  [...list].slice(0, 5).forEach((e) => console.log(JSON.stringify(e.getAttribute('style'))));
  console.log('avaStyle?', typeof w.__ttokttokModel);
  if (w.__ttokttokModel && w.__ttokttokModel.teacherPublicProfile) console.log('ok model');
})();
