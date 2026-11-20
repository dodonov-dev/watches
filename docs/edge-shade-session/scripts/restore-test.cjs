const { chromium } = require(process.cwd() + '/node_modules/playwright');
(async () => {
  const b = await chromium.launch(); const pg = await b.newPage();
  const warns = []; pg.on('console', (m) => { if (m.type() === 'warning') warns.push(m.text()); });
  await pg.goto('http://localhost:5191/?fresh=1', { waitUntil: 'networkidle' });
  // a session saved by the v29 sim: untagged material state in material mode, its design with the smoothstep keys
  const material = { material: JSON.parse(require('fs').readFileSync('../presets/materials/alpine.json', 'utf8')).material };
  await pg.evaluate((m) => {
    const s = JSON.parse(localStorage.getItem('liquid-watch-session-v1') || '{}');
    const mat = { ...(m || {}), mode: 'material', design: { tubeHeight: 40, edgeShade: 0.52, edgeShadeFrom: 1.15, edgeShadeTo: 2.85 } };
    delete mat.version;
    s.material = mat; s.params = { ...(s.params || {}), v: 29, edgeShade: 0.52, edgeShadeFrom: 1.15, edgeShadeTo: 2.85 };
    localStorage.setItem('liquid-watch-session-v1', JSON.stringify(s));
  }, material);
  await pg.goto('http://localhost:5191/', { waitUntil: 'networkidle' });
  await pg.waitForTimeout(800);
  await pg.evaluate(() => window.dispatchEvent(new Event('pagehide')));
  await pg.waitForTimeout(300);
  const after = await pg.evaluate(() => JSON.parse(localStorage.getItem('liquid-watch-session-v1') || '{}'));
  console.log('mode', after.material && after.material.mode, 'version', after.material && after.material.version, 'design', JSON.stringify(after.material && after.material.design));
  console.log('params edgeShade', after.params && after.params.edgeShade, 'pow', after.params && after.params.edgeShadePow, 'from' in (after.params || {}) ? 'FROM KEPT' : 'from dropped');
  console.log('warnings', warns.filter((w) => /material/.test(w)));
  await b.close();
})();
