/* Small helpers the poker screens share. Amounts arrive as whole units: chips for fake money, cents for real. */
import { esc } from '../util.js';
import { t, intlLocale, CHIP_SIGN } from '../i18n.js';

/** 1500 chips -> "1,500"; 10050 cents of the player's balance -> "$100.50". */
export const amt = (n, scale) => (scale === 100
  ? CHIP_SIGN + (n / 100).toLocaleString(intlLocale(), { minimumFractionDigits: n % 100 ? 2 : 0, maximumFractionDigits: 2 })
  : Math.round(n).toLocaleString(intlLocale()));

/** The number as typed into a form field (dollars for real money, chips for fake). */
export const field = (n, scale) => (scale === 100 ? String(n / 100) : String(n));

export const blindsText = (sb, bb, scale) => `${amt(sb, scale)} / ${amt(bb, scale)}`;

export const moneyTag = (money) => (money === 'real'
  ? `<span class="tag bad pk-real">${t('Fichas de tu saldo')}</span>`
  : `<span class="tag good">${t('Fichas de práctica')}</span>`);

export const initials = (name) => esc((name || '?').slice(0, 1).toUpperCase());
