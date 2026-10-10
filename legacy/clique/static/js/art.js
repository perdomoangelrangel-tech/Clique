/* Clique's own sticker art. Flat colours, thick ink outlines, halftone shading. No emoji, no gradients.
   Every glyph is drawn in a 64x64 box and wrapped in a colour-block tile by sticker(). */

const INK = '#0E0C0A', CREAM = '#EFE6D2', LIME = '#C6F432', VERM = '#FF4B2B', FELT = '#1E3B2C', FELT2 = '#2F6B47', BONE = '#CFC3A8';
export const TILE_BG = { lime: LIME, verm: VERM, cream: CREAM, felt: FELT, bone: BONE, ink: '#2A2420' };

// ---- suits (20x20 box), also used on the playing cards ----
const SUIT_PATH = {
  S: 'M10 1c4 5 8 7 8 11a4 4 0 0 1-7 2.4c.2 1.8.8 3.4 2 4.6H7c1.2-1.2 1.8-2.8 2-4.6A4 4 0 0 1 2 12c0-4 4-6 8-11z',
  H: 'M10 18.5 2.4 10.4C-.6 6.600 1.400 1.500 5.600 1.500c2 0 3.600 1.200 4.400 3 .8-1.800 2.400-3 4.400-3 4.200 0 6.200 5.100 3.200 8.900z',
  D: 'M10 1l7 9-7 9-7-9z',
  C: 'M10 1.500a3.800 3.800 0 0 0-3.200 5.800A4 4 0 1 0 9 13.600c-.1 1.700-.7 3.200-1.900 4.400h5.800c-1.200-1.200-1.800-2.700-1.900-4.400a4 4 0 1 0 2.200-6.300A3.800 3.800 0 0 0 10 1.500z',
};
export const suitSvg = (s, size = 18) => `<svg class="suit" width="${size}" height="${size}" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path d="${SUIT_PATH[s]}"/></svg>`;

// ---- glyphs: each returns the inner SVG for a 64x64 box ----
const g = (inner) => `<g fill="none" stroke="${INK}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round">${inner}</g>`;
const dot = (x, y, r = 3, f = INK) => `<circle cx="${x}" cy="${y}" r="${r}" fill="${f}" stroke="none"/>`;
const T = (x, y, size, txt, fam = 'var(--f-display)', f = INK) => `<text x="${x}" y="${y}" text-anchor="middle" font-size="${size}" font-weight="800" font-family="${fam}" fill="${f}" stroke="none">${txt}</text>`;

