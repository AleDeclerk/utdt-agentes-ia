"""Memory Bank (réplica del patrón) con Gemini, PERSISTENTE EN DISCO: extracción de hechos + consolidación, en dos procesos.

══════════════════════════════════════════════════════════════════════════════════════════
 LA IDEA, EN UNA FRASE
══════════════════════════════════════════════════════════════════════════════════════════
  Un agente conversa con un usuario; un servicio de memoria extrae HECHOS de esas conversaciones («Textil Norte evalúa
  una línea a 18 meses»), los consolida cuando algo se corrige y los guarda en disco. En un segundo proceso, que
  arranca sin nada en memoria, se comprueba que el agente recuerda y que se puede borrar de verdad.

══════════════════════════════════════════════════════════════════════════════════════════
 QUÉ PASA, EN DOS FASES (cada una es un proceso distinto: eso es lo que prueba la persistencia)
══════════════════════════════════════════════════════════════════════════════════════════
  FASE 1 · `guardar`
    1. Sesión 1: el usuario 44 conversa con el agente. Al cerrarla, Gemini extrae hechos y se guardan.
    2. Sesión 2: el mismo usuario CORRIGE un dato («18 meses, no 24»). El hecho viejo pasa al historial y queda uno vigente.
    3. Otro usuario (51) conversa sobre otro cliente: sirve para probar el aislamiento después.
  FASE 2 · `recordar` (proceso NUEVO)
    4. Lee de disco lo que quedó guardado (hechos, historial y sesiones).
    5. Busca en la memoria y comprueba que cada usuario ve solo lo suyo.
    6. Una sesión nueva con el agente: la memoria le inyecta los hechos y contesta con el dato corregido.
    7. Derecho al olvido: borra todo lo del usuario 44 (hechos, sesiones y rastros en los archivos).

══════════════════════════════════════════════════════════════════════════════════════════
 LAS PIEZAS
══════════════════════════════════════════════════════════════════════════════════════════
  El LLM que extrae hechos y decide cómo consolidarlos es Gemini (vía `gemini_backend.py`); la lógica de consolidación
  y el almacenamiento están en `servicios_memoria.py`. El agente que conversa y el agente final también usan Gemini.

  Servicios de ADK que usa (la misma pareja que `memoria_faiss.py`, pero con otra memoria):
    - `DatabaseSessionService`  → las SESIONES (las conversaciones) en SQLite, en disco: `datos_memory_bank/sesiones.db`.
    - `LocalMemoryBankService`  → la MEMORIA DE LARGO PLAZO, subclase de `BaseMemoryService`: hechos con versiones, en SQLite en disco:
                                  `datos_memory_bank/memory_bank.db`. Guarda hechos consolidados, no turnos crudos.

  Las sesiones 1 y 2 y la del otro usuario son CONVERSACIONES REALES: cada mensaje del usuario pasa por el agente y el SessionService guarda los eventos;
  al cerrarlas se las pasa a `add_session_to_memory`. Por eso el contenido varía entre corridas (tras la sesión 1, Gemini suele extraer de 3 a 5 hechos).

  El servicio administrado «Memory Bank» de Google Cloud exige un Agent Engine y no corre en tu máquina: esto es una **réplica del patrón**,
  no el servicio.

══════════════════════════════════════════════════════════════════════════════════════════
 MAPA DEL ARCHIVO
══════════════════════════════════════════════════════════════════════════════════════════
  PARTE 1  Imports y configuración
  PARTE 2  Los mensajes de la demo
  PARTE 3  Piezas de apoyo (captura de lo que recibe el modelo, servicios, agente, conversación)
  PARTE 4  Funciones para mostrar resultados
  PARTE 5  FASE 1 · `guardar`
  PARTE 6  FASE 2 · `recordar`
  PARTE 7  `reset` y programa principal (los subcomandos)

══════════════════════════════════════════════════════════════════════════════════════════
 USO
══════════════════════════════════════════════════════════════════════════════════════════
Subcomandos (cada uno es un proceso distinto: eso es lo que prueba la persistencia):
    python memory_bank.py reset      borra las dos bases de datos de esta demo
    python memory_bank.py guardar    "Semana 1": conversa (sesiones 1, 2 y la del otro usuario) y consolida hechos       → verificaciones A y B
    python memory_bank.py recordar   proceso NUEVO: lee lo guardado, busca, pregunta al agente y ejerce el derecho al olvido → P, C, D, E y F
    python memory_bank.py todo       reset + guardar + recordar, cada uno en su propio proceso (por defecto)

Verificaciones (el resultado depende de lo que Gemini extraiga y decida):
  A  la sesión 1 produce un hecho vigente con «24 meses»                                                        (en `guardar`)
  B  después de la corrección (sesión 2) hay UN hecho vigente sobre el plazo, con «18 meses», y el de «24» quedó como historial   (en `guardar`)
  P  un proceso NUEVO recupera de disco los hechos con la corrección ya consolidada y las dos sesiones del usuario 44   (sin modelo)
  C  la búsqueda por «plazo» devuelve primero el hecho de 18 meses
  D  otro usuario no ve nada de este (aislamiento) y un usuario sin memoria recibe una lista vacía
  E  una sesión NUEVA con el agente (PreloadMemoryTool + Gemini) contesta con el plazo corregido; se captura y se imprime lo que Gemini recibió
  F  derecho al olvido: se borran los hechos Y las sesiones del usuario 44, no se toca al 51, y «Textil Norte» ya no figura en los bytes de ningún archivo
     (SQLite deja las filas borradas en páginas libres hasta un `VACUUM`: por eso se compacta antes de comprobarlo)

Sobre los umbrales de consolidación (`SIM_DUPLICADO=0.985`, `SIM_MISMO_TEMA=0.55`): con el modelo de embeddings de la demo, «24 meses» contra
«18 meses» da 0.936 si la redacción es casi idéntica (solo cambia el número) y 0.889 si es distinta: los dos caen entre los umbrales, así que la
corrección no se descarta como duplicado ni se trata como un tema distinto. Lo que queda abierto es lo que Gemini **decida** al consolidar
(`actualizar` o `agregar`) y cómo redacte los hechos; si B falla, es un resultado de la demo, no un error.

Necesita `GOOGLE_API_KEY` (ver `.env.example`). Los datos de la demo son ficticios y quedan en `datos_memory_bank/` (no se versiona; `reset` y la
verificación F los limpian). Códigos de salida: 0 = verificaciones OK · 1 = alguna verificación falló (es un resultado de la demo) · 2 = error de
ejecución (cuota, red, credenciales…; se imprime el traceback).
Sin `reset` previo, `recordar` por sí solo falla si ya se ejerció el derecho al olvido: `todo` siempre empieza con `reset`.
"""
# ══════════════════════════════════════════════════════════════════════════════
# PARTE 1 · IMPORTS Y CONFIGURACIÓN
#   Se cargan las variables del `.env`, se crea el LLM de extracción (Gemini) y se definen
#   dónde se guardan los datos y quiénes son los usuarios de la demo.
# ══════════════════════════════════════════════════════════════════════════════
import asyncio
import os
import pathlib
import sqlite3
import subprocess
import sys
import uuid

