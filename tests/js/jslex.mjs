// A small JavaScript lexer for the checks in this folder: finds every template literal (with the source of each ${...} inside it) and
// every quoted string, skipping comments and regular expressions. Not a parser: just enough to know what is text and what is code.

const REGEX_AFTER = new Set(['', '(', ',', '=', ':', '[', '!', '&', '|', '?', '{', '}', ';', '+', '-', '*', '%', '<', '>', '~', '^',
  'return', 'typeof', 'case', 'do', 'else', 'in', 'of', 'new', 'delete', 'void', 'throw', 'yield', 'await']);
const isIdStart = (c) => /[A-Za-z_$]/.test(c);
const isId = (c) => /[A-Za-z0-9_$]/.test(c);

export function lex(src) {
  const templates = [], strings = [];
  let i = 0, prev = '';
  const n = src.length;
  const lineAt = (k) => { let l = 1; for (let j = 0; j < k; j++) if (src.charCodeAt(j) === 10) l++; return l; };

  function str(q) {
    const start = i; i++;
    let out = '';
    while (i < n && src[i] !== q) { if (src[i] === '\\') { out += src[i + 1]; i += 2; continue; } out += src[i++]; }
    i++;
    strings.push({ text: out, start, end: i });
    prev = 'str';
  }
  function tpl() {
    const tag = /^[A-Za-z_$][\w$]*$/.test(prev) && !/\s/.test(src[i - 1] || '') ? prev : null;     // html`...` is a tagged template
    const start = i; i++;
    const chunks = [], exprs = [];
    let cur = '';
    while (i < n && src[i] !== '`') {
      if (src[i] === '\\') { cur += src.slice(i, i + 2); i += 2; continue; }
      if (src[i] === '$' && src[i + 1] === '{') {
        chunks.push(cur); cur = '';
        i += 2;
        const from = i;
        code(true);
        exprs.push({ src: src.slice(from, i - 1), start: from, end: i - 1 });
        continue;
      }
      cur += src[i++];
    }
    chunks.push(cur);
    i++;
    templates.push({ chunks, exprs, start, end: i, tag });
    prev = 'str';
  }
  function regex() {
    i++;
    let klass = false;
    while (i < n) {
      const c = src[i];
      if (c === '\\') { i += 2; continue; }
      if (c === '[') klass = true; else if (c === ']') klass = false;
      else if ((c === '/' && !klass) || c === '\n') break;
      i++;
    }
    i++;
    while (i < n && /[a-z]/i.test(src[i])) i++;
    prev = 're';
  }
  function code(stopBrace) {
    let depth = 0;
    while (i < n) {
      const c = src[i];
      if (c === ' ' || c === '\t' || c === '\r' || c === '\n') { i++; continue; }
      if (c === '/' && src[i + 1] === '/') { const j = src.indexOf('\n', i); i = j < 0 ? n : j; continue; }
      if (c === '/' && src[i + 1] === '*') { const j = src.indexOf('*/', i + 2); i = j < 0 ? n : j + 2; continue; }
      if (c === '"' || c === "'") { str(c); continue; }
      if (c === '`') { tpl(); continue; }
      if (c === '/' && REGEX_AFTER.has(prev)) { regex(); continue; }
      if (isIdStart(c)) { let j = i; while (j < n && isId(src[j])) j++; prev = src.slice(i, j); i = j; continue; }
      if (/[0-9]/.test(c)) { let j = i; while (j < n && /[A-Za-z0-9._]/.test(src[j])) j++; prev = 'num'; i = j; continue; }
      if (c === '{') depth++;
      if (c === '}') { if (stopBrace && depth === 0) { i++; prev = '}'; return; } depth--; }
      prev = c; i++;
    }
  }
  code(false);
  for (const t of templates) { t.line = lineAt(t.start); for (const e of t.exprs) e.line = lineAt(e.start); }
  for (const s of strings) s.line = lineAt(s.start);
  return { templates, strings };
}
