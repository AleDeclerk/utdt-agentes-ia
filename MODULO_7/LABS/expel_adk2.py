"""
ExpeL en ADK2. Destila REGLAS de varias trayectorias y las transfiere.

ExpeL USA Reflexion: su materia prima es la experiencia que Reflexion ya dejó (intentos
fallidos, reflexiones, aciertos). La diferencia no es de dónde viene la experiencia sino
qué se hace con ella: Reflexion la guarda como lecciones sueltas, atadas a casos y
recuperadas por parecido; ExpeL la DESTILA en reglas generales, con votos, y las edita.

Fases:
  1. Experiencia : la de Reflexion sobre TRAIN (3 categorías x 3 tareas). Se reutiliza
                   `reflexion_resultados.json` y `memoria_reflexiones.json` si existen;
                   si no (o con --rehacer-experiencia) se corre `reflexion_adk2.aprender`.
  2. Destilación : un LlmAgent con `output_schema` propone operaciones sobre el banco
                   de reglas — AGREE / REMOVE / EDIT / ADD — una trayectoria a la vez.
                   El banco se guarda en `reglas_expel.json` (persiste entre sesiones).
  3. Transferencia: tareas NUEVAS (TEST) de las mismas categorías, baseline contra
                   ExpeL, 1 intento en ambas (sin memoria · reglas destiladas). No se
                   compara con otras técnicas.

Diferencias con el ExpeL del paper:
  - Cada regla nueva entra con 1 voto (el paper usa importancia inicial 2) y un REMOVE
    la elimina directo (el paper la baja de a uno y la borra al llegar a 0).
  - La destilación procesa UNA trayectoria a la vez, en secuencia (el banco evoluciona).

Costo (medido): ~5 min reutilizando la experiencia. La fase 2 hace 9 llamadas de
destilación en secuencia; la fase 3 corre 2 condiciones x 6 tareas x 3 repeticiones.
Si la experiencia hay que generarla (fase 1), suma ~3-4 min. Con --solo-probar se saltean
las fases 1-2 (~3 min).

Nota: este montaje (tareas de `tareas.py`, pocas lecciones) muestra el mecanismo de ExpeL
(votos, EDIT, riesgo de reglas erróneas) más que una ventaja grande; el caso pensado para
ver la mejora contra el baseline es `expel_caso_adk2.py`.

Salidas: reglas_expel.json (el banco, persistente) y expel_resultados.json.
La demo de referencia de ExpeL es expel_caso_adk2.py.

Uso:  python expel_adk2.py                          # fases 1-3 (reutiliza la experiencia)
      python expel_adk2.py --rehacer-experiencia    # vuelve a correr el aprendizaje de Reflexion
      python expel_adk2.py --solo-probar            # reutiliza reglas_expel.json (fase 3)
"""
import asyncio
import json
import os
import sys
import uuid
from typing import Literal, Optional

from google.adk import Runner
from google.adk.agents import LlmAgent
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel

from comun import (APP, ARCHIVO_MEMORIA, MODEL, MemoriaReflexiones, baseline_vs_tecnica,
                   con_reintentos, contar_uso, correr_en_paralelo, crear_workflow, narrar,
                   registrar_costo, resolver_tarea, resumen)
from reflexion_adk2 import ARCHIVO_RESULTADOS, aprender
from tareas import TEST, TRAIN

ARCHIVO_REGLAS = "reglas_expel.json"
MAX_REGLAS_INYECTADAS = 8
REPETICIONES_TEST = 3


class Operacion(BaseModel):
    """Una operación propuesta por el destilador sobre el banco de reglas."""
    tipo: Literal["AGREE", "REMOVE", "EDIT", "ADD"]
    id_regla: Optional[int] = None   # AGREE / REMOVE / EDIT
    texto: Optional[str] = None      # ADD / EDIT


class Operaciones(BaseModel):
    """`output_schema` del agente destilador: fuerza una respuesta estructurada."""
    operaciones: list[Operacion]


INSTRUCCION_DESTILADOR = """Sos el módulo de destilación de un agente financiero que aprende de su experiencia.
Mantenés un banco de reglas generales. Recibís UNA experiencia (un problema, los intentos del agente y
las reflexiones) y devolvés operaciones sobre el banco:
- AGREE id_regla: la experiencia confirma una regla existente.
- ADD texto: regla nueva, que NO esté ya en el banco.
- EDIT id_regla texto: mejora la redacción o precisión de una regla.
- REMOVE id_regla: la regla es incorrecta o contradice la experiencia.
Las reglas deben ser GENERALES (valer para toda una categoría de problemas), imperativas y sin
los números concretos de este caso. Si el agente acertó a la primera y no hay nada nuevo, devolvé una lista vacía.

BANCO ACTUAL:
{banco}

EXPERIENCIA:
{experiencia}"""


