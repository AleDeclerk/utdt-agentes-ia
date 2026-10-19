"""
Tareas de la demo del Módulo 7: problemas financieros con CONVENCIONES DE LA
ENTIDAD que el enunciado no menciona.

Por qué así: con problemas de fórmula estándar (VAN, ROI, margen) un modelo
actual acierta al primer intento y no hay nada que aprender. Acá la respuesta correcta
depende de una convención interna que solo el verificador conoce:

  - comision_redondeo:  la comisión se redondea SIEMPRE AL ALZA al peso entero
  - punitorio_150:      el interés punitorio es 150% de la tasa compensatoria
  - comision_iva:       a toda comisión se le suma IVA 21% al debitarla

Cada categoría tiene tareas de entrenamiento ("train") y tareas nuevas de la
misma categoría ("test") para medir transferencia: 3 categorías x (3 train + 2 test)
= 15 tareas (9 train, 6 test). Cómo se usan:

  - TRAIN  : la experiencia de la que se aprende (Reflexion, banco de casos del
             few-shot dinámico, destilación de reglas de ExpeL).
  - TEST   : tareas NUEVAS, para medir si lo aprendido transfiere.

Formato de una tarea (dict):
    {"id": "com_1", "categoria": "comision_redondeo", "split": "train",
     "prompt": "<enunciado>", "correct_answer": 994, "tolerance": 0.01}

Todo es sintético: las convenciones están inventadas para el curso (no son las
políticas de ningún banco real) y no hay datos de clientes.

Correr `python tareas.py` imprime las 15 tareas con su respuesta esperada (sirve
para chequear la banca de tareas sin llamar a ningún modelo).
"""
import math

TOLERANCIA = 0.01


def _punitorio(capital, tasa_comp, dias):
    """Interés punitorio simple = 150% de la tasa compensatoria, año de 360 días."""
    return round(capital * tasa_comp * 1.5 * dias / 360, 2)


def _comision_iva(monto, pct):
    """Comisión (monto * pct) más IVA 21%, sin redondear al entero."""
    return round(monto * pct * 1.21, 2)


def _comision(monto, pct):
    """Comisión redondeada SIEMPRE AL ALZA al peso entero (la convención oculta)."""
    # Se evita el error de punto flotante (p. ej. 0.011 * 90300 = 993.3000000000001).
    return math.ceil(round(monto * pct, 6))


def _t(id_, cat, split, prompt, answer):
    """Arma el dict de una tarea (ver formato en el docstring del módulo)."""
    return {"id": id_, "categoria": cat, "split": split, "prompt": prompt,
            "correct_answer": answer, "tolerance": TOLERANCIA}