from dotenv import load_dotenv

load_dotenv()

from google.adk import Agent, Runner  # Agent: el agente · Runner: lo que lo ejecuta junto con las sesiones y la memoria
from google.adk.sessions import DatabaseSessionService, Session  # sesiones guardadas en una base de datos
from google.adk.tools.preload_memory_tool import PreloadMemoryTool  # herramienta que, ANTES de cada llamada al modelo, busca en la memoria
from google.genai.types import AutomaticFunctionCallingConfig, Content, GenerateContentConfig, Part  # tipos de mensaje y de configuración de Gemini

import gemini_backend  # el LLM que extrae los hechos y decide cómo consolidarlos
from adk_util import con_reintentos_async  # reintenta ante cuota (429) o cortes de red
from servicios_memoria import LocalMemoryBankService  # el servicio de memoria con hechos, versiones y consolidación

MODELO = os.environ.get("DEMO_MODEL", "gemini-2.5-flash")
GEMINI = gemini_backend.GeminiBackend(MODELO)  # el LLM de extracción y consolidación (cuenta llamadas y tokens)

DATOS = pathlib.Path(__file__).resolve().parent / "datos_memory_bank"  # no se versiona
DB_SESIONES, DB_MEMORIA = DATOS / "sesiones.db", DATOS / "memory_bank.db"  # una base para las conversaciones y otra para los hechos
APP = "asistente_normativa"  # nombre de la aplicación: junto con el usuario, identifica a quién pertenece cada dato
U44, U51, U99 = "oficial_cuentas_44", "oficial_cuentas_51", "oficial_cuentas_99"  # 44 y 51 conversan; 99 nunca habla (para probar el aislamiento)

