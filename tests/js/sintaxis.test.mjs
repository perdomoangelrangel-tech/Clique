// Every script the browser loads parses as an ES module. A broken line in any view only shows up when that screen opens, so it is
// checked here for all of them at once. Run: node --test tests/js/sintaxis.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { relative } from 'node:path';
import { jsFiles, JS } from './htmlcheck.mjs';

test('every file in static/js parses as a module', () => {
  const bad = [];
  for (const p of jsFiles()) {
    const r = spawnSync(process.execPath, ['--input-type=module', '--check'], { input: readFileSync(p), encoding: 'utf8' });
    if (r.status !== 0) bad.push(`${relative(JS, p)}: ${(r.stderr.split('\n').find((l) => /Error/.test(l)) || r.stderr).trim()} (${r.stderr.split('\n')[0].trim()})`);
  }
  assert.deepEqual(bad, []);
});

test('the service worker parses as a classic script', () => {
  const r = spawnSync(process.execPath, ['--check', new URL('../../static/sw.js', import.meta.url).pathname.replace(/^\/(\w:)/, '$1')], { encoding: 'utf8' });
  assert.equal(r.status, 0, r.stderr);
});
