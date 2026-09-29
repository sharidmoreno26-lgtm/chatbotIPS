import pytest

from app.chatbot import intenciones as i
from app.chatbot import permisos, respuestas
from app.chatbot.normalizador import normalizar


@pytest.mark.parametrize(
    "pregunta, hay_med, esperado",
    [
        ("¿Cuántos medicamentos tenemos registrados actualmente?", False, i.TOTAL_MEDICAMENTOS),
        ("¿Cuáles son los medicamentos que están por debajo del mínimo establecido?", False, i.BAJO_STOCK),
        ("¿Qué medicamentos tienen poco stock?", False, i.BAJO_STOCK),
        ("¿Qué medicamentos están próximos a vencer durante los próximos 30 días?", False, i.PROXIMOS_A_VENCER),
        ("¿Qué medicamentos están próximos a vencer?", False, i.PROXIMOS_A_VENCER),
        ("¿Qué medicamentos debo revisar por vencimiento?", False, i.REVISION_VENCIMIENTO),
        ("¿Cuántas entradas y salidas de medicamentos se registraron durante este mes?", False, i.MOVIMIENTOS_DEL_MES),
        ("¿Qué medicamento tiene mayor movimiento durante este mes?", False, i.MAYOR_MOVIMIENTO_MES),
        ("¿Cuántas unidades hay disponibles de acetaminofén?", True, i.CONSULTAR_INVENTARIO_MEDICAMENTO),
        ("¿Cuánto acetaminofén queda?", True, i.CONSULTAR_INVENTARIO_MEDICAMENTO),
        ("¿Cuántas unidades de acetaminofén hay?", True, i.CONSULTAR_INVENTARIO_MEDICAMENTO),
        ("¿Qué cantidad de acetaminofén tenemos?", True, i.CONSULTAR_INVENTARIO_MEDICAMENTO),
        ("¿Cuántas unidades de acetaminofén ingresaron durante este mes?", True, i.ENTRADAS_MEDICAMENTO_MES),
        ("¿Cuántas unidades de acetaminofén salieron durante este mes?", True, i.SALIDAS_MEDICAMENTO_MES),
        ("¿Dónde está ubicado insulina?", True, i.UBICACION_MEDICAMENTO),
        ("¿Dónde está ubicada la insulina?", True, i.UBICACION_MEDICAMENTO),
        ("¿Cuándo fue registrada la última entrada de acetaminofén?", True, i.ULTIMA_ENTRADA),
        ("¿Cuándo fue registrada la última salida de acetaminofén?", True, i.ULTIMA_SALIDA),
        ("hola", False, None),
        ("¿Cuál es la capital de Francia?", False, None),
        ("¿Dónde está ubicado el paracetamol?", False, None),  # medicamento no encontrado
    ],
)
def test_detectar_intencion(pregunta, hay_med, esperado):
    assert i.detectar_intencion(normalizar(pregunta), hay_med) == esperado


def test_toda_intencion_tiene_permisos_y_manejador():
    todas = {v for k, v in vars(i).items() if k.isupper() and not k.startswith("_") and isinstance(v, str)}
    assert todas == set(permisos.PERMISOS) == set(respuestas.MANEJADORES)
