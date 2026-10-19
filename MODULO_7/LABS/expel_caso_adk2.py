"""
Caso ExpeL (baseline vs. técnica): ¿mejoran las REGLAS destiladas al agente?

Es el caso más simple posible para ver el efecto de ExpeL, sin compararlo con otras
técnicas. Un solo cambio entre las dos condiciones: las reglas.

  baseline : el agente sin memoria, 1 intento.
  ExpeL    : el mismo agente, 1 intento, con las reglas que destiló de la experiencia.

Tres pasos:

  1. EXPERIENCIA   6 tareas de entrenamiento, hasta 2 intentos cada una (sin memoria):
                   si falla, reflexiona y reintenta. Es la materia prima de ExpeL.
  2. DESTILACIÓN   un LlmAgent con `output_schema` propone AGREE / ADD / EDIT / REMOVE
                   sobre un banco de reglas, una experiencia por vez (reglas_expel_caso.json).
                   Las tareas que el agente acierta a la primera no se destilan: no hay nada
                   que aprender de ellas.
  3. PRUEBA        6 tareas NUEVAS x 3 repeticiones, 1 intento, baseline vs. ExpeL.

Diseño pensado para que se VEA lo que ExpeL aporta:

  - Dos convenciones de la entidad que el enunciado no dice y que el agente no puede adivinar,
    pero que se deducen comparando su número con el correcto (inventadas para el curso):
      * CARGO FIJO: una transferencia al exterior suma $1,800 de gestión (diferencia constante)
      * DESCUENTO PREMIUM: a un cliente Premium se le cobra el 50% de la comisión (cociente constante)
  - Tres entrenamientos por convención, todos fallan al principio y todos enseñan lo mismo:
    se ve cómo las reglas ganan votos (ADD y después AGREE) en vez de acumular lecciones sueltas.
  - Las reglas son generales y TIENEN ÁMBITO («al exterior», «Premium»). La prueba incluye una
    transferencia nacional y un cliente estándar: ahí el baseline acierta, y la regla no debe
    romperlo. Es el control de que ExpeL no sobre-aplica.

Ayuda numérica: a la experiencia se le agrega la diferencia y el cociente entre el número
del agente y el correcto (lo calcula el código, no el modelo). Sin eso el destilador debe
adivinar la convención a partir de dos números sueltos.

Costo aproximado: ~18 llamadas (experiencia) + 6 (destilación, en
secuencia) + 36 (prueba) = ~60 llamadas, 2-3 minutos.

Salidas: reglas_expel_caso.json y expel_caso_resultados.json (no pisa los de expel_adk2.py).

Uso:  python expel_caso_adk2.py                  # pasos 1-3
      python expel_caso_adk2.py --solo-probar    # paso 3 con reglas_expel_caso.json existente
"""
import asyncio
import json
import os
import sys

from comun import (baseline_vs_tecnica, con_reintentos, correr_en_paralelo, crear_workflow, narrar,
                   registrar_costo, resolver_tarea)
from expel_adk2 import aplicar_operaciones, proponer_operaciones, reglas_para_prompt, texto_banco
from tareas_caso import TEST, TRAIN

ARCHIVO_REGLAS = "reglas_expel_caso.json"
ARCHIVO_RESULTADOS = "expel_caso_resultados.json"
REPETICIONES_TEST = 3
MIN_VOTOS = 2          # solo las reglas confirmadas (>= 2 votos) llegan al prompt


