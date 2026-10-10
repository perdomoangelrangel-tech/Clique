/* Small helpers the poker screens share. Amounts arrive as whole units: chips for fake money, cents for real. */
import { esc } from '../util.js';

/** 1500 chips -> "1,500"; 10050 cents -> "$100.50". */
export const amt = (n, scale) => (scale === 100
  ? '$' + (n / 100).toLocaleString('en-US', { minimumFractionDigits: n % 100 ? 2 : 0, maximumFractionDigits: 2 })
  : Math.round(n).toLocaleString('en-US'));

/** The number as typed into a form field (dollars for real money, chips for fake). */
export const field = (n, scale) => (scale === 100 ? String(n / 100) : String(n));

export const blindsText = (sb, bb, scale) => `${amt(sb, scale)} / ${amt(bb, scale)}`;

export const moneyTag = (money) => (money === 'real'
  ? '<span class="tag bad pk-real">Real cash</span>'
  : '<span class="tag good">Fake chips</span>');

export const initials = (name) => esc((name || '?').slice(0, 1).toUpperCase());