const GLYPH = {
  die: () => g(`<g transform="rotate(-10 32 32)"><rect x="14" y="14" width="36" height="36" rx="5" fill="${CREAM}"/>${dot(23.5, 23.5)}${dot(40.5, 23.5)}${dot(32, 32)}${dot(23.5, 40.5)}${dot(40.5, 40.5)}</g>`),
  trophy: () => g(`<path d="M20 12h24v14c0 9-5 14-12 14s-12-5-12-14z" fill="${LIME}"/><path d="M20 16h-6c0 8 3 12 8 13M44 16h6c0 8-3 12-8 13"/><path d="M32 40v8"/><rect x="22" y="48" width="20" height="7" rx="1.500" fill="${CREAM}"/>`),
  controller: () => g(`<path d="M10 28c0-5 4-9 9-9h26c5 0 9 4 9 9l3 14c1 5-2 8-6 8-3 0-5-2-7-5H20c-2 3-4 5-7 5-4 0-7-3-6-8z" fill="${CREAM}"/><path d="M23 27v10M18 32h10"/><circle cx="42" cy="30" r="3.200" fill="${VERM}"/><circle cx="48" cy="35" r="3.200" fill="${LIME}"/>`),
  sprout: () => g(`<path d="M32 56V30"/><path d="M32 34C32 21 24 14 11 14c0 13 8 20 21 20z" fill="${LIME}"/><path d="M32 42c0-9 7-15 20-15 0 11-8 17-20 17z" fill="${FELT2}"/>`),
  coin: () => g(`<circle cx="32" cy="32" r="20" fill="${LIME}"/><circle cx="32" cy="32" r="13" fill="none"/>`) + T(32, 39, 20, '$'),
  bolt: () => g(`<path d="M38 7 15 37h14l-4 20 24-31H34z" fill="${VERM}"/>`),
  note: () => g(`<ellipse cx="23" cy="46" rx="9" ry="7" fill="${LIME}" transform="rotate(-20 23 46)"/><path d="M31 44V13"/><path d="M31 13l19 7v11l-19-7z" fill="${VERM}"/>`),
  star: () => g(`<polygon points="32,6 39,22 56,20 45,33 56,46 39,44 32,59 25,44 8,46 19,33 8,20 25,22" fill="${LIME}"/>`),
  crown: () => g(`<path d="M12 46 9 21l15 11 8-19 8 19 15-11-3 25z" fill="${LIME}"/><rect x="12" y="46" width="40" height="8" rx="1.500" fill="${CREAM}"/>`) + dot(9, 21, 3.500, VERM) + dot(32, 12, 3.500, VERM) + dot(55, 21, 3.500, VERM),
  flame: () => g(`<path d="M32 6c3 11 17 16 17 32a17 17 0 0 1-34 0c0-9 4-13 9-17 0 6 2 9 6 10-1-9-1-17 2-25z" fill="${VERM}"/><path d="M32 33c3 6 8 8 8 14a8 8 0 0 1-16 0c0-5 4-7 8-14z" fill="${LIME}"/>`),
  rocket: () => `<g transform="rotate(40 32 32)">${g(`<path d="M32 4c10 7 12 22 8 38H24C20 26 22 11 32 4z" fill="${CREAM}"/><path d="M32 4c3 2 6 6 8 11H24c2-5 5-9 8-11z" fill="${VERM}"/><circle cx="32" cy="26" r="5" fill="${FELT2}"/><path d="M24 34l-9 11v7l9-5zM40 34l9 11v7l-9-5z" fill="${VERM}"/><path d="M27 44h10l-5 15z" fill="${LIME}"/>`)}</g>`,
  chartdown: () => g(`<path d="M9 15l15 15 9-9 15 15" stroke-width="10"/>`) + `<path d="M9 15l15 15 9-9 15 15" fill="none" stroke="${VERM}" stroke-width="4.500" stroke-linecap="round" stroke-linejoin="round"/>` + g(`<path d="M54 34v17H37z" fill="${VERM}"/>`),
  crystal: () => g(`<circle cx="32" cy="27" r="18" fill="${LIME}"/><path d="M52 52H12c0-7 7-11 20-11s20 4 20 11z" fill="${VERM}"/>`) + `<path d="M23 19a11 11 0 0 1 8-5" fill="none" stroke="${CREAM}" stroke-width="3.500" stroke-linecap="round"/>` + `<path d="M52 8l2 5 5 2-5 2-2 5-2-5-5-2 5-2z" fill="${CREAM}" stroke="${INK}" stroke-width="1.500"/>`,
  target: () => g(`<circle cx="29" cy="35" r="21" fill="${VERM}"/><circle cx="29" cy="35" r="14" fill="${CREAM}"/><circle cx="29" cy="35" r="7" fill="${VERM}"/><path d="M29 35 53 11"/><path d="M47 17l1-9 7 7zM53 11l8-1-3 8z" fill="${CREAM}"/>`),
  whale: () => g(`<path d="M5 38c0-13 10-20 25-20 12 0 21 6 24 16 5-2 8-5 8-11 4 4 3 12-2 16-3 3-7 4-11 4H18C10 43 5 42 5 38z" fill="${CREAM}"/><path d="M10 44c12 5 30 5 42-1"/><path d="M27 17c-3-4-1-9-1-9M34 17c0-5 3-9 3-9" stroke="${LIME}" stroke-width="3.500"/>`) + dot(18, 32, 2.200),
  chips: () => g(`<rect x="10" y="40" width="44" height="11" rx="5.500" fill="${VERM}"/><rect x="10" y="28" width="44" height="11" rx="5.500" fill="${CREAM}"/><rect x="10" y="16" width="44" height="11" rx="5.500" fill="${LIME}"/><path d="M19 45.500h4M30 45.500h4M41 45.500h4M19 33.500h4M30 33.500h4M41 33.500h4M19 21.500h4M30 21.500h4M41 21.500h4" stroke-width="2.500"/>`),
  clover: () => g(`<circle cx="23" cy="23" r="10" fill="${LIME}"/><circle cx="41" cy="23" r="10" fill="${LIME}"/><circle cx="23" cy="41" r="10" fill="${LIME}"/><circle cx="41" cy="41" r="10" fill="${LIME}"/><path d="M34 44c3 7 9 10 15 11"/>`) + dot(32, 32, 6, LIME),
  cardspade: () => g(`<path d="M6 55 20 30l9 25z" fill="${VERM}"/><g transform="rotate(8 32 34)"><rect x="17" y="10" width="32" height="46" rx="4" fill="${CREAM}"/><path d="M33 20c5 5 9 8 9 12a5 5 0 0 1-9 2 5 5 0 0 1-9-2c0-4 4-7 9-12z" fill="${INK}"/><path d="M33 34v8" stroke-width="3.500"/></g>`),
  chicken: () => g(`<path d="M15 34c-6-4-7-10-5-13 5 2 9 5 10 11z" fill="${CREAM}"/><ellipse cx="30" cy="38" rx="18" ry="14" fill="${CREAM}"/><circle cx="43" cy="21" r="10" fill="${CREAM}"/><path d="M37 14c0-6 5-7 6-2 1-5 7-3 5 3z" fill="${VERM}"/><path d="M52 21l9 3-9 4z" fill="${LIME}"/><path d="M21 37c4-4 11-4 15 2-4 5-12 5-15-2z" fill="${BONE}"/><path d="M26 52v6M35 52v6M21 58h8M30 58h8"/>`) + dot(45, 20, 2.200),
  wheel: () => g(`<circle cx="32" cy="32" r="23" fill="${INK}"/><circle cx="32" cy="32" r="16" fill="none" stroke="${VERM}" stroke-width="12" stroke-dasharray="6.28 6.28"/><circle cx="32" cy="32" r="8" fill="${CREAM}"/><circle cx="48" cy="13" r="3.600" fill="${CREAM}"/>`) + dot(32, 32, 3, VERM),
  house: () => g(`<rect x="13" y="30" width="38" height="25" fill="${CREAM}"/><path d="M7 33 32 9l25 24z" fill="${VERM}"/><rect x="27" y="40" width="10" height="15" fill="${INK}"/>`),
  brokenheart: () => g(`<path d="M32 56 8 32C1 24 6 10 19 10c6 0 10 3 13 8 3-5 7-8 13-8 13 0 18 14 11 22z" fill="${VERM}"/><path d="M33 17l-6 11 9 6-7 13" stroke-width="3.500"/>`),
  paper: () => g(`<path d="M16 8h24l10 10v38H16z" fill="${CREAM}"/><path d="M40 8v10h10" fill="${BONE}"/><path d="M22 30h22M22 38h22M22 46h14" stroke-width="2.500"/><path d="M5 20l5 3M59 22l-5 3M4 36h5M55 36h5" stroke-width="2.500"/>`),
  brain: () => g(`<path d="M32 13c-4-5-14-4-16 3-6 1-8 8-4 12-3 5 0 11 6 12 2 6 11 7 14 1z" fill="${CREAM}"/><path d="M32 13c4-5 14-4 16 3 6 1 8 8 4 12 3 5 0 11-6 12-2 6-11 7-14 1z" fill="${CREAM}"/><path d="M22 25c3 0 4 3 7 3M42 25c-3 0-4 3-7 3M24 37c3-1 5 1 8 0" stroke-width="2.500"/>`),
  bubble: () => g(`<path d="M12 12h40a4 4 0 0 1 4 4v22a4 4 0 0 1-4 4H35L24 53V42H12a4 4 0 0 1-4-4V16a4 4 0 0 1 4-4z" fill="${CREAM}"/>`) + dot(21, 27) + dot(32, 27) + dot(43, 27),
  mountain: () => g(`<path d="M3 55 24 20l12 18 8-10 17 27z" fill="${FELT2}"/><path d="M24 20l-6 10 6-3 6 3z" fill="${CREAM}"/><path d="M24 20V6"/><path d="M24 6l13 4-13 4z" fill="${VERM}"/>`),
  ghost: () => g(`<path d="M13 55V30a19 19 0 0 1 38 0v25l-6.300-5-6.300 5-6.400-5-6.300 5-6.400-5z" fill="${CREAM}"/><path d="M27 41h10" stroke-width="2.500"/>`) + dot(25, 30, 3.200) + dot(39, 30, 3.200),
  slip: () => g(`<path d="M11 8h42v48l-5.250-4-5.250 4-5.250-4-5.250 4-5.250-4-5.250 4-5.250-4-5.250 4z" fill="${CREAM}"/><path d="M17 20h30" stroke-dasharray="3 4" stroke-width="2.500"/>`) + T(32, 43, 17, '$0', 'var(--f-mono)'),
  chip: () => g(`<circle cx="32" cy="32" r="22" fill="${VERM}"/><circle cx="32" cy="32" r="15" fill="none" stroke="${CREAM}" stroke-width="6" stroke-dasharray="7.85 7.85"/><circle cx="32" cy="32" r="8.500" fill="${CREAM}"/>`),
  bookmark: () => g(`<path d="M16 6h32v52l-16-12-16 12z" fill="${LIME}"/><path d="M26 18h12" stroke-width="2.500"/>`),
  lens: () => g(`<path d="M37 37l16 16" stroke-width="11"/>`) + `<path d="M37 37l16 16" stroke="${VERM}" stroke-width="5.500" stroke-linecap="round"/>` + g(`<circle cx="26" cy="26" r="17" fill="${CREAM}"/>`) + T(26, 34, 22, '?'),
  snake: () => g(`<g transform="rotate(-12 20 40)"><rect x="5" y="25" width="28" height="28" rx="4" fill="${CREAM}"/></g><g transform="rotate(10 46 28)"><rect x="32" y="11" width="28" height="28" rx="4" fill="${CREAM}"/></g>`) + dot(19, 39.500, 3.800, VERM) + dot(46, 25, 3.800, VERM),
  shelf: () => g(`<path d="M20 10h24v14c0 9-5 14-12 14s-12-5-12-14z" stroke-dasharray="4 5"/><path d="M32 38v7" stroke-dasharray="3 4"/><path d="M6 54h52" stroke-width="5"/>`),
  scale: () => g(`<path d="M32 10v40M18 53h28M8 20h48" stroke-width="3.500"/><path d="M8 20 2 36h12zM56 20l-6 16h12z" fill="${CREAM}"/>`) + dot(32, 10, 4, LIME),
  flag: () => g(`<path d="M14 8v50"/><rect x="14" y="10" width="36" height="26" fill="${CREAM}"/>`) + [0, 1, 2, 3, 4, 5].map((i) => `<rect x="${14 + (i % 3) * 12 + (1.500)}" y="${11.500 + Math.floor(i / 3) * 12.500}" width="9" height="11" fill="${(i + Math.floor(i / 3)) % 2 ? INK : 'none'}" stroke="none"/>`).join(''),
  cards: () => g(`<g transform="rotate(-14 24 40)"><rect x="8" y="14" width="28" height="40" rx="4" fill="${CREAM}"/></g><g transform="rotate(12 44 34)"><rect x="25" y="10" width="28" height="42" rx="4" fill="${CREAM}"/></g>`)
    + `<g transform="translate(14 22) scale(.7)"><path d="${SUIT_PATH.S}" fill="${INK}"/></g><g transform="translate(37 20) scale(.8)"><path d="${SUIT_PATH.H}" fill="${VERM}"/></g>`,
  dice1: () => GLYPH.snake(),
  poker: () => g(`<g transform="rotate(-16 22 36)"><rect x="6" y="12" width="28" height="40" rx="4" fill="${CREAM}"/></g><g transform="rotate(10 40 32)"><rect x="24" y="8" width="28" height="40" rx="4" fill="${CREAM}"/></g>`)
    + `<g transform="translate(10 21) scale(.7)"><path d="${SUIT_PATH.S}" fill="${INK}"/></g><g transform="translate(32 16) scale(.75)"><path d="${SUIT_PATH.H}" fill="${VERM}"/></g>`
    + g(`<circle cx="46" cy="47" r="12" fill="${LIME}"/><circle cx="46" cy="47" r="7" fill="none" stroke-width="2.200" stroke-dasharray="3.5 3.5"/>`),
  coinflip: () => g(`<g transform="rotate(-16 32 33)"><ellipse cx="32" cy="33" rx="17" ry="23" fill="${LIME}"/><ellipse cx="32" cy="33" rx="10" ry="15" fill="none" stroke-width="2.500" stroke-dasharray="3 4"/></g><path d="M11 49c-4 4-4 9 0 12M53 15c4-4 4-9 0-12" stroke-width="2.500"/>`)
    + `<path d="M34 22l-7 12h5.500l-3.500 10 9-13h-6z" fill="${VERM}" stroke="${INK}" stroke-width="2" stroke-linejoin="round"/>`,
  war: () => g(`<g transform="rotate(-12 22 36)"><rect x="6" y="14" width="27" height="40" rx="4" fill="${CREAM}"/></g><g transform="rotate(12 44 34)"><rect x="31" y="10" width="27" height="40" rx="4" fill="${CREAM}"/></g>`)
    + T(19, 43, 20, 'K') + T(45, 39, 20, 'A', 'var(--f-display)', VERM)
    + `<path d="M30 20l-5 10h5l-3 9 8-11h-5.500z" fill="${LIME}" stroke="${INK}" stroke-width="2" stroke-linejoin="round"/>`,
  dice: () => g(`<g transform="rotate(-14 24 40)"><rect x="6" y="24" width="30" height="30" rx="5" fill="${CREAM}"/>${dot(15, 33, 2.800)}${dot(27, 33, 2.800)}${dot(15, 45, 2.800)}${dot(27, 45, 2.800)}</g><g transform="rotate(12 44 26)"><rect x="30" y="8" width="28" height="28" rx="5" fill="${LIME}"/>${dot(37, 15, 2.800)}${dot(51, 15, 2.800)}${dot(44, 22, 2.800)}${dot(37, 29, 2.800)}${dot(51, 29, 2.800)}</g>`),
  bomb: () => g(`<circle cx="29" cy="37" r="19" fill="#2A2420"/><path d="M41 21l5-6"/><path d="M46 15c3-3 6-2 8 1" stroke="${BONE}" stroke-width="3.500"/>`)
    + `<path d="M55 6l1.800 4.400 4.400 1.800-4.400 1.800L55 18.400l-1.800-4.400-4.400-1.800 4.400-1.800z" fill="${VERM}" stroke="${INK}" stroke-width="1.500" stroke-linejoin="round"/>`
    + `<path d="M19 30a12 12 0 0 1 8-7" fill="none" stroke="${CREAM}" stroke-width="3.500" stroke-linecap="round"/>`,
  gem: () => g(`<path d="M14 24 22 11h20l8 13-18 29z" fill="${LIME}"/><path d="M14 24h36M22 11l10 13 10-13M32 24v29" stroke-width="2.500"/>`),
  mines: () => GLYPH.bomb() + `<g transform="translate(30 32) scale(.48)">${GLYPH.gem()}</g>`,
  mole: () => g(`<ellipse cx="32" cy="50" rx="27" ry="9" fill="#2A2420"/><path d="M15 50c0-17 6-29 17-29s17 12 17 29z" fill="${BONE}"/><circle cx="18" cy="27" r="4.500" fill="${BONE}"/><circle cx="46" cy="27" r="4.500" fill="${BONE}"/><path d="M5 50a27 9 0 0 0 54 0v3a27 9 0 0 1-54 0z" fill="${FELT2}"/>`)
    + dot(26, 35, 2.600) + dot(38, 35, 2.600)
    + `<ellipse cx="32" cy="42" rx="5" ry="3.800" fill="${VERM}" stroke="${INK}" stroke-width="2"/><ellipse cx="21" cy="49" rx="5" ry="3.200" fill="${CREAM}" stroke="${INK}" stroke-width="2"/><ellipse cx="43" cy="49" rx="5" ry="3.200" fill="${CREAM}" stroke="${INK}" stroke-width="2"/>`,
  tower: () => g(`<path d="M16 58V22h-5V9h9v6h6V9h12v6h6V9h9v13h-5v36z" fill="${BONE}"/><path d="M16 34h32M16 46h32M26 22v12M38 34v12M26 46v12" stroke-width="2.200"/><path d="M26 58V48a6 6 0 0 1 12 0v10z" fill="#2A2420"/><path d="M32 9V1"/>`)
    + `<path d="M32 1l13 4-13 4z" fill="${VERM}" stroke="${INK}" stroke-width="2.500" stroke-linejoin="round"/>`,
  sun: () => g(`<circle cx="32" cy="32" r="12" fill="${LIME}"/><path d="M32 6v8M32 50v8M6 32h8M50 32h8M13 13l6 6M45 45l6 6M13 51l6-6M45 19l6-6"/>`),
  warning: () => g(`<path d="M32 8 58 54H6z" fill="${LIME}"/><path d="M32 24v14"/>`) + dot(32, 46, 2.800),
};

