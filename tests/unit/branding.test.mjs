import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
const root = new URL('../../', import.meta.url);
const read = path => readFileSync(new URL(path, root), 'utf8');
const html = read('frontend/index.html');

test('publication preserves institutional branding and project title', () => {
  assert.match(html, /<title>Real-Time Speech Dialogue<\/title>/);
  assert.match(html, /<h1 class="demo-tag">Real-Time Speech Dialogue<\/h1>/);
  assert.match(html, /class="university-seal"/);
  assert.match(html, /class="ifn-logo"/);
  assert.match(html, /alt="TU Braunschweig seal"/);
  assert.match(html, /alt="IfN · Institut für Nachrichtentechnik"/);
  for (const match of html.matchAll(/src="(\/branding\/[^"?]+)(?:\?[^\"]*)?"/g)) {
    assert.ok(existsSync(new URL('frontend' + match[1], root)), match[1]);
  }
});

test('logos keep proportions, IfN white backing and separate rights', () => {
  const css = read('frontend/style.css');
  assert.match(css, /\.brand img \{[^}]*width: auto;[^}]*object-fit: contain;/);
  assert.match(css, /\.logo-backing \{[^}]*background: #fff/);
  assert.ok(existsSync(new URL('assets/branding/logo_IFN.original.svg', root)));
  assert.match(read('assets/branding/README.md'), /no unrestricted public redistribution/);
});

test('publication cache marker is consistent across entry assets', () => {
  const app = read('frontend/app.js');
  assert.match(app, /const FRONTEND_BUILD = 'publication-v2';/);
  assert.match(html, /style\.css\?v=publication-v2/);
  assert.match(html, /app\.js\?v=publication-v2/);
  assert.ok([...app.matchAll(/\?v=([A-Za-z0-9._-]+)/g)].every(m => m[1] === 'publication-v2'));
});