# ─── Destilación ────────────────────────────────────────────────────────────────────
INSTRUCCION_DESTILADOR = """Sos el módulo de destilación de un agente financiero que aprende de su experiencia.
Mantenés un banco de reglas de la entidad. Recibís UNA experiencia (un problema, los intentos del agente,
el número correcto y la relación numérica entre el número del agente y el correcto) y devolvés
operaciones sobre el banco:
- AGREE id_regla: la experiencia confirma una regla existente.
- ADD texto: regla nueva, que NO esté ya en el banco.
- EDIT id_regla texto: corrige o precisa una regla (también si la experiencia la contradice).
- REMOVE id_regla: la regla es incorrecta.

Cómo redactar las reglas:
- Deducí la convención comparando el número del agente con el correcto. Si la diferencia es
  siempre la misma, es un monto fijo que se suma; si el cociente es siempre el mismo, es un
  descuento o recargo porcentual sobre la comisión.
- Decí a qué operaciones o clientes aplica la regla (por ejemplo, «transferencias al exterior»,
  «clientes de tal segmento»): no la generalices a todo.
- Incluí las constantes de la política (montos fijos, porcentajes), pero no los datos de un
  caso concreto (importe o tasa de esta operación).
- Una sola línea, imperativa y verificable. Sin condicionales del tipo «si el enunciado no menciona».
- La tasa porcentual y el importe que aparecen en el enunciado son DATOS DEL CASO, no políticas:
  nunca los escribas como parte de una regla (cada operación trae su propia tasa).
- No hagas ADD si el banco ya tiene una regla con el mismo ámbito (mismo tipo de operación o
  de cliente): usá AGREE si coincide o EDIT si hay que precisarla.
- Si el agente acertó a la primera y no hay nada nuevo, devolvé una lista vacía.

BANCO ACTUAL:
{banco}

EXPERIENCIA:
{experiencia}"""


def experiencia_como_texto(res: dict, tarea: dict) -> str:
    """Resume una trayectoria para el destilador, con la relación numérica de cada fallo."""
    correcto = tarea["correct_answer"]
    lineas = [f"Problema: {tarea['prompt']}",
              f"Número correcto: {correcto}. "
              f"{'Resuelto' if res['resuelta'] else 'NO resuelto'} en {res['intentos']} intento(s)."]
    for a in res["trayectoria"]:
        n = a["numero"]
        linea = f"- Intento {a['intento']}: número={n} ({'OK' if a['ok'] else 'FALLO'})"
        if not a["ok"] and n:
            linea += (f" | correcto − tu número = {correcto - n:+g}"
                      f" | correcto / tu número = {correcto / n:.4g}")
        lineas.append(linea)
        if a.get("reflexion"):
            lineas.append(f"  Reflexión: {a['reflexion'][:400]}")
    return "\n".join(lineas)


def _marca(ok: bool) -> str:
    return "✓" if ok else "✗"


NOMBRES = {"cargo_exterior": "cargo fijo al exterior", "descuento_premium": "descuento Premium",
           "control_nacional": "control (transferencia nacional)", "control_estandar": "control (cliente estándar)"}


async def experiencia() -> list[dict]:
    """Paso 1: TRAIN sin memoria, hasta 2 intentos (fallo → reflexión → reintento)."""
    print(f"PASO 1 — EXPERIENCIA: el agente resuelve {len(TRAIN)} tareas de entrenamiento (hasta 2 intentos, sin memoria)")
    wf = crear_workflow(max_intentos=2)
    res = await correr_en_paralelo([lambda t=t: resolver_tarea(wf, t) for t in TRAIN])
    for r, t in zip(res, TRAIN):
        nums = " → ".join(f"{a['numero']:g}" if a["numero"] is not None else "?" for a in r["trayectoria"])
        veredicto = ("acertó a la primera" if r["primer_intento"]
                     else "falló, reflexionó y acertó" if r["resuelta"] else "no resuelta")
        print(f"  {t['id']}  {veredicto:<28} respuestas: {nums:<14} correcto: {t['correct_answer']:g}")
    fallaron = [r for r in res if not r["primer_intento"]]
    narrar(f"{len(fallaron)} de {len(res)} tareas fallaron al primer intento: el agente no conoce las "
           f"convenciones de la entidad. {sum(r['resuelta'] for r in fallaron)} de esas {len(fallaron)} se "
           f"resolvieron al reintentar, con el número correcto a la vista y su propia reflexión. Esa "
           f"experiencia es la materia prima que ExpeL va a destilar.")
    return res


def _describir(op: dict, banco: list[dict]) -> str:
    """Una operación del destilador, legible: «ADD  «texto»» / «AGREE regla 0»."""
    t, i = op["tipo"], op.get("id_regla")
    if t == "ADD":
        return f"ADD   «{op.get('texto', '')}»"
    if t == "EDIT":
        return f"EDIT  regla {i} → «{op.get('texto', '')}»"
    return f"{t:<5} regla {i}"


