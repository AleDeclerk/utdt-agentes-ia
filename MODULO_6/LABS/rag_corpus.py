"""Corpus de las demos de RAG — normativa interna de una entidad financiera (sintético).

Ocho fragmentos normativos (`norm_001` .. `norm_008`) que combinan manual de
suscripción de riesgos, política de riesgo crediticio, circular normativa,
manual de producto Pyme y reglamento de siniestros. Los datos son sintéticos
e inventados a propósito: no usar como referencia regulatoria real.
"""

CORPUS = [
    {
        "id": "norm_001",
        "source": "Manual de Suscripción de Riesgos 2026",
        "text": """Las pólizas de seguro técnico con suma asegurada superior a USD 500.000 requieren
inspección previa de riesgo y aprobación del Comité de Suscripción. Por debajo de ese
monto, la aprobación es facultad del suscriptor asignado a la cartera."""
    },
    {
        "id": "norm_002",
        "source": "Manual de Suscripción de Riesgos 2026",
        "text": """No se emiten pólizas nuevas sobre bienes ubicados en zonas declaradas de riesgo
hídrico severo sin recargo técnico. El recargo mínimo es del 35% sobre la prima de
tarifa y no puede ser bonificado por el canal comercial."""
    },
    {
        "id": "norm_003",
        "source": "Política de Riesgo Crediticio 2026",
        "text": """La asistencia crediticia total a un mismo cliente no puede superar el 15% de la
responsabilidad patrimonial computable de la entidad. Para clientes vinculados, el
límite se computa en forma consolidada y se reduce al 5%."""
    },
    {
        "id": "norm_004",
        "source": "Política de Riesgo Crediticio 2026",
        "text": """Toda operación que exceda las facultades del oficial de cuentas debe elevarse al
Comité de Créditos con dictamen previo de la Gerencia de Riesgos. El dictamen tiene
una vigencia de 90 días corridos desde su emisión; vencido ese plazo debe requerirse
uno nuevo."""
    },
    {
        "id": "norm_005",
        "source": "Circular Normativa 07/2026",
        "text": """Los legajos de clientes personas jurídicas deben actualizarse con periodicidad
anual. La falta de actualización por más de doce meses inhabilita la aprobación de
nuevas operaciones activas hasta su regularización."""
    },
    {
        "id": "norm_006",
        "source": "Circular Normativa 07/2026",
        "text": """Antes del alta de un beneficiario nuevo debe verificarse su identificación contra
las listas de sanciones vigentes. Las transferencias a beneficiarios dados de alta en
las últimas 48 horas quedan sujetas a revisión manual cuando superan el equivalente a
veinte salarios mínimos."""
    },
    {
        "id": "norm_007",
        "source": "Manual de Producto — Línea Pyme 2026",
        "text": """La línea de capital de trabajo para Pymes se otorga a un plazo máximo de 18 meses,
con un período de gracia de hasta 90 días. La cancelación anticipada total no tiene
penalidad; la parcial admite un máximo de dos eventos por ejercicio."""
    },
    {
        "id": "norm_008",
        "source": "Reglamento de Siniestros 2026",
        "text": """La denuncia de siniestro debe presentarse dentro de los 3 días hábiles de conocido
el hecho. El liquidador designado tiene 30 días corridos para pronunciarse; vencido
ese plazo sin pronunciamiento, el siniestro se considera aceptado."""
    },
]

if __name__ == "__main__":
    print(f"Corpus cargado: {len(CORPUS)} documentos")
