// The language system (static/js/i18n.js): the key is the Spanish text itself, English comes from static/i18n/en.json,
// numbers and dates follow es-MX, and switching language never reloads the page.
// Run: node --test tests/js/i18n.test.mjs
import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

// a tiny stand-in for the browser bits i18n.js touches
const html = { lang: 'en', attrs: {}, setAttribute(k, v) { this.attrs[k] = v; if (k === 'lang') this.lang = v; } };
const saved = new Map();
let reloads = 0;
globalThis.document = { documentElement: html };
globalThis.localStorage = { getItem: (k) => (saved.has(k) ? saved.get(k) : null), setItem: (k, v) => saved.set(k, String(v)), removeItem: (k) => saved.delete(k) };
globalThis.location = { reload() { reloads++; } };

const EN = JSON.parse(readFileSync(new URL('../../static/i18n/en.json', import.meta.url), 'utf8'));
const loader = async (code) => { if (code !== 'en') throw new Error('no such language'); return EN; };

const i18n = await import('../../static/js/i18n.js');
const { t, th, tp, setLang, getLang, initLang, onLang, LANGS, chips, number, date, time, dateTime, ago, until, tError } = i18n;

beforeEach(async () => { await setLang('es-MX', { loader }); });

test('Spanish is the default and the key is the Spanish text itself', () => {
  assert.equal(getLang(), 'es-MX');
  assert.equal(t('Mercados'), 'Mercados');
  assert.equal(t('Una frase que nadie tradujo'), 'Una frase que nadie tradujo');
});

test('the two languages on offer, Spanish first', () => {
  assert.deepEqual(Object.keys(LANGS), ['es-MX', 'en']);
});

test('placeholders are filled in, in either language', async () => {
  assert.equal(t('Hola, {nombre}', { nombre: 'Ana' }), 'Hola, Ana');
  await setLang('en', { loader });
  assert.equal(t('Hola, {nombre}', { nombre: 'Ana' }), 'Hi, Ana');
  assert.equal(t('{a} y {a}', { a: 'x' }), '{a} y {a}'.replace(/\{a\}/g, 'x'));
});

test('a placeholder nobody filled stays visible instead of turning into "undefined"', () => {
  assert.equal(t('Hola, {nombre}'), 'Hola, {nombre}');
});

test('th() escapes what goes into the placeholders but not the sentence', () => {
  assert.equal(th('Hola, {nombre}', { nombre: '<img src=x onerror=alert(1)>' }), 'Hola, &lt;img src=x onerror=alert(1)&gt;');
});

test('English comes from en.json, and a sentence missing from it stays in Spanish', async () => {
  await setLang('en', { loader });
  assert.equal(getLang(), 'en');
  assert.equal(t('Mercados'), 'Markets');
  assert.equal(t('Una frase que nadie tradujo'), 'Una frase que nadie tradujo');
});

test('plurals follow the rules of the language on screen', async () => {
  assert.equal(tp(1, '{n} ficha', '{n} fichas'), '1 ficha');
  assert.equal(tp(3, '{n} ficha', '{n} fichas'), '3 fichas');
  assert.equal(tp(1000000, '{n} ficha', '{n} fichas'), '1,000,000 fichas');        // es: "many" counts as the plural form
  assert.equal(tp(0, '{n} ficha', '{n} fichas'), '0 fichas');
  await setLang('en', { loader });
  assert.equal(tp(1, '{n} ficha', '{n} fichas'), '1 chip');
  assert.equal(tp(2, '{n} ficha', '{n} fichas'), '2 chips');
});

test('<html lang> follows the language, and the choice is remembered', async () => {
  await setLang('en', { loader });
  assert.equal(html.lang, 'en');
  assert.equal(saved.get('clique-lang'), 'en');
  await setLang('es-MX', { loader });
  assert.equal(html.lang, 'es-MX');
  assert.equal(saved.get('clique-lang'), 'es-MX');
});