export const GLYPH_NAMES = Object.keys(GLYPH);

/** Small square sticker: colour-block tile, thick outline, halftone corner. */
export function sticker(name, { size = 48, bg = 'cream', rot = 0, ht = true, cls = '' } = {}) {
  const fill = TILE_BG[bg] || bg;
  const glyph = (GLYPH[name] || GLYPH.star)();
  const tone = bg === 'felt' || bg === 'ink' ? 'ht-dots-light' : 'ht-dots';
  return `<svg class="sticker ${cls}" width="${size}" height="${size}" viewBox="0 0 64 64" style="${rot ? `transform:rotate(${rot}deg)` : ''}" aria-hidden="true">
    <rect x="2" y="2" width="60" height="60" rx="3" fill="${fill}" stroke="${INK}" stroke-width="3"/>
    ${ht ? `<path d="M2 62V34L30 62z" fill="url(#${tone})" opacity=".55"/>` : ''}${glyph}</svg>`;
}

/** The two faces of the Coinflip coin: a crown for heads, a star for tails. Flat, original, no portraits. */
export const coinFace = (side) => {
  const heads = side === 'heads';
  const emblem = heads
    ? `<path d="M-19 12-23-12-9 0 0-17 9 0 23-12 19 12z" fill="${INK}"/><rect x="-19" y="14" width="38" height="7" fill="${INK}"/>`
    : `<polygon points="0,-22 6.500,-7 22,-7 9.500,3 14,19 0,9.500 -14,19 -9.500,3 -22,-7 -6.500,-7" fill="${INK}"/>`;
  return `<svg class="coin-face" viewBox="0 0 100 100" aria-hidden="true"><circle cx="50" cy="50" r="47" fill="${heads ? LIME : CREAM}" stroke="${INK}" stroke-width="4"/>
    <circle cx="50" cy="50" r="38" fill="none" stroke="${INK}" stroke-width="2.500" stroke-dasharray="2.500 5.500"/><g transform="translate(50 49)">${emblem}</g>
    <text x="50" y="79.500" text-anchor="middle" font-size="8.500" font-weight="800" letter-spacing="3" font-family="var(--f-mono)" fill="${INK}">${heads ? 'HEADS' : 'TAILS'}</text></svg>`;
};

