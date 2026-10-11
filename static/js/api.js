import { registerLooks } from './looks.js';
import { t, tError } from './i18n.js';
let onUnauthorized = () => {};
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn; };
let demoProbe = () => false;
export const setDemoProbe = (fn) => { demoProbe = fn; };      // state.js says whether demo mode is on
let acctProbe = () => null;
export const setAcctProbe = (fn) => { acctProbe = fn; };      // state.js says which account the casino is playing with ('accumulated', or nothing for the weekly one)

export async function api(method, path, body) {
  // In demo mode every casino request plays on the practice wallet. The server decides, the browser just asks.
  if (path.startsWith('/api/games/') && demoProbe()) {
    if (method === 'GET') path += (path.includes('?') ? '&' : '?') + 'demo=1';
    else body = { ...(body || {}), demo: true };
  } else if (path.startsWith('/api/games/') && acctProbe() === 'accumulated') {      // a casino request on the accumulated account: the server decides, the browser just asks
    if (method === 'GET') path += (path.includes('?') ? '&' : '?') + 'acct=accumulated';
    else body = { ...(body || {}), acct: 'accumulated' };
  }
  const opts = { method, headers: {}, credentials: 'same-origin' };
  if (body !== undefined) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
  else if (method !== 'GET') { opts.headers['Content-Type'] = 'application/json'; opts.body = '{}'; }
  let res;
  try { res = await fetch(path, opts); }
  catch { const err = new Error(tError({ code: 'NETWORK' })); err.code = 'NETWORK'; throw err; }
  let data = null;
  try { data = await res.json(); } catch { /* not json */ }
  if (data) registerLooks(data);                         // remember how every person in the answer looks
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith('/api/auth/')) onUnauthorized();
    // a refusal is shown by its code when the server sends one (E3's list, equipo/contratos/errores.md), else in the server's own words
    const err = new Error(tError({ code: data && data.code, message: (data && data.error) || t('Algo salió mal ({estado})', { estado: res.status }) }));
    err.status = res.status;
    if (data && data.code) err.code = data.code;
    if (data) err.data = data;                           // anything extra the server sent with the refusal (a fresh quote, for one)
    if (data && data.quote) err.quote = data.quote;
    throw err;
  }
  return data;
}
export const get = (p) => api('GET', p);
export const post = (p, b) => api('POST', p, b ?? {});
export const patch = (p, b) => api('PATCH', p, b ?? {});
export const del = (p) => api('DELETE', p);
