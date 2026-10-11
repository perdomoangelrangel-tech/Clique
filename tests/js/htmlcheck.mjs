// Finds text people write (names, messages, market titles, punishments...) that reaches HTML without being escaped.
// Used by tests/js/html_seguro.test.mjs; run it by hand to see every finding: node tests/js/htmlcheck.mjs [file.js]
//
// How it decides: every template literal that holds HTML is a place where text becomes markup. Each ${...} inside it is looked at:
//   * text that went through esc(), th() or a helper that escapes on its own (avatar, circleMark, thumb...) is safe;
//   * a nested template is checked on its own;
//   * whatever is left over is unsafe when it names a field people write (name, question, text, title, punishment, bio...).
// The same goes for `innerHTML = ` and insertAdjacentHTML with something built by joining strings.
// A line can be marked `html: seguro (why)` once a person has checked it: the reason is required.
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { lex } from './jslex.mjs';

export const ROOT = fileURLToPath(new URL('../../', import.meta.url));
export const JS = join(ROOT, 'static', 'js');

// helpers whose output is already safe HTML whatever text goes in (each one escapes what it is given)
export const ESCAPERS = ['esc', 'escape', 'th', 'avatar', 'plainAvatar', 'presenceAvatar', 'circleMark', 'thumb', 'titleHtml', 'detailText', 'attr', 'encodeURIComponent', 'errorBlock', 'initials', 'setText'];
// functions that take text but never put it on the page (comparisons, lookups, numbers)
const NOT_TEXT = ['includes', 'indexOf', 'has', 'test', 'startsWith', 'endsWith', 'find', 'filter', 'some', 'every', 'findIndex', 'Number',
  'Boolean', 'money', 'moneyFull', 'num', 'pct', 'cents', 'vol', 'ago', 'until', 'dateShort', 'dateLong', 'icon', 'sticker', 'localeCompare', 'get', 'lookOf', 'hash', 'glyph', 'gameSticker', 'fmtX'];
// fields (or variables) that hold text a person typed
export const PEOPLE_TEXT = /^(username|user|users|name|names|question|title|text|body|message|messages|msg|bio|desc|description|rules|punishment|punish|label|emoji|by|who|author|circle|circleName|note|notes|reason|comment|caption|tagline|nick|email|address|outcome|winner|loser|owner|host|creator|proposer|search|query|player|players|members|member|friend|other|sender|clarification|resolution)$/i;

const strip = (src) => {
  // drop string literals and nested templates (checked on their own), then the arguments of the escaping helpers
  let out = '', i = 0;
  while (i < src.length) {
    const c = src[i];
    if (c === '"' || c === "'") { const q = c; i++; while (i < src.length && src[i] !== q) i += src[i] === '\\' ? 2 : 1; i++; out += '""'; continue; }
    if (c === '`') {
      let depth = 0; i++;
      while (i < src.length && !(src[i] === '`' && depth === 0)) {
        if (src[i] === '\\') { i += 2; continue; }
        if (src[i] === '$' && src[i + 1] === '{') { depth++; i += 2; continue; }
        if (src[i] === '}' && depth) depth--;
        i++;
      }
      i++; out += '``'; continue;
    }
    out += c; i++;
  }
  for (const f of [...ESCAPERS, ...NOT_TEXT]) {
    const rx = new RegExp(`(?<![\\w.$])${f}\\(`, 'g');
    let m;
    while ((m = rx.exec(out))) {
      let j = m.index + m[0].length, depth = 1;
      while (j < out.length && depth) { if (out[j] === '(') depth++; else if (out[j] === ')') depth--; j++; }
      out = out.slice(0, m.index) + 'SAFE' + out.slice(j);
      rx.lastIndex = m.index + 4;
    }
  }
  return out;
};

