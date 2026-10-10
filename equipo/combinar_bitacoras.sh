#!/usr/bin/env bash
# Junta la bitácora de cada rama de encargo en equipo/BITACORA_COMBINADA.md.
#
# Por qué se genera y no se escribe a mano: cada encargo escribe en la bitácora de SU rama
# y ninguno ve las de los demás. Una copia hecha a mano se queda vieja el mismo día.
#
#   bash equipo/combinar_bitacoras.sh
#
# Solo lee con `git show` (ramas de origin) y escribe el resultado en el árbol donde se corre.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
git fetch origin --quiet || true

SALIDA="equipo/BITACORA_COMBINADA.md"
BASE=$(mktemp)
trap 'rm -f "$BASE"' EXIT
git show origin/integracion:equipo/BITACORA.md > "$BASE" 2>/dev/null || true
# Las líneas que integracion todavía no tiene (las vacías se quitan también: da igual).
solo_nuevas() { grep -Fxv -f "$BASE" || true; }
RAMAS=$(git for-each-ref --format='%(refname:short)' refs/remotes/origin \
        | grep -E '^origin/(integracion|e[0-9]+-)' | sort)

{
  echo "# Bitácora combinada"
  echo
  echo "*Generada por \`equipo/combinar_bitacoras.sh\` el $(date '+%d-%m-%Y %H:%M').*"
  echo "*No se edita a mano: se vuelve a generar. Cada encargo escribe en la bitácora de su rama.*"
  echo
  for r in $RAMAS; do
    if git cat-file -e "$r:equipo/BITACORA.md" 2>/dev/null; then
      # Cada rama rebasa sobre integracion y trae sus líneas: de las ramas e* solo va lo nuevo.
      if [ "$r" = "origin/integracion" ]; then FILTRO=cat; else FILTRO=solo_nuevas; fi
      echo "---"
      echo
      echo "## Rama \`${r#origin/}\` — $(git log -1 --format='%h %ad' --date=format:'%d-%b %H:%M' "$r")"
      echo
      echo "### Peticiones"
      git show "$r:equipo/BITACORA.md" | sed -n '/^## Peticiones/,/^## Registro/p' | sed '1d;$d' | $FILTRO
      echo "### Registro"
      git show "$r:equipo/BITACORA.md" | sed -n '/^## Registro/,$p' | tail -n +2 | $FILTRO
      echo
    fi
  done
} > "$SALIDA"

echo "Escrito $SALIDA con: $(echo $RAMAS | tr '\n' ' ')"
wc -l "$SALIDA"
