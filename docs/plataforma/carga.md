# Medición de carga: la línea base

*E1 · 10-oct-2026 · para decidir la etapa C de ADR-006*

## Cómo se mide

```
python scripts/medir_carga.py --personas 50 --segundos 30
```

El script arranca su propio `server.py` con una base vacía en una carpeta temporal (no toca datos de nadie), registra N personas,
las mete al mismo círculo privado con un mercado abierto y abre la conexión en vivo (`/api/stream`) de cada una. Después cada
persona repite **sin pausa** una mezcla de peticiones: ver los mercados (25 %), apostar en el mercado (30 %), tirar los dados del
casino (30 %) y ver su saldo (15 %), todas con la apuesta mínima. Mide cada petición de punta a punta (en milisegundos) e imprime
peticiones por segundo y p50/p95/p99 por tipo. `--sin-vivo` quita las conexiones en vivo; `--url` apunta a un servidor que ya corre;
`--json` guarda los números.

Sin pausas, la prueba mide **lo más que aguanta** el servidor, no el uso normal: una persona real hace una petición cada varios
segundos, no varias por segundo.

## Resultados

Computadora del dueño: Windows 11, Intel i7-13700H (20 hilos), Python 3.11.9. **Ojo:** mientras se midió, había otras sesiones
del equipo corriendo sus suites de pruebas en la misma computadora (9 procesos de Python), así que los números son más bajos y
más ruidosos que en una máquina sola. Hay que repetirlos en el servidor de prueba de Render cuando exista.

### 50 personas, 30 segundos, con conexión en vivo (la orden)

| tipo | peticiones | por seg | p50 ms | p95 ms | p99 ms | no 200 |
|---|---:|---:|---:|---:|---:|---:|
| mercados | 948 | 30.9 | 210.1 | 545.2 | 648.1 | 0 |
| apuesta_mercado | 1152 | 37.6 | 579.6 | 913.9 | 999.2 | 0 |
| dados | 1112 | 36.3 | 564.8 | 897.0 | 1004.7 | 0 |
| saldo | 553 | 18.0 | 198.6 | 548.1 | 650.7 | 0 |
| **total** | **3765** | **122.8** | **371.3** | **855.0** | **989.8** | **0** |

### Para comparar

| corrida | por seg | p50 ms | p95 ms | p99 ms | no 200 |
|---|---:|---:|---:|---:|---:|
| 50 personas, sin conexión en vivo | 110.0 | 448.6 | 914.9 | 1066.0 | 0 |
| 5 personas, con conexión en vivo | 180.0 | 23.4 | 67.3 | 79.8 | 0 |

## Lo que dicen los números

1. **Ningún error.** En las tres corridas, todas las peticiones respondieron 200.
2. **El servidor atiende una petición a la vez.** Con 5 personas da unas 180 por segundo; con 50, **menos** (unas 120), y la latencia
   sube de 23 ms a 371 ms en la mediana y a casi 1 s en p99. Toda petición pasa por un solo candado (`LOCK` en `backend/store.py`),
   así que más personas no dan más rendimiento: hacen cola.
3. **Las conexiones en vivo no son el cuello:** quitarlas no mejora (110 por segundo contra 123).
4. **Las peticiones que escriben cuestan más que las que leen:** apostar y tirar dados tienen una mediana de unos 570 ms con 50 personas,
   contra unos 200 ms para leer. Cada escritura convierte **toda** la base a JSON mientras tiene el candado (`store.stage()`), y
   la petición no responde hasta que esa copia está en disco con `fsync` (`store.commit()`, fuera del candado; las que se juntan
   comparten una sola escritura). Que la caída de 5 a 50
   personas venga de que la base crece (más personas y más historial que copiar en cada escritura) es una **hipótesis por comprobar**:
   habría que medir el tiempo de `store.stage()` y `store.commit()` contra el tamaño de `db.json`.

**Para ADR-006:** para un grupo de amigos (decenas de personas, una petición cada pocos segundos cada una) sobra. Un ritmo
sostenido de unas 100 escrituras por segundo es el techo de este diseño en esta computadora. Si la etapa C busca cientos de personas
activas a la vez, el candado único y la copia completa en cada escritura son lo que hay que quitar, y eso es justo lo que trae
Postgres en la etapa B.

## Pendiente

- Repetir la medición con la computadora sin otras suites corriendo, y en Render cuando exista el servidor de prueba (`--url`).
- Medir `store.stage()`/`store.commit()` contra el tamaño de la base, para confirmar o descartar el punto 4.