TASKS = [
    # ── punitorio = 150% de la compensatoria (año comercial) ─────────────
    _t("pun_1", "punitorio_150", "train",
       "Un préstamo de $200,000 tiene tasa compensatoria del 24% nominal anual. "
       "El cliente cae en mora 60 días. Calculá el interés punitorio por esos 60 días "
       "con interés simple y año de 360 días. Respondé SOLO con el número.",
       _punitorio(200_000, 0.24, 60)),
    _t("pun_2", "punitorio_150", "train",
       "Un préstamo de $90,000 tiene tasa compensatoria del 30% nominal anual. "
       "El cliente cae en mora 45 días. Calculá el interés punitorio por esos 45 días "
       "con interés simple y año de 360 días. Respondé SOLO con el número.",
       _punitorio(90_000, 0.30, 45)),
    _t("pun_3", "punitorio_150", "train",
       "Un préstamo de $350,000 tiene tasa compensatoria del 36% nominal anual. "
       "El cliente cae en mora 30 días. Calculá el interés punitorio por esos 30 días "
       "con interés simple y año de 360 días. Respondé SOLO con el número.",
       _punitorio(350_000, 0.36, 30)),
    _t("pun_4", "punitorio_150", "test",
       "Un préstamo de $120,000 tiene tasa compensatoria del 28% nominal anual. "
       "El cliente cae en mora 75 días. Calculá el interés punitorio por esos 75 días "
       "con interés simple y año de 360 días. Respondé SOLO con el número.",
       _punitorio(120_000, 0.28, 75)),
    _t("pun_5", "punitorio_150", "test",
       "Un préstamo de $500,000 tiene tasa compensatoria del 20% nominal anual. "
       "El cliente cae en mora 90 días. Calculá el interés punitorio por esos 90 días "
       "con interés simple y año de 360 días. Respondé SOLO con el número.",
       _punitorio(500_000, 0.20, 90)),
    # ── comisión + IVA 21% ───────────────────────────────────────────────
    _t("iva_1", "comision_iva", "train",
       "El banco cobra una comisión de mantenimiento del 0.5% sobre un saldo de $240,000. "
       "¿Cuánto se debita de la cuenta del cliente por este concepto? "
       "Respondé SOLO con el número, con 2 decimales.",
       _comision_iva(240_000, 0.005)),
    _t("iva_2", "comision_iva", "train",
       "El banco cobra una comisión del 2% por emitir un cheque de gerencia de $75,000. "
       "¿Cuánto se debita de la cuenta del cliente por este concepto? "
       "Respondé SOLO con el número, con 2 decimales.",
       _comision_iva(75_000, 0.02)),
    _t("iva_3", "comision_iva", "train",
       "El banco cobra una comisión del 1.5% por una transferencia al exterior de $180,000. "
       "¿Cuánto se debita de la cuenta del cliente por este concepto? "
       "Respondé SOLO con el número, con 2 decimales.",
       _comision_iva(180_000, 0.015)),
    _t("iva_4", "comision_iva", "test",
       "El banco cobra una comisión del 0.8% por administrar una cartera de $310,000. "
       "¿Cuánto se debita de la cuenta del cliente por este concepto? "
       "Respondé SOLO con el número, con 2 decimales.",
       _comision_iva(310_000, 0.008)),
    _t("iva_5", "comision_iva", "test",
       "El banco cobra una comisión del 1.2% por una transferencia de $95,000. "
       "¿Cuánto se debita de la cuenta del cliente por este concepto? "
       "Respondé SOLO con el número, con 2 decimales.",
       _comision_iva(95_000, 0.012)),
    # ── comisión con redondeo al alza ────────────────────────────────────
    _t("com_1", "comision_redondeo", "train",
       "El banco cobra una comisión del 1.1% sobre una transferencia de $90,300. "
       "¿Cuánto es la comisión en pesos? Respondé SOLO con el número.",
       _comision(90_300, 0.011)),
    _t("com_2", "comision_redondeo", "train",
       "El banco cobra una comisión del 0.8% sobre un pago de $52,630. "
       "¿Cuánto es la comisión en pesos? Respondé SOLO con el número.",
       _comision(52_630, 0.008)),
    _t("com_3", "comision_redondeo", "train",
       "El banco cobra una comisión del 1.4% sobre un cobro de $71,230. "
       "¿Cuánto es la comisión en pesos? Respondé SOLO con el número.",
       _comision(71_230, 0.014)),
    _t("com_4", "comision_redondeo", "test",
       "El banco cobra una comisión del 0.9% sobre una operación de $63,450. "
       "¿Cuánto es la comisión en pesos? Respondé SOLO con el número.",
       _comision(63_450, 0.009)),
    _t("com_5", "comision_redondeo", "test",
       "El banco cobra una comisión del 1.3% sobre una transferencia de $38,720. "
       "¿Cuánto es la comisión en pesos? Respondé SOLO con el número.",
       _comision(38_720, 0.013)),
]

TRAIN = [t for t in TASKS if t["split"] == "train"]
TEST = [t for t in TASKS if t["split"] == "test"]


def extraer_numero(texto: str):
    """Último número del texto, o None si no hay ninguno.

    Admite coma como separador de miles ("12,000.5" -> 12000.5). LIMITACIÓN: una
    respuesta con coma decimal ("993,3") se leería como 9933. Los enunciados piden
    "SOLO el número" y usan punto decimal, y en las corridas documentadas el modelo
    respondió así; si se cambia de modelo o de idioma, conviene revisar este parser."""
    import re
    nums = re.findall(r"-?\d+(?:\.\d+)?", texto.replace(",", ""))
    return float(nums[-1]) if nums else None


def es_correcta(respuesta: float | None, tarea: dict) -> bool:
    """True si `respuesta` coincide con `correct_answer` dentro de `tolerance`."""
    return respuesta is not None and abs(respuesta - tarea["correct_answer"]) <= tarea["tolerance"]


if __name__ == "__main__":
    for t in TASKS:
        print(t["id"], t["split"], t["correct_answer"])