/** The names in an expression that point at text a person wrote (after the escaped parts are taken out). */
export function risky(exprSrc) {
  let left = strip(exprSrc);
  for (let k = 0; k < 3; k++) left = left.replace(/\[[^\[\]]*\]/g, '');          // a[i] is still a: what matters is what follows
  const hits = [];
  // a.b.c → look at each property name; a bare identifier → look at its name. Calls (x.join(...), x.length) are not text fields.
  const rx = /(?<![\w$.])([A-Za-z_$][\w$]*(?:\??\.[A-Za-z_$][\w$]*)*)(?!\s*\()/g;
  let m;
  while ((m = rx.exec(left))) {
    const before = left.slice(0, m.index).trimEnd(), after = left.slice(m.index + m[1].length).trimStart();
    if (/[{,]$/.test(before) && /^:/.test(after)) continue;                                  // an object key
    if (/^(\?(?!\.)|===|!==|==|!=|>|<|&&)/.test(after) || /(!|===|!==|==|!=|>|<|>=|<=)$/.test(before)) continue;   // a test, not output
    const parts = m[1].split(/\??\./);
    const lastNum = /^(length|size|count|id|ids|n|i|index|amount|balance|price|shares|value|pct|yes|no|mult|total|t|at|ts|time|createdAt|closesAt|endsAt|week|position|rank|level|xp)$/;
    if (lastNum.test(parts[parts.length - 1])) continue;
    if (PEOPLE_TEXT.test(parts[parts.length - 1]) && !['SAFE', 'S', 'ICON', 'Math', 'Number', 'JSON'].includes(parts[0])) hits.push(m[1]);
  }
  return hits;
}

const looksHtml = (chunks) => /<\/?[a-zA-Z][\w-]*[\s>/]/.test(chunks.join('\u0000'));

export function checkSource(src, file = '') {
  const { templates } = lex(src);
  const lines = src.split('\n');
  const found = [];
  for (const t of templates) {
    if (!looksHtml(t.chunks) || t.tag === 'html') continue;          // html`` from ui.js escapes every value itself
    for (const e of t.exprs) {
      // an expression that itself holds a template is that template's job (checked on its own); look only at what is outside it
      const hits = risky(e.src);
      if (!hits.length) continue;
      const line = lines[e.line - 1] || '';
      if (/html: seguro \(.+\)/.test(line)) continue;
      found.push({ file, line: e.line, expr: e.src.trim().slice(0, 90), hits });
    }
  }
  // HTML put together by joining strings and handed to innerHTML / insertAdjacentHTML
  lines.forEach((line, k) => {
    if (!/(innerHTML|outerHTML)\s*\+?=|insertAdjacentHTML\(/.test(line) || /html: seguro \(.+\)/.test(line)) return;
    const rhs = line.split(/innerHTML\s*\+?=|outerHTML\s*\+?=|insertAdjacentHTML\(/)[1] || '';
    if (/['"]\s*\+|\+\s*['"]/.test(rhs)) {
      const hits = risky(rhs.replace(/`[^`]*`/g, '``'));
      if (hits.length) found.push({ file, line: k + 1, expr: rhs.trim().slice(0, 90), hits });
    }
  });
  return found;
}

export function jsFiles(dir = JS) {
  const out = [];
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) out.push(...jsFiles(p));
    else if (n.endsWith('.js')) out.push(p);
  }
  return out.sort();
}

export function checkAll() {
  const all = [];
  for (const p of jsFiles()) all.push(...checkSource(readFileSync(p, 'utf8'), relative(JS, p).split(sep).join('/')));
  return all;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const only = process.argv[2];
  const all = checkAll().filter((f) => !only || f.file === only);
  for (const f of all) console.log(`${f.file}:${f.line}  [${f.hits.join(', ')}]  ${f.expr}`);
  const by = {};
  for (const f of all) by[f.file] = (by[f.file] || 0) + 1;
  console.log('\n' + Object.entries(by).map(([k, v]) => `${k}: ${v}`).join('\n') + `\nTOTAL: ${all.length}`);
}
