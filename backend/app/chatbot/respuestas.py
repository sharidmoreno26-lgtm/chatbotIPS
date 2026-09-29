from .. import consultas as c
from . import intenciones as i


def _pl(n, singular, plural):
    return singular if n == 1 else plural


def _fecha(valor):
    return valor.strftime("%d/%m/%Y")


def _lista(filas, formato):
    return "\n".join(f"• {formato(f)}" for f in filas)


def _linea_vencimiento(f):
    d = f["dias_restantes"]
    return f"{f['nombre']} — vence el {_fecha(f['fecha_vencimiento'])} (en {d} {_pl(d, 'día', 'días')})"


def total_medicamentos(conn, med):
    n = c.contar_medicamentos(conn)
    return f"Actualmente hay {n} {_pl(n, 'medicamento registrado', 'medicamentos registrados')} en el sistema."


def bajo_stock(conn, med):
    filas = c.medicamentos_bajo_stock(conn)
    if not filas:
        return "No hay medicamentos por debajo del mínimo establecido."
    n = len(filas)
    return (
        f"Actualmente hay {n} {_pl(n, 'medicamento', 'medicamentos')} por debajo del mínimo establecido:\n\n"
        + _lista(filas, lambda f: f"{f['nombre']} — {f['cantidad_actual']} unidades (mínimo {f['stock_minimo']})")
        + "\n\nTe recomiendo revisar estos medicamentos en el inventario."
    )


def proximos_a_vencer(conn, med):
    filas = c.medicamentos_proximos_a_vencer(conn)
    if not filas:
        return f"No hay medicamentos próximos a vencer durante los próximos {c.DIAS_VENCIMIENTO} días."
    n = len(filas)
    return (
        f"Hay {n} {_pl(n, 'medicamento próximo', 'medicamentos próximos')} a vencer "
        f"durante los próximos {c.DIAS_VENCIMIENTO} días:\n\n"
        + _lista(filas, _linea_vencimiento)
    )


def revision_vencimiento(conn, med):
    filas = c.medicamentos_proximos_a_vencer(conn)
    if not filas:
        return "No hay medicamentos que requieran revisión por vencimiento."
    n = len(filas)
    return (
        f"Hay {n} {_pl(n, 'medicamento que requiere', 'medicamentos que requieren')} "
        "revisión por vencimiento:\n\n" + _lista(filas, _linea_vencimiento)
    )


def movimientos_del_mes(conn, med):
    t = c.contar_movimientos_mes(conn)
    e, s = t["entradas"], t["salidas"]
    return (
        f"Durante este mes se registraron {e} {_pl(e, 'entrada', 'entradas')} "
        f"y {s} {_pl(s, 'salida', 'salidas')} de medicamentos."
    )


def mayor_movimiento_mes(conn, med):
    fila = c.mayor_movimiento_mes(conn)
    if fila is None:
        return "Durante este mes no se han registrado movimientos."
    n = fila["movimientos"]
    return (
        f"El medicamento con mayor movimiento durante este mes ha sido {fila['nombre']}, "
        f"con {n} {_pl(n, 'movimiento registrado', 'movimientos registrados')}."
    )


def inventario_medicamento(conn, med):
    u = med["cantidad_actual"]
    return f"Actualmente hay {u} {_pl(u, 'unidad disponible', 'unidades disponibles')} de {med['nombre']}."


def _unidades_mes(conn, med, tipo, verbo_singular, verbo_plural):
    u = c.unidades_movidas_mes(conn, med["id"], tipo)
    return (
        f"Durante este mes {_pl(u, verbo_singular, verbo_plural)} {u} "
        f"{_pl(u, 'unidad', 'unidades')} de {med['nombre']}."
    )


def entradas_medicamento_mes(conn, med):
    return _unidades_mes(conn, med, "ENTRADA", "ingresó", "ingresaron")


def salidas_medicamento_mes(conn, med):
    return _unidades_mes(conn, med, "SALIDA", "salió", "salieron")


def ubicacion_medicamento(conn, med):
    return f"{med['nombre']} se encuentra en: {med['ubicacion']}."


def _ultimo(conn, med, tipo, palabra):
    fila = c.ultimo_movimiento(conn, med["id"], tipo)
    if fila is None:
        return f"No hay {palabra}s registradas de {med['nombre']}."
    n = fila["cantidad"]
    return (
        f"La última {palabra} de {med['nombre']} fue registrada el {_fecha(fila['fecha'])}, "
        f"con {n} {_pl(n, 'unidad', 'unidades')}."
    )


def ultima_entrada(conn, med):
    return _ultimo(conn, med, "ENTRADA", "entrada")


def ultima_salida(conn, med):
    return _ultimo(conn, med, "SALIDA", "salida")


MANEJADORES = {
    i.TOTAL_MEDICAMENTOS: total_medicamentos,
    i.BAJO_STOCK: bajo_stock,
    i.PROXIMOS_A_VENCER: proximos_a_vencer,
    i.REVISION_VENCIMIENTO: revision_vencimiento,
    i.MOVIMIENTOS_DEL_MES: movimientos_del_mes,
    i.MAYOR_MOVIMIENTO_MES: mayor_movimiento_mes,
    i.CONSULTAR_INVENTARIO_MEDICAMENTO: inventario_medicamento,
    i.ENTRADAS_MEDICAMENTO_MES: entradas_medicamento_mes,
    i.SALIDAS_MEDICAMENTO_MES: salidas_medicamento_mes,
    i.UBICACION_MEDICAMENTO: ubicacion_medicamento,
    i.ULTIMA_ENTRADA: ultima_entrada,
    i.ULTIMA_SALIDA: ultima_salida,
}
