import re

TOTAL_MEDICAMENTOS = "TOTAL_MEDICAMENTOS"
BAJO_STOCK = "BAJO_STOCK"
PROXIMOS_A_VENCER = "PROXIMOS_A_VENCER"
REVISION_VENCIMIENTO = "REVISION_VENCIMIENTO"
MOVIMIENTOS_DEL_MES = "MOVIMIENTOS_DEL_MES"
MAYOR_MOVIMIENTO_MES = "MAYOR_MOVIMIENTO_MES"
CONSULTAR_INVENTARIO_MEDICAMENTO = "CONSULTAR_INVENTARIO_MEDICAMENTO"
ENTRADAS_MEDICAMENTO_MES = "ENTRADAS_MEDICAMENTO_MES"
SALIDAS_MEDICAMENTO_MES = "SALIDAS_MEDICAMENTO_MES"
UBICACION_MEDICAMENTO = "UBICACION_MEDICAMENTO"
ULTIMA_ENTRADA = "ULTIMA_ENTRADA"
ULTIMA_SALIDA = "ULTIMA_SALIDA"

_ENTRADA = r"\b(entradas?|entraron|ingres\w*)\b"
_SALIDA = r"\b(salidas?|salio|salieron|egres\w*)\b"


def _hay(patron: str, texto: str) -> bool:
    return re.search(patron, texto) is not None


def detectar_intencion(texto: str, hay_medicamento: bool):
    """Recibe texto ya normalizado. Devuelve el nombre de la intención o None."""
    if hay_medicamento and _hay(r"\bultim[ao]\b", texto):
        if _hay(_ENTRADA, texto):
            return ULTIMA_ENTRADA
        if _hay(_SALIDA, texto):
            return ULTIMA_SALIDA
    if hay_medicamento and _hay(r"\b(donde|ubicacion|ubicad[oa]s?|guardad[oa]s?)\b", texto):
        return UBICACION_MEDICAMENTO
    if _hay(r"\b(mayor|mas)\b.*\bmovimientos?\b", texto):
        return MAYOR_MOVIMIENTO_MES

    entradas, salidas = _hay(_ENTRADA, texto), _hay(_SALIDA, texto)
    if hay_medicamento and entradas and not salidas:
        return ENTRADAS_MEDICAMENTO_MES
    if hay_medicamento and salidas and not entradas:
        return SALIDAS_MEDICAMENTO_MES
    if not hay_medicamento and entradas and salidas:
        return MOVIMIENTOS_DEL_MES

    if _hay(r"\b(vencer|vencen|vencimientos?|vencidos?|caducar|caducan)\b", texto):
        return REVISION_VENCIMIENTO if _hay(r"\brevis\w*\b", texto) else PROXIMOS_A_VENCER
    if _hay(r"\b(minimo|poco stock|bajo stock|stock bajo|inventario bajo|poco inventario|pocas unidades)\b", texto):
        return BAJO_STOCK
    if (
        not hay_medicamento
        and _hay(r"\bmedicamentos\b", texto)
        and _hay(r"\b(cuantos|total)\b", texto)
        and _hay(r"\b(registrados|tenemos|hay|existen)\b", texto)
    ):
        return TOTAL_MEDICAMENTOS
    if hay_medicamento and _hay(
        r"\b(cuant\w*|cantidad|queda\w*|hay|tenemos|disponibles?|unidades|existencias?|stock|inventario)\b", texto
    ):
        return CONSULTAR_INVENTARIO_MEDICAMENTO
    return None