# ══════════════════════════════════════════════════════════════════════════════
# PARTE 2 · LOS MENSAJES DE LA DEMO
#   Solo los mensajes del USUARIO: las respuestas las genera el agente en una conversación real.
# ══════════════════════════════════════════════════════════════════════════════
# Solo los mensajes del USUARIO: las respuestas las genera el agente (Gemini) en una conversación real sobre un SessionService.
MENSAJES_S1 = [  # sesión 1 del usuario 44: presenta el caso (cliente, exposición, plazo de 24 meses y una preferencia)
    "Hola, consulto por Textil Norte S.A., banca corporativa. Hoy tienen 3.4 millones de dólares de exposición.",
    "Estoy evaluando una línea de capital de trabajo a 24 meses para ese cliente.",
    "Prefiero que las respuestas me lleguen siempre en millones de dólares y citando la fuente.",
]
MENSAJES_S2 = [  # sesión 2 del usuario 44: CORRIGE el plazo (de 24 a 18 meses) y agrega un dato independiente
    "Volvimos sobre Textil Norte S.A. Corrección: el plazo de la línea de capital de trabajo es de 18 meses, no de 24.",
    "Además, el dictamen de la Gerencia de Riesgos se emitió el 10 de julio.",
]
MENSAJES_OTRO_USUARIO = [  # sesión del usuario 51: otro cliente, para comprobar que no se mezclan los datos
    "Consulto por Frigorífico Pampa S.R.L.: quiero un leasing sobre maquinaria a 84 meses.",
]
PREGUNTA = "¿A qué plazo evaluamos la línea de capital de trabajo de Textil Norte?"  # la que se hace en la sesión nueva (fase 2)


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 3 · PIEZAS DE APOYO
#   Captura de lo que recibe el modelo, creación de los servicios, el agente que conversa y la
#   función que corre una conversación.
# ══════════════════════════════════════════════════════════════════════════════
CAPTURA = {"peticion": ""}  # acá se guarda, para mostrarlo, el texto que recibió el modelo en su última llamada


def capturar_system(callback_context, llm_request):
    """before_model_callback: guarda el texto que recibe el modelo (system instruction y contenidos). PreloadMemoryTool inyecta los
    recuerdos como contenido de usuario transitorio (ADK 2.10) o en la system instruction (versiones anteriores): se capturan los dos lugares.

    ADK llama a esta función justo antes de cada llamada al modelo. Sirve para MOSTRAR qué recuerdos le llegaron a Gemini. Devuelve
    `None` para no reemplazar la respuesta del modelo (el modelo corre normalmente).
    """
    si = llm_request.config.system_instruction if llm_request.config else None
    sistema = si if isinstance(si, str) else "" if si is None else "\n".join(p.text for p in (si.parts or []) if p.text)
    contenidos = "\n".join(p.text for c in (llm_request.contents or []) for p in (c.parts or []) if p.text)
    CAPTURA["peticion"] = sistema + "\n" + contenidos
    return None  # no reemplaza la respuesta: el modelo corre normalmente


