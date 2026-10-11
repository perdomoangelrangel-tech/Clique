"""Cada regla del libro y de la seguridad por fila, vista en rojo: se siembra un error a propósito en una copia de las
migraciones (un "mutante") y la prueba que cuida esa regla tiene que fallar. Si alguna pasa, la prueba no cuida nada.

    python -m backend.datos.mutantes            # todos
    python -m backend.datos.mutantes candados   # los que tengan esa palabra en el nombre

Necesita psycopg y pgserver. Cada mutante corre sus pruebas en otro proceso, con CLIQUE_MIGRATIONS_DIR apuntando a la copia.
"""
import glob
import os
import shutil
import subprocess
import sys
import tempfile

from . import pg_local

LIBRO = "20261010000200_libro.sql"
RLS = "20261010000300_seguridad_por_fila.sql"

# (nombre, archivo, [(texto original, texto mutante)], pruebas que deben ponerse en rojo)
MUTANTES = [
    ("suma-cero: no se revisa que las líneas sumen cero", LIBRO,
     [("    if v_sum <> 0 then\n        raise exception 'unbalanced", "    if false then\n        raise exception 'unbalanced")],
     ["tests.test_libro_pg.UnMovimientoQueSumaCero.test_lines_that_do_not_add_up_to_zero_are_refused"]),
    ("negativos: una persona puede quedar debiendo", LIBRO,
     [("if v_acct.kind <> 'system' and v_new < 0 then", "if false then")],
     ["tests.test_libro_pg.NingunaCuentaDePersonaQuedaNegativa.test_taking_more_than_a_person_has_is_refused"]),
    ("candados: se toman en el orden en que llegan las líneas", LIBRO,
     [("             order by a.id\n               for update) as locked;", "            ) as locked;"),
      ("          from jsonb_array_elements(p_lines) as l\n         order by 1\n    loop",
       "          from jsonb_array_elements(p_lines) with ordinality as l(v, n)\n         order by n\n    loop"),
      ("        select (l->>'account')::bigint as account, (l->>'amount')::bigint as amount\n          from jsonb_array_elements(p_lines) with ordinality",
       "        select (l.v->>'account')::bigint as account, (l.v->>'amount')::bigint as amount\n          from jsonb_array_elements(p_lines) with ordinality")],
     ["tests.test_libro_pg.LosCandadosVanEnOrdenFijo"]),
    ("idempotencia: la misma clave vuelve a mover dinero", LIBRO,
     [("values (p_idempotency_key, p_reason, v_hash", "values (p_idempotency_key || clock_timestamp()::text, p_reason, v_hash")],
     ["tests.test_libro_pg.LaMismaClaveDevuelveLaMismaTransaccion.test_a_retry_returns_the_first_transaction_and_moves_nothing"]),
    ("idempotencia: la misma clave con otras líneas se acepta", LIBRO,
     [("if v_prior <> v_hash then", "if false then")],
     ["tests.test_libro_pg.LaMismaClaveDevuelveLaMismaTransaccion.test_the_same_key_for_something_else_is_refused"]),
    ("fichas: la cuenta chips se mueve aunque esté apagada", LIBRO,
     [("                  and not a.enabled) then", "                  and false) then")],
     ["tests.test_libro_pg.LasFichasCompradasEstanApagadas.test_chips_cannot_move_while_switched_off"]),
    ("líneas: una cuenta puede aparecer dos veces", LIBRO,
     [("    if v_sum <> v_n then\n        raise exception 'invalid_lines: cada cuenta", "    if false then\n        raise exception 'invalid_lines: cada cuenta")],
     ["tests.test_libro_pg.UnMovimientoQueSumaCero.test_badly_shaped_lines_are_refused"]),
    ("permisos: el navegador puede llamar al libro", LIBRO,
     [("revoke all on function public.post_transaction(text, text, jsonb, jsonb) from public, anon, authenticated;",
       "grant execute on function public.post_transaction(text, text, jsonb, jsonb) to anon, authenticated;")],
     ["tests.test_libro_pg.SoloElServidorMueveDinero.test_the_browser_cannot_call_the_ledger"]),
    ("rls: cuentas sin seguridad por fila", RLS,
     [("alter table public.accounts            enable row level security;\n", "")],
     ["tests.test_esquema_pg.CadaTablaTieneSeguridadPorFila", "tests.test_esquema_pg.OtroUsuarioNoLaVe.test_accounts"]),
    ("rls: cualquiera ve a cualquier persona", RLS,
     [("using (id = auth.uid() or public.shares_circle_with(id));", "using (true);")],
     ["tests.test_esquema_pg.OtroUsuarioNoLaVe.test_profiles"]),
    ("rls: el libro de otros se ve", RLS,
     [("create policy ledger_entries_read on public.ledger_entries for select to authenticated\n    using (public.owns_account(account_id));",
       "create policy ledger_entries_read on public.ledger_entries for select to authenticated\n    using (true);")],
     ["tests.test_esquema_pg.OtroUsuarioNoLaVe.test_ledger_entries"]),
    ("rls: un mercado de círculo se ve desde fuera", RLS,
     [("using (circle_id is null or public.is_circle_member(circle_id));", "using (true);")],
     ["tests.test_esquema_pg.OtroUsuarioNoLaVe.test_markets"]),
    ("rls: el cierre semanal de un círculo se ve desde fuera", RLS,
     [("create policy week_standings_read on public.week_standings for select to authenticated\n    using (public.is_circle_member(circle_id));",
       "create policy week_standings_read on public.week_standings for select to authenticated\n    using (true);")],
     ["tests.test_esquema_pg.OtroUsuarioNoLaVe.test_week_standings"]),
    ("rls: el navegador puede escribir", RLS,
     [("revoke insert, update, delete, truncate on all tables in schema public from anon, authenticated;",
       "grant insert, update, delete on all tables in schema public to authenticated;\n"
       "create policy accounts_write on public.accounts for update to authenticated using (true);")],
     ["tests.test_esquema_pg.NadieEscribeDesdeElNavegador", "tests.test_libro_pg.SoloElServidorMueveDinero.test_the_browser_cannot_write_a_balance"]),
    ("rls: el estado de una ronda en curso se ve", RLS,
     [("revoke select on public.casino_rounds from authenticated;\n", "")],
     ["tests.test_esquema_pg.ElEstadoDeUnaRondaNoSeVe"]),
]