async def destilar(res: list[dict]) -> list[dict]:
    """Paso 2: una experiencia por vez; el banco evoluciona con las operaciones."""
    print("\nPASO 2 — DESTILACIÓN: un LLM convierte cada experiencia en operaciones sobre un banco de reglas")
    banco: list[dict] = []
    cuenta = {"ADD": 0, "AGREE": 0, "EDIT": 0, "REMOVE": 0}
    for r, t in zip(res, TRAIN):
        if r["primer_intento"]:
            print(f"  {t['id']}: acertó a la primera → nada que aprender")
            continue
        ops = await con_reintentos(lambda r=r, t=t: proponer_operaciones(
            banco, experiencia_como_texto(r, t), INSTRUCCION_DESTILADOR))
        previo = banco
        banco = aplicar_operaciones(banco, ops, edit_suma_voto=True)
        for o in ops:
            cuenta[o["tipo"]] += 1
            print(f"  {t['id']}: {_describir(o, previo)}")
        if not ops:
            print(f"  {t['id']}: sin cambios")
    with open(ARCHIVO_REGLAS, "w", encoding="utf-8") as f:
        json.dump(banco, f, indent=2, ensure_ascii=False)
    firmes = sum(r["votos"] >= MIN_VOTOS for r in banco)
    narrar(f"El destilador propuso {sum(cuenta.values())} operaciones ({cuenta['ADD']} ADD, {cuenta['AGREE']} AGREE, "
           f"{cuenta['EDIT']} EDIT, {cuenta['REMOVE']} REMOVE). El banco quedó con {len(banco)} regla(s), "
           f"{firmes} confirmada(s) por al menos {MIN_VOTOS} experiencias. Un voto es una experiencia que "
           f"respalda la regla; una regla con un solo voto no se inyecta.")
    return banco


def mostrar_banco(banco: list[dict]) -> None:
    print("\n  BANCO DE REGLAS")
    for r in banco:
        estado = "se inyecta" if r["votos"] >= MIN_VOTOS else f"NO se inyecta (menos de {MIN_VOTOS} votos)"
        print(f"   [{r['votos']} voto(s)] {r['texto']}\n              → {estado}")
    if not banco:
        print("   (vacío)")


def _por_categoria(base: list[dict], con: list[dict]) -> dict:
    """{categoria: (aciertos baseline, aciertos ExpeL, n)} a partir de los resultados de TEST."""
    out: dict = {}
    for i, t in enumerate(TEST):
        b = base[i * REPETICIONES_TEST:(i + 1) * REPETICIONES_TEST]
        c = con[i * REPETICIONES_TEST:(i + 1) * REPETICIONES_TEST]
        ab, ac, n = out.get(t["categoria"], (0, 0, 0))
        out[t["categoria"]] = (ab + sum(x["primer_intento"] for x in b),
                               ac + sum(x["primer_intento"] for x in c), n + len(b))
    return out


def explicar_prueba(base: list[dict], con: list[dict]) -> str:
    """Texto de «qué pasó» armado A PARTIR de los resultados: dice también cuando salió mal."""
    cat = _por_categoria(base, con)
    partes, mal = [], []
    for k, (b, c, n) in cat.items():
        if k.startswith("control"):
            continue
        veredicto = "mejoró" if c > b else "no mejoró"
        partes.append(f"en {NOMBRES[k]} pasó de {b}/{n} a {c}/{n} ({veredicto})")
        if c <= b:
            mal.append(NOMBRES[k])
    ctl = [(NOMBRES[k], b, c, n) for k, (b, c, n) in cat.items() if k.startswith("control")]
    rotos = [f"{nom} ({b}/{n} → {c}/{n})" for nom, b, c, n in ctl if c < b]
    texto = "Con las reglas: " + "; ".join(partes) + ". "
    if rotos:
        texto += ("ATENCIÓN: en " + ", ".join(rotos) + " ExpeL empeoró, o sea que una regla se aplicó donde "
                  "no correspondía. ")
    else:
        texto += "En los controles, donde ninguna convención aplica, no empeoró: las reglas no se sobre-aplicaron. "
    if mal:
        texto += ("No mejoró " + " ni ".join(mal) + ": revisá el banco, porque falta una regla correcta o hay "
                  "una espuria que el modelo aplicó.")
    return texto