test('switching to English and back never reloads the page, and tells whoever listens', async () => {
  const heard = [];
  const off = onLang((code) => heard.push(code));
  reloads = 0;
  await setLang('en', { loader });
  await setLang('es-MX', { loader });
  off();
  await setLang('en', { loader });
  assert.equal(reloads, 0);
  assert.deepEqual(heard, ['en', 'es-MX']);
});

test('an unknown language falls back to Spanish', async () => {
  await setLang('fr', { loader });
  assert.equal(getLang(), 'es-MX');
});

test('a dictionary that cannot be loaded leaves the app in Spanish instead of breaking it', async () => {
  await setLang('en', { loader: async () => { throw new Error('offline'); } });
  assert.equal(getLang(), 'es-MX');
  assert.equal(t('Mercados'), 'Mercados');
});

test('initLang picks up the remembered language', async () => {
  saved.set('clique-lang', 'en');
  await initLang({ loader });
  assert.equal(getLang(), 'en');
  saved.delete('clique-lang');
  await initLang({ loader });
  assert.equal(getLang(), 'es-MX');
});

test('chips are written the es-MX way: comma thousands, point decimals, big numbers shortened', () => {
  assert.equal(chips(1234.5), '$1,234.50');
  assert.equal(chips(1000, { noCents: true }), '$1,000');
  assert.equal(chips(25, { plus: true }), '+$25.00');
  assert.equal(chips(-25), '-$25.00');
  assert.equal(chips(2500000), '$2.5 M');
  assert.equal(chips(0), '$0.00');
  assert.equal(number(1234567.891), '1,234,567.89');
});

test('big chip amounts read "M" in Spanish and "M" in English, "mil M" vs "B" for billions', async () => {
  assert.equal(chips(3.2e9), '$3.2 mil M');
  await setLang('en', { loader });
  assert.equal(chips(3.2e9), '$3.2B');
  assert.equal(chips(2500000), '$2.5M');
});

test('dates and times in es-MX', () => {
  const t0 = Date.UTC(2026, 9, 10, 18, 5);           // 10 Oct 2026, 12:05 in Mexico City
  assert.match(date(t0, { timeZone: 'America/Mexico_City' }), /^10 oct(\.)? 2026$/);
  assert.match(time(t0, { timeZone: 'America/Mexico_City' }), /^12:05/);
  assert.match(dateTime(t0, { timeZone: 'America/Mexico_City' }), /10 oct/);
});

test('how long ago and how long until, in words that fit', async () => {
  const now = Date.now();
  assert.equal(ago(now - 5000), 'justo ahora');
  assert.equal(ago(now - 5 * 60000), 'hace 5 min');
  assert.equal(ago(now - 3 * 3600000), 'hace 3 h');
  assert.equal(ago(now - 2 * 86400000), 'hace 2 d');
  assert.equal(until(now - 1000), 'terminó');
  assert.equal(until(now + (2 * 86400 + 3 * 3600 + 60) * 1000), '2 d 3 h');
  assert.equal(until(now + 90 * 60000 + 1000), '1 h 30 min');
  await setLang('en', { loader });
  assert.equal(ago(now - 5 * 60000), '5m ago');
  assert.equal(until(now - 1000), 'ended');
});

test('a server error is shown by its code when there is a sentence for it, else the server text', () => {
  assert.equal(tError({ code: 'NOT_FOUND', message: 'Not found' }), 'No encontramos lo que buscabas.');
  assert.equal(tError({ code: 'SOMETHING_NEW', message: 'Raw text' }), 'Raw text');
  assert.equal(tError({ message: 'Raw text' }), 'Raw text');
  assert.equal(tError(null), 'Algo salió mal. Inténtalo otra vez.');
});

test('every placeholder in an English sentence is also in its Spanish key', () => {
  const bad = [];
  for (const [es, en] of Object.entries(EN)) {
    if (es.startsWith('_')) continue;
    const want = (es.match(/\{\w+\}/g) || []).sort().join();
    const got = (String(en).match(/\{\w+\}/g) || []).sort().join();
    if (want !== got) bad.push(`${es} → ${en}`);
  }
  assert.deepEqual(bad, []);
});