# ─── Banco de reglas (persistente) ──────────────────────────────────────────
def cargar_banco() -> list[dict]:
    """Lee el banco de reglas [{texto, votos}] de ARCHIVO_REGLAS; [] si no existe."""
    if os.path.exists(ARCHIVO_REGLAS):
        with open(ARCHIVO_REGLAS) as f:
            return json.load(f)
    return []


def guardar_banco(banco: list[dict]) -> None:
    """Persiste el banco. Es el 'archivo de largo plazo' del módulo: versionable y auditable."""
    with open(ARCHIVO_REGLAS, "w") as f:
        json.dump(banco, f, indent=2, ensure_ascii=False)


def texto_banco(banco: list[dict]) -> str:
    """Banco numerado con sus votos, tal como lo ve el destilador."""
    return "\n".join(f"[{i}] (votos={r['votos']}) {r['texto']}" for i, r in enumerate(banco)) or "(vacío)"


def aplicar_operaciones(banco: list[dict], ops: list[dict], edit_suma_voto: bool = False) -> list[dict]:
    """Aplica ADD/AGREE/EDIT/REMOVE y devuelve el banco ordenado por votos (desc).

    Es CÓDIGO determinista, no el modelo: el modelo solo propone. Ignora ids fuera de
    rango o ya eliminados, y operaciones sin texto (defensa ante salidas raras).
    Con `edit_suma_voto`, un EDIT también cuenta como confirmación: la experiencia respaldó
    la regla al punto de precisarla (decisión de diseño de `expel_caso_adk2.py`)."""
    quitar = set()
    for op in ops:
        i = op.get("id_regla")
        existe = i is not None and 0 <= i < len(banco) and i not in quitar
        if op["tipo"] == "ADD" and op.get("texto"):
            banco.append({"texto": op["texto"], "votos": 1})
        elif op["tipo"] == "AGREE" and existe:
            banco[i]["votos"] += 1
        elif op["tipo"] == "EDIT" and existe and op.get("texto"):
            banco[i]["texto"] = op["texto"]
            if edit_suma_voto:
                banco[i]["votos"] += 1
        elif op["tipo"] == "REMOVE" and existe:
            quitar.add(i)
    banco = [r for k, r in enumerate(banco) if k not in quitar]
    return sorted(banco, key=lambda r: -r["votos"])


def reglas_para_prompt(banco: list[dict], min_votos: int = 1) -> str:
    """Las MAX_REGLAS_INYECTADAS reglas con más votos (y al menos `min_votos`), como bloque
    para `{reglas?}`. Con `min_votos` > 1 una regla con un solo voto no llega al prompt."""
    top = [r for r in banco if r["votos"] >= min_votos][:MAX_REGLAS_INYECTADAS]
    if not top:
        return ""
    return "Reglas de la entidad aprendidas de experiencia previa (aplicalas):\n" + "\n".join(
        f"- {r['texto']}" for r in top)


# ─── Destilación ────────────────────────────────────────────────────────────
def experiencia_como_texto(res: dict, tarea: dict) -> str:
    """Resume una trayectoria (intentos, resultado, reflexiones) para el destilador."""
    lineas = [f"Problema: {tarea['prompt']}", f"Resultado: {'resuelto' if res['resuelta'] else 'NO resuelto'} "
              f"en {res['intentos']} intento(s). Número correcto: {tarea['correct_answer']}."]
    for a in res["trayectoria"]:
        lineas.append(f"- Intento {a['intento']}: número={a['numero']} ({'OK' if a['ok'] else 'FALLO'})")
        if a.get("reflexion"):
            lineas.append(f"  Reflexión: {a['reflexion'][:600]}")
    return "\n".join(lineas)


async def proponer_operaciones(banco: list[dict], experiencia: str,
                               instruccion: str = INSTRUCCION_DESTILADOR) -> list[dict]:
    """Una llamada al destilador: (banco actual, UNA experiencia) -> lista de operaciones.
    `instruccion` permite a otros casos (expel_caso_adk2.py) usar su propio prompt; debe
    contener las plantillas {banco} y {experiencia}."""
    agente = LlmAgent(name="destilador", model=MODEL, include_contents="none",
                      output_schema=Operaciones, output_key="ops", instruction=instruccion,
                      after_model_callback=contar_uso)
    svc = InMemorySessionService()
    sid = uuid.uuid4().hex[:8]
    await svc.create_session(app_name=APP, user_id="u", session_id=sid,
                             state={"banco": texto_banco(banco), "experiencia": experiencia})
    runner = Runner(agent=agente, app_name=APP, session_service=svc)
    msg = types.Content(role="user", parts=[types.Part(text="Proponé las operaciones.")])
    async for _ in runner.run_async(user_id="u", session_id=sid, new_message=msg):
        pass
    s = (await svc.get_session(app_name=APP, user_id="u", session_id=sid)).state
    ops = s.get("ops") or {}
    return ops.get("operaciones", []) if isinstance(ops, dict) else []