/** Bare glyph (no tile), for use on posters. */
export const glyph = (name) => (GLYPH[name] || GLYPH.star)();

// ---- the casino game pictures: one mapping for the lobby posters, the menu, the game headers and the winners list ----
// Files live in /casino-icons (480px, for posters) and /casino-icons/small (128px, for the little tiles). Whoever swaps the
// artwork again only has to replace those files. `bg` is the colour block each picture was drawn to sit on.
export const GAME_ICON = {
  chicken: { bg: LIME }, blackjack: { bg: FELT }, roulette: { bg: VERM }, limbo: { bg: CREAM }, coinflip: { bg: '#2A2420' },
  war: { bg: CREAM }, dice: { bg: FELT }, mines: { bg: VERM }, moles: { bg: LIME }, tower: { bg: CREAM }, poker: { bg: '#2A2420' },
  hilo: { bg: '#2A2420' }, wheel: { bg: FELT }, rps: { bg: LIME },
};
const iconSrc = (id, small = false) => `/casino-icons/${small ? 'small/' : ''}${GAME_ICON[id] ? id : 'chicken'}.${(GAME_ICON[id] || {}).ext || 'png'}`;
/** The picture itself, drawn inside a 64-unit box so the poster layouts can place, scale and tilt it like the old glyphs. */
const iconImage = (id) => `<image href="${iconSrc(id)}" x="-3" y="-3" width="70" height="70" preserveAspectRatio="xMidYMid meet"/>`;

