# Bitácora del cerebro

Decisiones, revisiones y cambios de plan. Lo más nuevo arriba.

---

## 2026-10-10 — Aprobaciones del dueño, repositorio y Supabase

**Decisiones del dueño:**
- Aprueba todo el plan (ADR-001 aceptado).
- Estética de casino premium hecha en Blender: "todo se debe sentir premium" → ADR-005, rol `arte3d`, OT-006.
- Agrega paquetes de fichas de máximo US$5 con muchísimas fichas → ADR-004. Se le explicó que el precio bajo no quita el riesgo legal; se diseñó con cuenta `chips` aparte, fuera de la competencia semanal, sin transferencias ni canje, sin caducidad, y con la compra apagada hasta dictamen legal.

**Hecho:**
- Repositorio `perdomoangelrangel-tech/Clique` con la app actual en `legacy/clique` (301 archivos, sin cambios), su huella `legacy/clique.sha256`, el sistema de agentes y las órdenes OT-001 a OT-006.
- Proyecto de Supabase `Clique` (ref `rrmifvptjajfvxxdqqek`, us-east-1) creado por el dueño en el plan Pro.
- Revisión independiente del sistema de agentes: se corrigieron 12 problemas (sincronizar `main` antes de crear ramas, leer órdenes desde `origin/main`, quién escribe en `main`, OT-001 sin excepción de rama, finales de línea en Windows, permisos de `git push`, superposición de OT-002 y OT-005, criterios circulares, concurrencia y RLS en OT-004, notas del azar en OT-005).

**Siguiente paso:** el dueño clona el repositorio en VS Code y lanza OT-001.

---

## 2026-10-09 — Diagnóstico y arranque de la Fase 0

**Hecho:**
- Diagnóstico completo de `legacy/clique`: 11,692 líneas de Python, 8,441 de JavaScript, 119 rutas de API, 13 juegos + póker. Las 1,142 pruebas pasan (7 omitidas por falta de Chrome en el entorno), 411 s.
- Revisión visual en 390×844 y 1366×768.
- Documento "Clique — Diagnóstico y plan maestro".
- Protocolo de agentes, ADR-001 a ADR-003, órdenes OT-001 a OT-005.

**Hallazgos clave:**
- Base de datos en un archivo JSON con candado global: no escala (ADR-001).
- Interfaz solo en inglés; encabezado del celular ocupa ~29% de la pantalla; en Mines a 1366×768 el botón de apostar queda fuera de pantalla porque el buscador de mercados y la cinta aparecen en el casino.
- Sin git, sin moderación, sin PWA, sin aviso de privacidad ni verificación de edad.
- `round2` en el legacy redondea a la mitad hacia arriba; los pagos usan `floor_cents` (hacia abajo). No confundirlos al portar.
