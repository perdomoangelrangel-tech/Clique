/* Bookmarked markets are remembered in this browser only. */
const KEY = 'clique-bookmarks';
const read = () => { try { return JSON.parse(localStorage.getItem(KEY) || '[]'); } catch { return []; } };
export const bookmarks = () => new Set(read());
export const isBookmarked = (id) => read().includes(id);
export function toggleBookmark(id) {
  const list = read(); const i = list.indexOf(id);
  if (i >= 0) list.splice(i, 1); else list.push(id);
  try { localStorage.setItem(KEY, JSON.stringify(list.slice(-300))); } catch { /* ignore */ }
  return i < 0;
}
