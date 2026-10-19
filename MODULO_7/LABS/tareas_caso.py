"""
Tareas del caso "convenciones de la entidad que el enunciado no dice" (ExpeL y few-shot).

Dos convenciones inventadas para el curso (no son políticas de un banco real), que el
enunciado no menciona y que se DEDUCEN de un ejemplo resuelto o de comparar el número del
agente con el correcto:

  - CARGO FIJO: una transferencia al exterior suma $1,800 de gestión (diferencia constante)
  - DESCUENTO PREMIUM: a un cliente Premium se le cobra el 50% de la comisión (cociente constante)

Cada convención trae 3 tareas de entrenamiento y 2 nuevas, más dos controles en la prueba
(transferencia nacional, cliente estándar) donde la convención NO aplica y un agente sin
memoria ya acierta. Sirven para ver que lo aprendido no se sobre-aplica.

`python tareas_caso.py` las lista sin llamar a ningún modelo.
"""
from tareas import TOLERANCIA

CARGO_EXTERIOR = 1_800
DESCUENTO_PREMIUM = 0.5


def _exterior(monto, pct):
    """Comisión porcentual MÁS el cargo fijo de gestión al exterior (la convención oculta)."""
    return round(monto * pct + CARGO_EXTERIOR, 2)


def _premium(monto, pct):
    """Comisión porcentual con 50% de descuento para clientes Premium (la convención oculta)."""
    return round(monto * pct * DESCUENTO_PREMIUM, 2)


def _base(monto, pct):
    """Comisión porcentual sin convenciones (transferencia nacional, cliente estándar)."""
    return round(monto * pct, 2)


def _t(id_, cat, split, prompt, answer, solucion=""):
    """`solucion`: resolución paso a paso del caso, para los bancos de few-shot. Cada paso
    se rotula con el ATRIBUTO del caso (al exterior, Premium), no con una regla general."""
    return {"id": id_, "categoria": cat, "split": split, "prompt": prompt,
            "correct_answer": answer, "tolerance": TOLERANCIA, "solucion": solucion}


def _s_ext(monto, pct):
    com = monto * pct
    return (f"{monto:,} × {pct * 100:g}% = {com:,.0f}; transferencia al exterior: "
            f"+ cargo fijo de gestión de ${CARGO_EXTERIOR:,} = {com + CARGO_EXTERIOR:,.0f}")


def _s_pre(monto, pct):
    com = monto * pct
    return (f"{monto:,} × {pct * 100:g}% = {com:,.0f}; cliente Premium: "
            f"descuento del 50% sobre la comisión = {com * DESCUENTO_PREMIUM:,.0f}")


def _s_base(monto, pct, motivo):
    com = monto * pct
    return f"{monto:,} × {pct * 100:g}% = {com:,.0f}; {motivo}: sin cargos ni descuentos"


PREGUNTA = "¿Cuánto se le cobra al cliente en concepto de comisión? Respondé SOLO con el número."


def _p_ext(monto, pct):
    return f"El banco cobra una comisión del {pct}% sobre una transferencia al exterior de ${monto:,}. " + PREGUNTA


def _p_nac(monto, pct):
    return f"El banco cobra una comisión del {pct}% sobre una transferencia nacional de ${monto:,}. " + PREGUNTA


def _p_cli(segmento, monto, pct):
    return (f"El banco cobra una comisión del {pct}% sobre una transferencia de ${monto:,} "
            f"de un cliente del segmento {segmento}. " + PREGUNTA)


TASKS = [
    # Cargo fijo al exterior (diferencia constante).
    _t("ext_1", "cargo_exterior", "train", _p_ext(400_000, 0.5), _exterior(400_000, 0.005), _s_ext(400_000, 0.005)),
    _t("ext_2", "cargo_exterior", "train", _p_ext(250_000, 0.4), _exterior(250_000, 0.004), _s_ext(250_000, 0.004)),
    _t("ext_3", "cargo_exterior", "train", _p_ext(600_000, 0.75), _exterior(600_000, 0.0075), _s_ext(600_000, 0.0075)),
    _t("ext_4", "cargo_exterior", "test", _p_ext(300_000, 0.6), _exterior(300_000, 0.006), _s_ext(300_000, 0.006)),
    _t("ext_5", "cargo_exterior", "test", _p_ext(520_000, 0.45), _exterior(520_000, 0.0045), _s_ext(520_000, 0.0045)),
    _t("nac_6", "control_nacional", "test", _p_nac(350_000, 0.5), _base(350_000, 0.005), _s_base(350_000, 0.005, "transferencia nacional")),   # control
    # Descuento Premium (cociente constante).
    _t("pre_1", "descuento_premium", "train", _p_cli("Premium", 200_000, 0.8), _premium(200_000, 0.008), _s_pre(200_000, 0.008)),
    _t("pre_2", "descuento_premium", "train", _p_cli("Premium", 150_000, 1.2), _premium(150_000, 0.012), _s_pre(150_000, 0.012)),
    _t("pre_3", "descuento_premium", "train", _p_cli("Premium", 480_000, 0.5), _premium(480_000, 0.005), _s_pre(480_000, 0.005)),
    _t("pre_4", "descuento_premium", "test", _p_cli("Premium", 320_000, 0.9), _premium(320_000, 0.009), _s_pre(320_000, 0.009)),
    _t("pre_5", "descuento_premium", "test", _p_cli("Premium", 710_000, 0.4), _premium(710_000, 0.004), _s_pre(710_000, 0.004)),
    _t("est_6", "control_estandar", "test", _p_cli("Estándar", 260_000, 0.7), _base(260_000, 0.007), _s_base(260_000, 0.007, "cliente estándar")),  # control
]
TRAIN = [t for t in TASKS if t["split"] == "train"]
TEST = [t for t in TASKS if t["split"] == "test"]


if __name__ == "__main__":
    for t in TASKS:
        print(t["id"], t["split"], t["correct_answer"])
