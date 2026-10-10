# equipo/

Los documentos de coordinación del equipo de agentes que mejora Clique.

| Archivo | Para qué |
|---|---|
| `DECISIONES.md` | Lo que firmó el dueño (D1 a D10) y las preguntas que tiene abiertas. Manda sobre todo lo demás |
| `ORDENES_E<n>.md` | La orden vigente de cada encargo. El gancho de inicio la recuerda y `/orden E<n>` la lee |
| `EQUIPO.md` · `COORDINACION.md` | Cómo trabaja el equipo, cómo se coordina y qué no hace nunca |
| `PROPIEDAD_DE_ARCHIVOS.md` | Qué archivo es de quién (los ganchos lo hacen cumplir) |
| `CONTRATOS.md` · `contratos/` | Las firmas y formas de datos que cruzan encargos |
| `DEFINICION_DE_TERMINADO.md` | Las siete casillas de cualquier entregable |
| `GLOSARIO.md` | Qué quiere decir cada palabra del proyecto |
| `COMO_ESCRIBIR_ORDENES.md` | Cómo escribe E0 una orden para que se cumpla |
| `BITACORA.md` | Avances, bloqueos y peticiones. Cada rama solo agrega al final |
| `BITACORA_COMBINADA.md` | Todas las bitácoras juntas. Se genera con `combinar_bitacoras.sh` |
| `VERIFICADO.md` | Lo que E7 comprobó de cada entregable, con el comando que lo decide |
| `ROJOS_CONOCIDOS.json` | Pruebas en rojo que se toleran, con dueño y porqué |
| `decisiones/` | Las decisiones largas (ADR-001 a ADR-006) |
| `historia/ronda-0/` | La ronda 0: órdenes OT-001 a OT-006, bitácoras y protocolo anterior |

## Correr las cosas

```
python server.py                                   # la app en http://localhost:3000
python -m unittest discover -s tests -t .          # la suite completa (unos 8 minutos)
python -m unittest tests.test_ledger               # una sola parte
node herramientas/ganchos.test.mjs                 # la prueba de las reglas de los ganchos
node herramientas/ganchos.en-vivo.test.mjs         # los ganchos de punta a punta, en una carpeta de juguete
bash equipo/combinar_bitacoras.sh                  # junta las bitácoras de todas las ramas
```
