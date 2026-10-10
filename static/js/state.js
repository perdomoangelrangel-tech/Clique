import { get, setDemoProbe, setAcctProbe } from './api.js';

export const S = { user: null, demo: false, demoUser: null, acct: 'weekly', categories: [], minBet: 0.1, myCircles: [], discover: [], search: '', week: '' };
export const bus = new EventTarget();

export const go = (hash) => { location.hash = hash; };

setDemoProbe(() => S.demo);
setAcctProbe(() => (S.acct === 'accumulated' ? 'accumulated' : null));
/** The wallet the casino is playing with right now: the practice one in demo mode, the accumulated account when that is chosen, or the weekly account.
    (For the accumulated account this is a reading copy with that account's money as the balance: to change money use deduct() / setUser().) */
export const wallet = () => {
  if (S.demo) return S.demoUser || { balance: 0, netWorth: 0, demo: true };
  if (S.acct === 'accumulated' && S.user) return { ...S.user, balance: S.user.accum || 0, netWorth: S.user.accum || 0 };
  return S.user;
};
export const balanceNow = () => wallet().balance;

export function setUser(u) {
  if (u && u.demo) {                       // a practice-wallet update: never touches the real user
    const before = S.demoUser;
    S.demoUser = u;
    bus.dispatchEvent(new CustomEvent('user', { detail: { prev: before, user: u, demo: true } }));
    return;
  }
  const prev = S.user;
  S.user = u;
  bus.dispatchEvent(new CustomEvent('user', { detail: { prev, user: u } }));
}

export async function refreshMe() {
  const d = await get('/api/me');
  S.categories = d.categories;
  S.minBet = d.minBet;
  S.week = d.week;
  setUser(d.user);
  return d.user;
}

export async function loadCircles() {
  const d = await get('/api/circles');
  S.myCircles = d.mine;
  S.discover = d.discover;
  return d;
}