async def probar(banco: list[dict]) -> dict:
    """Paso 3: TEST, 1 intento en ambas condiciones; lo único que cambia son las reglas."""
    print(f"\nPASO 3 — PRUEBA en {len(TEST)} tareas NUEVAS x {REPETICIONES_TEST} repeticiones, 1 intento, "
          "sin reglas contra con reglas")
    wf = crear_workflow(max_intentos=1)
    reglas = {"reglas": reglas_para_prompt(banco, MIN_VOTOS)}
    print(f"  Reglas inyectadas en el prompt: {sum(r['votos'] >= MIN_VOTOS for r in banco)} de {len(banco)}")
    jobs = [t for t in TEST for _ in range(REPETICIONES_TEST)]
    base, con = await asyncio.gather(
        correr_en_paralelo([lambda t=t: resolver_tarea(wf, t) for t in jobs]),
        correr_en_paralelo([lambda t=t: resolver_tarea(wf, t, reglas) for t in jobs]))

    print("\n  Por tarea (aciertos de 3 repeticiones):")
    print(f"   {'tarea':<7}{'tipo':<34}{'correcto':>9}   {'sin reglas':<12}{'con ExpeL':<10}")
    for i, t in enumerate(TEST):
        b = base[i * REPETICIONES_TEST:(i + 1) * REPETICIONES_TEST]
        c = con[i * REPETICIONES_TEST:(i + 1) * REPETICIONES_TEST]
        print(f"   {t['id']:<7}{NOMBRES[t['categoria']]:<34}{t['correct_answer']:>9g}   "
              f"{sum(x['primer_intento'] for x in b)}/{len(b):<10}{sum(x['primer_intento'] for x in c)}/{len(c)}")

    # Un ejemplo concreto: la primera tarea de TEST, primera repetición de cada condición.
    t0, b0, c0 = TEST[0], base[0], con[0]
    print(f"\n  Ejemplo — {t0['id']}: {t0['prompt'][:95]}...")
    def num(r):
        n = r["trayectoria"][0]["numero"]
        return f"{n:g}" if n is not None else "?"
    print(f"    sin reglas respondió {num(b0):>8}  {_marca(b0['primer_intento'])}   (correcto: {t0['correct_answer']:g})")
    print(f"    con ExpeL  respondió {num(c0):>8}  {_marca(c0['primer_intento'])}")

    resumen = baseline_vs_tecnica("ExpeL (reglas)", base, con, etiqueta_baseline="sin reglas")
    narrar(explicar_prueba(base, con))
    salida = {"reglas": banco, "min_votos": MIN_VOTOS, "resumen": resumen,
              "por_tarea": [{"id": t["id"], "baseline": [x["primer_intento"] for x in base[i * REPETICIONES_TEST:(i + 1) * REPETICIONES_TEST]],
                             "expel": [x["primer_intento"] for x in con[i * REPETICIONES_TEST:(i + 1) * REPETICIONES_TEST]]}
                            for i, t in enumerate(TEST)]}
    with open(ARCHIVO_RESULTADOS, "w", encoding="utf-8") as f:
        json.dump(salida, f, indent=2, ensure_ascii=False)
    return salida


async def main():
    print("EXPeL — aprender REGLAS GENERALES de la experiencia")
    print("El agente no conoce dos convenciones de la entidad (un cargo fijo al exterior y un descuento")
    print("a clientes Premium). ExpeL junta experiencia, la destila en reglas con votos y las inyecta.")
    print("(Tareas sintéticas: las convenciones están inventadas para el curso.)\n")
    if "--solo-probar" in sys.argv:
        if not os.path.exists(ARCHIVO_REGLAS):
            sys.exit(f"Falta {ARCHIVO_REGLAS}: corré primero sin --solo-probar.")
        with open(ARCHIVO_REGLAS, encoding="utf-8") as f:
            banco = json.load(f)
        print(f"Banco cargado de {ARCHIVO_REGLAS}:\n{texto_banco(banco)}")
    else:
        banco = await destilar(await experiencia())
    mostrar_banco(banco)
    await probar(banco)
    registrar_costo("expel_caso_adk2")


if __name__ == "__main__":
    if {"-h", "--help"} & set(sys.argv):
        print(__doc__)
        sys.exit(0)
    asyncio.run(main())