// ---- game posters for the lobby ----
const POSTER = {
  chicken: { bg: LIME, glyph: 'chicken', band: VERM, no: '01' },
  blackjack: { bg: FELT, glyph: 'cards', band: LIME, no: '02', dark: true },
  roulette: { bg: VERM, glyph: 'wheel', band: CREAM, no: '03' },
  limbo: { bg: CREAM, glyph: 'rocket', band: VERM, no: '04' },
  coinflip: { bg: '#2A2420', glyph: 'coinflip', band: LIME, no: '05', dark: true },
  war: { bg: CREAM, glyph: 'war', band: FELT2, no: '06' },
  dice: { bg: FELT, glyph: 'dice', band: VERM, no: '07', dark: true },
  mines: { bg: VERM, glyph: 'mines', band: INK, no: '08' },
  moles: { bg: LIME, glyph: 'mole', band: FELT2, no: '09' },
  tower: { bg: CREAM, glyph: 'tower', band: FELT2, no: '10' },
  poker: { bg: '#2A2420', glyph: 'poker', band: VERM, no: '11', dark: true },
  hilo: { bg: '#2A2420', glyph: 'cards', band: LIME, no: '12', dark: true },
  wheel: { bg: FELT, glyph: 'wheel', band: VERM, no: '13', dark: true },
  rps: { bg: LIME, glyph: 'war', band: FELT2, no: '14' },
};
export function poster(id, { cls = '', wide = false, banner = false } = {}) {
  const p = POSTER[id] || POSTER.chicken;
  const dark = !!p.dark;
  const tone = dark ? '-light' : '';
  const ink = dark ? CREAM : INK;
  if (banner) {   // full-width strip: the glyph marches across
    const g = iconImage(id);
    return `<svg class="poster ${cls}" viewBox="0 0 480 100" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <rect width="480" height="100" fill="${p.bg}"/><rect y="72" width="480" height="28" fill="${p.band}"/><rect y="72" width="480" height="28" fill="url(#ht-stripes${tone})" opacity=".5"/><rect y="70.500" width="480" height="3" fill="${INK}"/>
      ${[0, 1, 2, 3, 4].map((k) => `<g transform="translate(${24 + k * 86} ${4 + (k % 2) * 3}) scale(.9) rotate(${k % 2 ? 6 : -6} 32 32)" opacity="${0.45 + k * 0.14}">${g}</g>`).join('')}
      <text x="452" y="16" text-anchor="end" font-size="9" font-weight="700" font-family="var(--f-mono)" letter-spacing="2" fill="${ink}">No.${p.no}</text></svg>`;
  }
  if (wide) {   // 2:1 version: the glyph repeats like a trail
    const g = iconImage(id);
    return `<svg class="poster ${cls}" viewBox="0 0 240 120" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <rect width="240" height="120" fill="${p.bg}"/><rect y="86" width="240" height="34" fill="${p.band}"/><rect y="86" width="240" height="34" fill="url(#ht-stripes${tone})" opacity=".5"/><rect y="84.500" width="240" height="3" fill="${INK}"/>
      <g transform="translate(18 18) scale(.7) rotate(-8 32 32)" opacity=".55">${g}</g><g transform="translate(62 12) scale(.85) rotate(-4 32 32)" opacity=".8">${g}</g>
      <g transform="translate(112 4) scale(1.15)">${g}</g>
      <text x="8" y="16" font-size="9" font-weight="700" font-family="var(--f-mono)" letter-spacing="2" fill="${ink}">No.${p.no}</text></svg>`;
  }
  return `<svg class="poster ${cls}" viewBox="0 0 120 150" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
    <rect width="120" height="150" fill="${p.bg}"/>
    <rect y="104" width="120" height="46" fill="${p.band}"/><rect y="104" width="120" height="46" fill="url(#ht-stripes${tone})" opacity=".5"/>
    <rect y="102" width="120" height="3" fill="${INK}"/>
    <image href="${iconSrc(id)}" x="23" y="19" width="74" height="74" preserveAspectRatio="xMidYMid meet"/>
    <text x="8" y="16" font-size="8" font-weight="700" font-family="var(--f-mono)" letter-spacing="1.5" fill="${ink}">No.${p.no}</text></svg>`;
}