async def obtener_experiencia(rehacer: bool) -> list[dict]:
    """Fase 1: la experiencia de Reflexion sobre TRAIN. La reutiliza del archivo que dejó
    `reflexion_adk2.py` (así ExpeL consume literalmente lo que Reflexion aprendió) o, si
    no existe o se pidió `rehacer`, corre la pasada de aprendizaje de Reflexion."""
    if not rehacer and os.path.exists(ARCHIVO_RESULTADOS):
        with open(ARCHIVO_RESULTADOS, encoding="utf-8") as f:
            previa = json.load(f).get("entrenamiento")
        if previa:
            print(f"  reutilizando la experiencia de {ARCHIVO_RESULTADOS} ({len(previa)} tareas)")
            return previa
    print("  corriendo la pasada de aprendizaje de Reflexion (reflexion_adk2.aprender)")
    memoria = MemoriaReflexiones(ARCHIVO_MEMORIA, cargar=False)
    res = await aprender(memoria)
    with open(ARCHIVO_RESULTADOS, "w", encoding="utf-8") as f:
        json.dump({"entrenamiento": res}, f, indent=2, ensure_ascii=False)
    return res


async def fase_destilacion(rehacer: bool = False) -> list[dict]:
    """Fases 1 y 2: experiencia de Reflexion sobre TRAIN y destilación secuencial del
    banco de reglas."""
    print("FASE 1 — experiencia (la de Reflexion sobre TRAIN)")
    res = await obtener_experiencia(rehacer)
    por_id = {r["id"]: r for r in res}
    res = [por_id[t["id"]] for t in TRAIN]
    print(f"  {sum(r['resuelta'] for r in res)}/{len(res)} resueltas, "
          f"{sum(r['primer_intento'] for r in res)} al primer intento")
    print("FASE 2 — destilación de reglas (AGREE / ADD / EDIT / REMOVE)")
    banco: list[dict] = []
    for r, t in zip(res, TRAIN):
        ops = await con_reintentos(
            lambda r=r, t=t: proponer_operaciones(banco, experiencia_como_texto(r, t)))
        banco = aplicar_operaciones(banco, ops)
        print(f"  {t['id']}: {[o['tipo'] for o in ops] or 'sin cambios'} → {len(banco)} reglas")
    guardar_banco(banco)
    return banco


# ─── Transferencia ──────────────────────────────────────────────────────────
async def fase_transferencia(banco: list[dict]) -> list[dict]:
    """Fase 3: baseline (sin memoria) contra ExpeL (reglas destiladas) sobre tareas
    NUEVAS (TEST), un intento en ambas condiciones."""
    print(f"\nFASE 3 — transferencia a tareas NUEVAS ({len(TEST)} x {REPETICIONES_TEST} repeticiones, 1 intento)")
    print("Banco de reglas (cargado de reglas_expel.json) — generales, sin números de un caso:")
    for r in banco:
        print(f"  (votos={r['votos']}) {r['texto']}")
    wf = crear_workflow(1)
    estado_reglas = {"reglas": reglas_para_prompt(banco)}
    trabajos = {
        "sin memoria (baseline)": [lambda t=t: resolver_tarea(wf, t) for t in TEST for _ in range(REPETICIONES_TEST)],
        "ExpeL (reglas)": [lambda t=t: resolver_tarea(wf, t, estado_reglas) for t in TEST for _ in range(REPETICIONES_TEST)],
    }
    resultados = await asyncio.gather(*[correr_en_paralelo(v) for v in trabajos.values()])
    print("\nRESULTADOS")
    out = [resumen(n, r) for n, r in zip(trabajos, resultados)]
    out.append(baseline_vs_tecnica("ExpeL (reglas)", resultados[0], resultados[1], etiqueta_baseline="sin reglas"))
    a = sum(r["primer_intento"] for r in resultados[0])
    b = sum(r["primer_intento"] for r in resultados[1])
    narrar(f"Variante sobre las tareas originales (redondeo, IVA, punitorio), con las reglas destiladas de la "
           f"experiencia de Reflexion. Sin reglas el agente acertó {a} de {len(resultados[0])} al primer intento; "
           f"con las {len(banco)} regla(s) del banco, {b} de {len(resultados[1])}. "
           + ("Las reglas ayudaron, pero revisá el banco: una regla que contradiga la convención se aplica a "
              "toda la familia." if b > a else
              "Las reglas no mejoraron el primer intento: leé el banco, porque con poca experiencia el "
              "destilador puede escribir reglas flojas o erróneas.")
           + " La demo de referencia de ExpeL es expel_caso_adk2.py.")
    with open("expel_resultados.json", "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    return out


async def main():
    """Con --solo-probar reutiliza el banco guardado; si no, lo destila de cero."""
    if "--solo-probar" in sys.argv:
        banco = cargar_banco()
    else:
        banco = await fase_destilacion("--rehacer-experiencia" in sys.argv)
    await fase_transferencia(banco)
    registrar_costo("expel_adk2")


if __name__ == "__main__":
    if {"-h", "--help"} & set(sys.argv):
        print(__doc__)
        sys.exit(0)
    asyncio.run(main())