def servicios() -> tuple[DatabaseSessionService, LocalMemoryBankService]:
    """Crea los dos servicios que guardan datos en disco y los devuelve: (servicio de sesiones, servicio de memoria).

    - `DatabaseSessionService` guarda las CONVERSACIONES en `sesiones.db`.
    - `LocalMemoryBankService` guarda los HECHOS (con versiones e historial) en `memory_bank.db`.
    Crea la carpeta de datos si no existe. Si los archivos ya existían, los usa: así un proceso nuevo recupera lo guardado.
    """
    DATOS.mkdir(exist_ok=True)
    return DatabaseSessionService(f"sqlite+aiosqlite:///{DB_SESIONES}"), LocalMemoryBankService(str(DB_MEMORIA), GEMINI.chat_json)


def agente_conversacional() -> Agent:
    """El agente que conversa en las sesiones 1 y 2. Tiene PreloadMemoryTool, como en producción: en la sesión 2 ya ve los hechos de la 1.

    Contesta en una oración y con temperatura 0 (respuestas lo más estables posible). `PreloadMemoryTool` no la llama el modelo:
    ADK la ejecuta solo, antes de cada llamada, busca en la memoria con el mensaje del usuario y le pasa lo encontrado.
    """
    return Agent(name="asistente_de_normativa", model=MODELO, tools=[PreloadMemoryTool()],
                 instruction="Sos un asistente de normativa interna para oficiales de una entidad financiera. Respondé en UNA oración. "
                             "No inventes normas ni datos que el usuario no te dio.",
                 # La llamada automática a funciones del SDK (AFC) viene activada por defecto y avisa por log aunque acá no se use: las
                 # herramientas las ejecuta ADK, no el SDK. Se desactiva explícitamente; no cambia lo que se le manda al modelo.
                 generate_content_config=GenerateContentConfig(
                     temperature=0.0, automatic_function_calling=AutomaticFunctionCallingConfig(disable=True)))


async def conversar(runner: Runner, ses: DatabaseSessionService, user_id: str, sid: str, mensajes: list[str]) -> Session:
    """Conversación real: cada mensaje del usuario pasa por el agente y el SessionService guarda los eventos. Devuelve la sesión cerrada.

    Parámetros:
      runner    el `Runner` que ejecuta el agente.
      ses       el servicio de sesiones donde se guarda la conversación.
      user_id   a qué usuario pertenece la sesión.
      sid       identificador de la sesión (por ejemplo «s1»).
      mensajes  los mensajes del usuario, en orden.
    Para cada mensaje: se lo envía al agente, se imprime «Usuario / Agente» y se pasa al siguiente. Al terminar se devuelve la sesión
    ya cerrada (con todos los eventos), lista para entregársela a la memoria con `add_session_to_memory`.
    """
    await ses.create_session(app_name=APP, user_id=user_id, session_id=sid)
    for m in mensajes:
        async def turno() -> str:
            """Un turno de conversación: envía el mensaje `m` al agente y devuelve el texto de su respuesta final."""
            texto = ""
            async for ev in runner.run_async(user_id=user_id, session_id=sid, new_message=Content(role="user", parts=[Part(text=m)])):
                if ev.is_final_response() and ev.content and ev.content.parts:
                    texto = ev.content.parts[0].text
            return texto
        print(f"    Usuario: {m}\n    Agente:  {await con_reintentos_async(turno, 'agente (memory_bank)')}")  # con reintentos ante 429 o red
    return await ses.get_session(app_name=APP, user_id=user_id, session_id=sid)


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 4 · FUNCIONES PARA MOSTRAR RESULTADOS
#   Solo imprimen: no deciden nada.
# ══════════════════════════════════════════════════════════════════════════════
def mostrar(mem: LocalMemoryBankService, usuario: str, titulo: str, historial: bool = False) -> None:
    """Imprime los hechos guardados de un usuario, con su número, versión y si siguen vigentes.

    Con `historial=True` incluye también los hechos que fueron REEMPLAZADOS por una corrección (marcados «REEMPLAZADO»).
    Un hecho nuevo que corrige a uno anterior muestra «(reemplaza al #N)».
    """
    print(f"  {titulo}")
    for h in mem.listar(APP, usuario, historial=historial):
        marca = "vigente " if h["vigente"] else "REEMPLAZADO"
        rem = f" (reemplaza al #{h['reemplaza']})" if h["reemplaza"] else ""
        print(f"    #{h['id']} v{h['version']} [{marca}] {h['hecho']}{rem}")