def run(only=None):
    results = []
    for name, filename, edits, tests in MUTANTES:
        if only and only not in name:
            continue
        folder = tempfile.mkdtemp(prefix="clique-mutante-")
        try:
            for path in pg_local.migration_files():
                shutil.copy(path, folder)
            target = os.path.join(folder, filename)
            with open(target, "r", encoding="utf-8") as f:
                sql = f.read()
            for old, new in edits:
                if old not in sql:
                    results.append((name, "NO APLICA", f"no encontré el texto a cambiar: {old[:60]!r}"))
                    break
                sql = sql.replace(old, new)
            else:
                with open(target, "w", encoding="utf-8", newline="\n") as f:
                    f.write(sql)
                env = {**os.environ, "CLIQUE_MIGRATIONS_DIR": folder}
                p = subprocess.run([sys.executable, "-m", "unittest", *tests], cwd=pg_local.ROOT, env=env,
                                   capture_output=True, text=True, timeout=900)
                tail = (p.stderr.strip().splitlines() or [""])[-1]
                if "skipped" in p.stderr and "OK" in tail:
                    results.append((name, "OMITIDO", tail))
                elif p.returncode != 0:
                    results.append((name, "EN ROJO", tail))
                else:
                    results.append((name, "SOBREVIVE", tail))
        finally:
            shutil.rmtree(folder, ignore_errors=True)
    return results


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not pg_local.AVAILABLE:
        print(pg_local.WHY_NOT)
        return 1
    results = run(argv[0] if argv else None)
    for name, verdict, tail in results:
        print(f"{verdict:10} {name}   ({tail})")
    alive = [r for r in results if r[1] != "EN ROJO"]
    print(f"\n{len(results) - len(alive)} de {len(results)} mutantes puestos en rojo.")
    return 1 if alive else 0


if __name__ == "__main__":
    sys.exit(main())