// ---- logo ----
export const logoMark = (size = 30) => `<svg class="logo-mark" width="${size}" height="${size}" viewBox="0 0 32 32" aria-hidden="true"><rect x="1.500" y="1.500" width="29" height="29" rx="3" fill="${LIME}" stroke="${INK}" stroke-width="2.500"/><path d="M21.500 10.500A8 8 0 1 0 21.500 21.500" fill="none" stroke="${INK}" stroke-width="4" stroke-linecap="round"/><circle cx="22.500" cy="16" r="2.600" fill="${INK}"/></svg>`;

// ---- awards, categories, games -> glyph + tile colour ----
export const AWARD_ART = {
  topDog: ['crown', 'lime'], hotSeat: ['flame', 'verm'], rocketMan: ['rocket', 'cream'], freefall: ['chartdown', 'cream'], oracle: ['crystal', 'felt'],
  sharpshooter: ['target', 'cream'], whale: ['whale', 'felt'], highRoller: ['chips', 'felt'], luckyCharm: ['clover', 'cream'], cardShark: ['cardspade', 'lime'],
  chickenChamp: ['chicken', 'lime'], spinDoctor: ['wheel', 'cream'], houseFavorite: ['house', 'bone'], badBeat: ['brokenheart', 'cream'], paperHands: ['paper', 'bone'],
  marketMaker: ['brain', 'verm'], chatterbox: ['bubble', 'lime'], degenerate: ['die', 'verm'], comebackKid: ['mountain', 'cream'], ghost: ['ghost', 'felt'],
};
export const CATEGORY_ART = {
  General: ['die', 'cream'], Sports: ['trophy', 'felt'], Gaming: ['controller', 'verm'], Life: ['sprout', 'cream'],
  Money: ['coin', 'felt'], Dares: ['bolt', 'lime'], Music: ['note', 'cream'], Other: ['star', 'verm'],
};