def trazar(mem: LocalMemoryBankService, desde: int) -> None:
    """Imprime las decisiones de consolidación tomadas desde la posición `desde` de la traza del servicio.

    Cada línea dice qué se hizo con un hecho (AGREGAR, ACTUALIZAR o IGNORAR), con qué similitud respecto del hecho más parecido
    que ya existía, y el texto del hecho. `mem.traza` es la lista de decisiones de este proceso.
    """
    for t in mem.traza[desde:]:
        print(f"    consolidación → {t['accion'].upper():10} (similitud {t.get('similitud', '-')}) {t['hecho'] or ''}")


def resumir(resultados: dict[str, bool]) -> int:
    """Imprime el cuadro final de verificaciones ([OK] / [FALLA]) y el uso de Gemini. Devuelve el código de salida del proceso.

    Devuelve 0 si TODAS las verificaciones pasaron y 1 si alguna falló (un resultado de la demo, no un error de ejecución).
    """
    print("\n" + "=" * 70)
    for k, v in resultados.items():
        print(f"  [{'OK' if v else 'FALLA'}] {k}")
    print(GEMINI.resumen())
    return 0 if all(resultados.values()) else 1


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 5 · FASE 1 · `guardar`  («Semana 1»)
#   Conversa, extrae hechos, consolida la corrección y deja todo en disco.
# ══════════════════════════════════════════════════════════════════════════════
async def guardar() -> int:
    """Fase 1: tres conversaciones reales que terminan guardadas en disco. Devuelve 0 si pasaron las verificaciones A y B, y 1 si no.

    Pasos: (1) crear servicios y runner; (2) sesión 1 y verificación A; (3) sesión 2, la corrección, y verificación B;
    (4) conversación del otro usuario; (5) resumen.
    Cada vez que una sesión termina se la entrega a la memoria con `add_session_to_memory`: ahí Gemini extrae los hechos y el
    servicio decide, hecho por hecho, si los AGREGA, ACTUALIZA o IGNORA.
    """
    # ── Paso 1 · Servicios (sesiones y memoria en disco) y el `Runner` que ejecuta al agente con ambos. ──
    ses, mem = servicios()
    runner_conv = Runner(agent=agente_conversacional(), app_name=APP, session_service=ses, memory_service=mem)
    resultados: dict[str, bool] = {}  # verificación → pasó o no

    # ── Paso 2 · Sesión 1: conversación real; al cerrarla, Gemini extrae hechos. ──
    print("== Sesión 1 (oficial_cuentas_44): conversación real; al cerrarla, Gemini extrae hechos ==")
    s1 = await conversar(runner_conv, ses, U44, "s1", MENSAJES_S1)
    await mem.add_session_to_memory(s1)  # extracción de hechos (Gemini) + consolidación (el servicio) + guardado en disco
    trazar(mem, 0)
    mostrar(mem, U44, "hechos vigentes tras la sesión 1:")
    resultados["A  la sesión 1 produce un hecho con «24 meses»"] = any("24 meses" in h["hecho"] for h in mem.listar(APP, U44))

    # ── Paso 3 · Sesión 2: el usuario corrige el plazo. El hecho viejo debe pasar al historial. ──
    print("\n== Sesión 2 (mismo usuario): corrige el plazo ==")
    n0 = len(mem.traza)  # cuántas decisiones había antes de la sesión 2, para imprimir solo las nuevas
    s2 = await conversar(runner_conv, ses, U44, "s2", MENSAJES_S2)
    await mem.add_session_to_memory(s2)
    trazar(mem, n0)
    mostrar(mem, U44, "hechos vigentes tras la corrección:")
    mostrar(mem, U44, "historial completo (incluye lo reemplazado):", historial=True)
    # Verificación B: debe haber UN solo hecho vigente sobre el plazo (con «18 meses») y el de «24 meses» en el historial.
    sobre_plazo = [h for h in mem.listar(APP, U44) if "capital de trabajo" in h["hecho"].lower() or "plazo" in h["hecho"].lower()]
    reemplazados = [h for h in mem.listar(APP, U44, historial=True) if not h["vigente"] and "24 meses" in h["hecho"]]
    resultados["B  un solo hecho vigente sobre el plazo, con «18 meses», y el de «24» quedó como historial"] = (
        len(sobre_plazo) == 1 and "18 meses" in sobre_plazo[0]["hecho"] and "24 meses" not in sobre_plazo[0]["hecho"]
        and len(reemplazados) == 1)

    # ── Paso 4 · Otro usuario: conversa sobre otro cliente. Se usa después para probar el aislamiento. ──
    print("\n== Otro usuario (oficial_cuentas_51) ==")
    s3 = await conversar(runner_conv, ses, U51, "s3", MENSAJES_OTRO_USUARIO)
    await mem.add_session_to_memory(s3)
    mostrar(mem, U51, "hechos de oficial_cuentas_51:")

    # ── Paso 5 · Resumen: todo queda en disco para que lo lea el proceso siguiente. ──
    print(f"\nGuardado en disco: {len(mem.listar(APP, U44, historial=True))} hechos de 44 (con historial), "
          f"{len(mem.listar(APP, U51, historial=True))} de 51, y 3 sesiones en {DATOS.name}/.")
    return resumir(resultados)


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 6 · FASE 2 · `recordar`  (un proceso NUEVO, sin nada en memoria)
#   Lee lo guardado, busca, le pregunta al agente y ejerce el derecho al olvido.
# ══════════════════════════════════════════════════════════════════════════════
def _compactar(*archivos: pathlib.Path) -> None:
    """SQLite marca las filas borradas como libres pero no las sobrescribe hasta un VACUUM.

    Ejecuta `VACUUM` sobre cada archivo para que el texto borrado deje de estar físicamente en el disco.
    """
    for a in archivos:
        con = sqlite3.connect(a)
        con.execute("VACUUM")
        con.close()


