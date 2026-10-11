// Every script the browser loads parses as an ES module. A broken line in any view only shows up when that screen opens, so it is
// checked here for all of them at once. Run: node --test tests/js/sintaxis.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { relative } from 'node:path';
import { jsFiles, JS } from './htmlcheck.mjs';
import { lex } from './jslex.mjs';

test('every file in static/js parses as a module', () => {
  const bad = [];
  for (const p of jsFiles()) {
    const r = spawnSync(process.execPath, ['--input-type=module', '--check'], { input: readFileSync(p), encoding: 'utf8' });
    if (r.status !== 0) bad.push(`${relative(JS, p)}: ${(r.stderr.split('\n').find((l) => /Error/.test(l)) || r.stderr).trim()} (${r.stderr.split('\n')[0].trim()})`);
  }
  assert.deepEqual(bad, []);
});

/** The source with every string and the text of every template blanked out (the code inside ${...} is kept), so a regex only sees code. */
function codeOnly(src) {
  const out = src.split('');
  const blank = (a, b) => { for (let i = a; i < b; i++) if (out[i] !== '\n') out[i] = ' '; };
  const { templates, strings } = lex(src);
  for (const s of strings) blank(s.start, s.end);
  for (const tp of templates) {
    let from = tp.start;
    for (const e of tp.exprs) { blank(from, e.start); from = e.end; }
    blank(from, tp.end);
  }
  return out.join('').replace(/\/\/[^\n]*/g, (m) => ' '.repeat(m.length)).replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '));
}

test('no file that uses t() from i18n.js also names a local variable t (it would hide the function and break at the first click)', () => {
  const bad = [];
  const DECL = /\b(?:const|let|var)\s+t\b|(?<![\w$.])\(\s*t\s*(?:,|\)\s*=>)|,\s*t\s*\)\s*=>|(?<![\w$.])t\s*=>|\bcatch\s*\(\s*t\s*\)|\bfunction\s*[\w$]*\s*\(\s*t\s*[,)]/g;
  for (const p of jsFiles()) {
    const src = readFileSync(p, 'utf8');
    if (!/import\s*\{[^}]*\bt\b[^}]*\}\s*from\s*['"][./]*i18n\.js['"]/.test(src)) continue;
    const code = codeOnly(src);
    let m;
    while ((m = DECL.exec(code))) bad.push(`${relative(JS, p)}:${code.slice(0, m.index).split('\n').length}: ${m[0].trim()}`);
  }
  assert.deepEqual(bad, [], 'rename the local variable (el, tot, text...): t is the translation function');
});

test('the shadowing check catches the usual shapes', () => {
  const DECL = /\b(?:const|let|var)\s+t\b|(?<![\w$.])\(\s*t\s*(?:,|\)\s*=>)|,\s*t\s*\)\s*=>|(?<![\w$.])t\s*=>|\bcatch\s*\(\s*t\s*\)|\bfunction\s*[\w$]*\s*\(\s*t\s*[,)]/;
  for (const s of ['const t = e.target;', 'list.map((t) => t.id)', 'rows.forEach((t, i) => 1)', 'const f = t => 1', 'function f(t) {}']) assert.ok(DECL.test(codeOnly(s)), s);
  for (const s of ["toast(t('Hola'))", 'const tot = 1;', "el.title = 't'", 'x.t = 1', 'const s = `(t) => ${t("a")}`']) assert.ok(!DECL.test(codeOnly(s)), s);
});

test('the service worker parses as a classic script', () => {
  const r = spawnSync(process.execPath, ['--check', new URL('../../static/sw.js', import.meta.url).pathname.replace(/^\/(\w:)/, '$1')], { encoding: 'utf8' });
  assert.equal(r.status, 0, r.stderr);
});