export const awardSticker = (key, size = 56) => { const [n, bg] = AWARD_ART[key] || ['star', 'cream']; return sticker(n, { size, bg }); };
/** A game's picture on its own colour block, for the menu, the game header and the winners list. Same look as the old
 *  stickers (thick outline, hard corners); the game's name is always written next to it, so the picture itself is not read out. */
export const gameSticker = (id, size = 36) => `<span class="gicon" style="--s:${size}px;--bg:${(GAME_ICON[id] || GAME_ICON.chicken).bg}"><img src="${iconSrc(id, true)}" alt="" width="${size}" height="${size}" decoding="async"></span>`;

// ---- rank badges: a flat shield, a colour per tier, and chevrons for the division (three for division I, two for II, one for III; Master gets a star) ----
const RANK_COLORS = { bronze: ['#C98A4B', '#8C5A2B'], silver: ['#D5D9DE', '#98A0AA'], gold: ['#F2C230', '#B8870C'], platinum: ['#8FE3D6', '#3BA99B'], diamond: ['#6EC6FF', '#2B86C9'], master: ['#FF4B2B', '#B8200A'] };
/** The badge for a rank. Takes the short form sent with every name ({ t, d, l }) or the full one ({ tier, division, label }). */
export function rankBadge(r, size = 22) {
  const tier = (r && (r.tier || r.t)) || 'bronze', div = (r && (r.division ?? r.d)) || 0;
  const label = String((r && (r.label || r.l)) || 'Bronze III').replace(/[<>"&]/g, '');
  const [fill, shade] = RANK_COLORS[tier] || RANK_COLORS.bronze;
  const pips = tier === 'master' ? 0 : 4 - div;                       // III -> 1, II -> 2, I -> 3
  const chevrons = [...Array(pips)].map((_, i) => `<path d="M13 ${31 - i * 6.5} L20 ${25 - i * 6.5} L27 ${31 - i * 6.5}" fill="none" stroke="${INK}" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/>`).join('');
  const star = tier === 'master' ? `<polygon points="20,13 23,20 30.500,20.600 24.800,25.400 26.600,32.800 20,28.800 13.400,32.800 15.200,25.400 9.500,20.600 17,20" fill="${LIME}" stroke="${INK}" stroke-width="2.4" stroke-linejoin="round"/>` : '';
  return `<svg class="rkb rkb-${tier}" width="${size}" height="${Math.round(size * 1.1)}" viewBox="0 0 40 44" role="img" aria-label="${label}"><title>${label}</title>
    <path d="M20 3 36 9v13c0 9-7 16-16 19C11 38 4 31 4 22V9z" fill="${fill}"/><path d="M20 3 36 9v13c0 9-7 16-16 19z" fill="${shade}"/>
    <path d="M20 3 36 9v13c0 9-7 16-16 19C11 38 4 31 4 22V9z" fill="none" stroke="${INK}" stroke-width="3" stroke-linejoin="round"/>${chevrons}${star}</svg>`;
}
/** A badge and the label, small enough to sit next to a name in a list. */
export const rankTag = (r, size = 18) => (r ? `<span class="rkt" title="${String(r.label || r.l || '').replace(/[<>"&]/g, '')}">${rankBadge(r, size)}</span>` : '');