async def recordar() -> int:
    """Fase 2, en un proceso NUEVO: comprueba que lo guardado sobrevivió y luego lo borra. Devuelve 0 si pasaron P, C, D, E y F, y 1 si no.

    Pasos: (1) leer de disco y verificar P; (2) búsqueda y aislamiento, verificaciones C y D; (3) sesión nueva con el agente,
    verificación E; (4) derecho al olvido, verificación F; (5) resumen.
    """
    ses, mem = servicios()  # abre los MISMOS archivos que dejó la fase 1: no hay nada en memoria del programa
    resultados: dict[str, bool] = {}

    # ── Paso 1 · Lo que quedó en disco (sin usar el modelo). Verificación P. ──
    print("== Proceso NUEVO: lo que quedó guardado en disco ==")
    mostrar(mem, U44, "hechos vigentes de oficial_cuentas_44:")
    mostrar(mem, U44, "historial completo (incluye lo reemplazado):", historial=True)
    sesiones44 = (await ses.list_sessions(app_name=APP, user_id=U44)).sessions
    print(f"  sesiones de oficial_cuentas_44 en `sesiones.db`: {sorted(s.id for s in sesiones44)}")
    vig = [h for h in mem.listar(APP, U44) if "capital de trabajo" in h["hecho"].lower() or "plazo" in h["hecho"].lower()]
    hist24 = [h for h in mem.listar(APP, U44, historial=True) if not h["vigente"] and "24 meses" in h["hecho"]]
    resultados["P  un proceso NUEVO recupera de disco los hechos (corrección ya consolidada: 18 vigente, 24 en el historial) y las 2 sesiones de 44"] = (
        len(vig) == 1 and "18 meses" in vig[0]["hecho"] and len(hist24) == 1 and len(sesiones44) == 2)

    # ── Paso 2 · Búsqueda en la memoria y aislamiento entre usuarios. Verificaciones C y D. ──
    print("\n== Búsqueda y aislamiento ==")
    r = await mem.search_memory(app_name=APP, user_id=U44, query="plazo de la línea de capital de trabajo")
    for m in r.memories:
        print(f"    oficial_44 · score={m.custom_metadata['score']:.3f} v{m.custom_metadata['version']}: {m.content.parts[0].text}")
    resultados["C  la búsqueda por «plazo» devuelve primero el hecho de 18 meses"] = (
        bool(r.memories) and "18 meses" in r.memories[0].content.parts[0].text)
    r51 = await mem.search_memory(app_name=APP, user_id=U51, query="Textil Norte plazo de la línea")  # el usuario 51 busca datos del 44
    r99 = await mem.search_memory(app_name=APP, user_id=U99, query="Textil Norte")  # un usuario que nunca habló
    fuga = any("Textil Norte" in m.content.parts[0].text for m in r51.memories)  # ¿el 51 llegó a ver algo del 44?
    print(f"    oficial_51 buscando «Textil Norte»: {len(r51.memories)} resultados, fuga={fuga} | oficial_99: {len(r99.memories)} resultados")
    resultados["D  aislamiento entre usuarios y lista vacía sin memoria"] = (not fuga) and len(r99.memories) == 0

    # ── Paso 3 · Sesión nueva con el agente: la memoria le inyecta los hechos y debe contestar con el plazo corregido. Verificación E. ──
    print(f"\n== Sesión NUEVA con el agente (PreloadMemoryTool + Gemini): «{PREGUNTA}» ==")
    agente = Agent(name="asistente_de_normativa", model=MODELO, before_model_callback=capturar_system,
                   instruction="Sos un asistente para oficiales de una entidad financiera. Respondé en UNA oración. "
                               "Si no tenés información previa, decilo.", tools=[PreloadMemoryTool()],
                   # temperatura 0: respuesta lo más estable posible entre corridas · AFC desactivado (ver `agente_conversacional`)
                   generate_content_config=GenerateContentConfig(
                       temperature=0.0, automatic_function_calling=AutomaticFunctionCallingConfig(disable=True)))
    runner = Runner(agent=agente, app_name=APP, session_service=ses, memory_service=mem)

    async def preguntar() -> str:
        """Hace la pregunta en una sesión nueva y vacía del usuario 44 y devuelve la respuesta final del agente."""
        sid = f"dia2_{uuid.uuid4().hex[:8]}"  # sesión nueva en cada intento: un reintento no deja mensajes repetidos
        await ses.create_session(app_name=APP, user_id=U44, session_id=sid)
        texto = ""
        async for ev in runner.run_async(user_id=U44, session_id=sid, new_message=Content(role="user", parts=[Part(text=PREGUNTA)])):
            if ev.is_final_response() and ev.content and ev.content.parts:
                texto = ev.content.parts[0].text
        return texto

    respuesta = await con_reintentos_async(preguntar, "agente (memory_bank)")
    inyectado = "<PAST_CONVERSATIONS>" in CAPTURA["peticion"]  # PreloadMemoryTool envuelve los recuerdos en esta etiqueta
    print(f"    hechos inyectados en la petición al modelo: {'sí' if inyectado else 'NO'}")
    if inyectado:
        bloque = CAPTURA["peticion"].split("<PAST_CONVERSATIONS>")[1].split("</PAST_CONVERSATIONS>")[0].strip()
        print("    lo que Gemini recibió como recuerdos:")
        for linea in bloque.splitlines():
            print(f"      {linea}")
    print(f"    respuesta: {respuesta}")
    resultados["E  la respuesta usa el plazo corregido (18) y no el viejo (24)"] = inyectado and "18" in respuesta and "24" not in respuesta

    # ── Paso 4 · Derecho al olvido: borrar hechos y sesiones del usuario 44, compactar y buscar rastros. Verificación F. ──
    print("\n== Derecho al olvido (hechos, sesiones y archivos) ==")
    n = mem.borrar_usuario(APP, U44)  # borra todos los hechos del usuario 44 (vigentes e historial); devuelve cuántos
    for s in (await ses.list_sessions(app_name=APP, user_id=U44)).sessions:  # incluye la sesión que acaba de crear el agente
        await ses.delete_session(app_name=APP, user_id=U44, session_id=s.id)
    _compactar(DB_MEMORIA, DB_SESIONES)  # sin esto, el texto borrado seguiría dentro de los archivos
    quedan_hechos_44 = len(mem.listar(APP, U44, historial=True))
    quedan_hechos_51 = len(mem.listar(APP, U51, historial=True))
    quedan_ses_44 = len((await ses.list_sessions(app_name=APP, user_id=U44)).sessions)
    quedan_ses_51 = len((await ses.list_sessions(app_name=APP, user_id=U51)).sessions)
    rastro = {a.name: b"Textil Norte" in a.read_bytes() for a in (DB_MEMORIA, DB_SESIONES)}  # ¿el texto sigue en los bytes del archivo?
    print(f"    borrar_usuario({U44}) → {n} hechos eliminados; quedan {quedan_hechos_44} hechos y {quedan_ses_44} sesiones de 44 | "
          f"{quedan_hechos_51} hechos y {quedan_ses_51} sesiones de 51")
    print(f"    ¿«Textil Norte» en los bytes del archivo tras compactar? {rastro}")
    resultados["F  se borran hechos y sesiones del usuario 44, no se toca al 51, y «Textil Norte» no queda en ningún archivo"] = (
        quedan_hechos_44 == 0 and quedan_ses_44 == 0 and quedan_hechos_51 > 0 and quedan_ses_51 > 0 and not any(rastro.values()))
    # ── Paso 5 · Resumen de verificaciones. ──
    return resumir(resultados)


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 7 · `reset` Y PROGRAMA PRINCIPAL
#   El programa principal reparte los subcomandos (reset, guardar, recordar, todo).
# ══════════════════════════════════════════════════════════════════════════════
def reset() -> None:
    """Borra los dos archivos de datos de la demo (sesiones y memoria), si existen, para empezar de cero."""
    for f in (DB_SESIONES, DB_MEMORIA):
        f.unlink(missing_ok=True)
    print("Bases de datos de la demo borradas.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "todo"  # sin argumentos corre `todo`
    try:
        if cmd == "reset":
            reset()
        elif cmd == "guardar":
            sys.exit(asyncio.run(guardar()))
        elif cmd == "recordar":
            sys.exit(asyncio.run(recordar()))
        elif cmd == "todo":
            reset()
            rc = 0
            for sub in ("guardar", "recordar"):  # procesos separados a propósito: eso es lo que prueba la persistencia
                print(f"\n######## {sub} (proceso nuevo) ########", flush=True)
                rc_sub = subprocess.run([sys.executable, "-u", __file__, sub]).returncode
                if rc_sub == 2:
                    sys.exit(2)  # error de ejecución: no sigue
                rc = max(rc, rc_sub)
            sys.exit(rc)
        else:
            sys.exit(__doc__)  # subcomando desconocido: imprime este texto como ayuda de uso
    except Exception:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print("\nERROR DE EJECUCIÓN (no es una verificación fallida): ver el traceback de arriba.")
        sys.exit(2)
