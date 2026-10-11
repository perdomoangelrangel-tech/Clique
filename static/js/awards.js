/* The weekly awards (backend/weekly.py, AWARD_DEFS) in the language on screen. The server sends their names in English; this maps
   them by key. An award the server adds later shows its own words until it gets a line here. */
import { t } from './i18n.js';

const AWARDS = {                                                                     // i18n: claves ↓
  topDog: ['El Mero Mero', 'Quien tiene más cuando cierra la semana'],
  hotSeat: ['La Silla Caliente', 'La peor semana del círculo (la caída más grande o la ganancia más chica). Hora del castigo'],
  rocketMan: ['Cohete', 'La ganancia más grande de la semana'],
  freefall: ['Caída Libre', 'La caída más grande de la semana'],
  oracle: ['El Oráculo', 'La mayor ganancia por predicciones acertadas'],
  sharpshooter: ['Francotirador', 'El mejor porcentaje de aciertos (al menos 3 apuestas resueltas)'],
  whale: ['La Ballena', 'Hizo la apuesta individual más grande'],
  highRoller: ['Apostador Fuerte', 'Apostó más que nadie en los juegos'],
  luckyCharm: ['Amuleto de la Suerte', 'Pegó el multiplicador más alto en un juego (x5 o más)'],
  cardShark: ['Tahúr', 'Ganó más manos de blackjack'],
  chickenChamp: ['Guerrero del Camino', 'Cruzó al pollo con el multiplicador más alto'],
  spinDoctor: ['Dueño del Giro', 'La mayor ganancia en la ruleta'],
  houseFavorite: ['Consentido de la Casa', 'Le dejó más fichas que nadie a los juegos del casino'],
  badBeat: ['Mala Pata', 'Perdió más en una apuesta que parecía segura (70¢ o más)'],
  paperHands: ['Manos de Papel', 'Perdió más por vender una posición antes de tiempo'],
  marketMaker: ['Creador de Mercados', 'Propuso más eventos'],
  chatterbox: ['Perico', 'Dejó más comentarios'],
  degenerate: ['Incansable', 'Más apuestas y manos jugadas (10 o más)'],
  comebackKid: ['La Remontada', 'Subió más lugares en las posiciones'],
  ghost: ['Fantasma', 'No hizo absolutamente nada esta semana'],
};                                                                                   // i18n: fin

export const awardName = (a) => (a && AWARDS[a.key] ? t(AWARDS[a.key][0]) : (a && a.name) || '');
export const awardDesc = (a) => (a && AWARDS[a.key] ? t(AWARDS[a.key][1]) : (a && a.desc) || '');
