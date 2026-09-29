from psycopg.errors import UniqueViolation

DIAS_VENCIMIENTO = 30

_COLUMNAS_MED = """id, nombre, principio_activo, presentacion, cantidad_actual, stock_minimo,
                   fecha_vencimiento, ubicacion, estado"""

# Constante interna (no contiene entrada del usuario).
_EN_EL_MES = """fecha >= date_trunc('month', CURRENT_DATE)::date
                AND fecha < (date_trunc('month', CURRENT_DATE) + interval '1 month')::date"""


def listar_medicamentos(conn):
    return conn.execute(
        f"SELECT {_COLUMNAS_MED} FROM medicamentos WHERE estado = 'ACTIVO' ORDER BY nombre"
    ).fetchall()


def obtener_medicamento(conn, med_id):
    return conn.execute(
        f"SELECT {_COLUMNAS_MED} FROM medicamentos WHERE id = %s AND estado = 'ACTIVO'", (med_id,)
    ).fetchone()


def contar_medicamentos(conn):
    return conn.execute("SELECT count(*) AS n FROM medicamentos WHERE estado = 'ACTIVO'").fetchone()["n"]


def medicamentos_bajo_stock(conn):
    return conn.execute(
        f"""SELECT {_COLUMNAS_MED} FROM medicamentos
            WHERE estado = 'ACTIVO' AND cantidad_actual < stock_minimo ORDER BY nombre"""
    ).fetchall()


def medicamentos_proximos_a_vencer(conn, dias=DIAS_VENCIMIENTO):
    return conn.execute(
        f"""SELECT {_COLUMNAS_MED}, (fecha_vencimiento - CURRENT_DATE) AS dias_restantes
            FROM medicamentos
            WHERE estado = 'ACTIVO'
              AND fecha_vencimiento BETWEEN CURRENT_DATE AND CURRENT_DATE + %s::int
            ORDER BY fecha_vencimiento, nombre""",
        (dias,),
    ).fetchall()


def listar_movimientos(conn, tipo=None):
    return conn.execute(
        """SELECT mv.id, mv.medicamento_id, m.nombre AS medicamento, mv.tipo, mv.cantidad,
                  mv.fecha, mv.responsable AS usuario, mv.lote, mv.fecha_vencimiento
           FROM movimientos mv
           JOIN medicamentos m ON m.id = mv.medicamento_id
           WHERE (%s::text IS NULL OR mv.tipo = %s)
           ORDER BY mv.fecha DESC, mv.id DESC""",
        (tipo, tipo),
    ).fetchall()


def contar_movimientos_mes(conn):
    return conn.execute(
        f"""SELECT count(*) FILTER (WHERE tipo = 'ENTRADA') AS entradas,
                   count(*) FILTER (WHERE tipo = 'SALIDA') AS salidas
            FROM movimientos WHERE {_EN_EL_MES}"""
    ).fetchone()


def mayor_movimiento_mes(conn):
    return conn.execute(
        f"""SELECT m.nombre, count(*) AS movimientos
            FROM movimientos mv JOIN medicamentos m ON m.id = mv.medicamento_id
            WHERE {_EN_EL_MES}
            GROUP BY m.id, m.nombre ORDER BY movimientos DESC, m.nombre LIMIT 1"""
    ).fetchone()


def unidades_movidas_mes(conn, med_id, tipo):
    return conn.execute(
        f"""SELECT COALESCE(SUM(cantidad), 0) AS total FROM movimientos
            WHERE medicamento_id = %s AND tipo = %s AND {_EN_EL_MES}""",
        (med_id, tipo),
    ).fetchone()["total"]


def ultimo_movimiento(conn, med_id, tipo):
    return conn.execute(
        """SELECT fecha, cantidad FROM movimientos WHERE medicamento_id = %s AND tipo = %s
           ORDER BY fecha DESC, id DESC LIMIT 1""",
        (med_id, tipo),
    ).fetchone()


def registrar_movimiento(conn, med_id, tipo, cantidad, usuario_id):
    """Registra el movimiento y actualiza el stock. No hace commit."""
    med = conn.execute(
        "SELECT cantidad_actual FROM medicamentos WHERE id = %s AND estado = 'ACTIVO' FOR UPDATE",
        (med_id,),
    ).fetchone()
    if med is None:
        raise LookupError("Medicamento no encontrado")
    cambio = cantidad if tipo == "ENTRADA" else -cantidad
    if med["cantidad_actual"] + cambio < 0:
        raise ValueError("No hay unidades suficientes para registrar la salida")
    nuevo = conn.execute(
        "UPDATE medicamentos SET cantidad_actual = cantidad_actual + %s WHERE id = %s RETURNING cantidad_actual",
        (cambio, med_id),
    ).fetchone()["cantidad_actual"]
    mov = conn.execute(
        """INSERT INTO movimientos (medicamento_id, tipo, cantidad, usuario_id, responsable)
           VALUES (%s, %s, %s, %s, (SELECT nombre FROM usuarios WHERE id = %s)) RETURNING id""",
        (med_id, tipo, cantidad, usuario_id, usuario_id),
    ).fetchone()
    return {"id": mov["id"], "cantidad_actual": nuevo}


def registrar_ingreso(
    conn, usuario_id, cantidad, lote, fecha_vencimiento, fecha_ingreso, medicamento_id=None, nuevo=None
):
    """Registra un ingreso (ENTRADA con lote) y actualiza stock y vencimiento. No hace commit.

    Lanza LookupError si el medicamento no existe y ValueError si el nombre nuevo ya existe.
    """
    if nuevo is not None:
        try:
            medicamento_id = conn.execute(
                """INSERT INTO medicamentos (nombre, principio_activo, presentacion, cantidad_actual,
                                             stock_minimo, fecha_vencimiento, ubicacion)
                   VALUES (%s, %s, %s, 0, %s, %s, %s) RETURNING id""",
                (
                    nuevo["nombre"],
                    nuevo["principio_activo"],
                    nuevo["presentacion"],
                    nuevo["stock_minimo"],
                    fecha_vencimiento,
                    nuevo["ubicacion"],
                ),
            ).fetchone()["id"]
        except UniqueViolation:
            raise ValueError("Ya existe un medicamento con ese nombre")
    actualizado = conn.execute(
        """UPDATE medicamentos
           SET cantidad_actual = cantidad_actual + %s,
               fecha_vencimiento = CASE WHEN fecha_vencimiento < CURRENT_DATE THEN %s
                                        ELSE LEAST(fecha_vencimiento, %s) END
           WHERE id = %s AND estado = 'ACTIVO'
           RETURNING cantidad_actual, fecha_vencimiento""",
        (cantidad, fecha_vencimiento, fecha_vencimiento, medicamento_id),
    ).fetchone()
    if actualizado is None:
        raise LookupError("Medicamento no encontrado")
    movimiento = conn.execute(
        """INSERT INTO movimientos (medicamento_id, tipo, cantidad, fecha, usuario_id, responsable,
                                     lote, fecha_vencimiento)
           VALUES (%s, 'ENTRADA', %s, %s::date + localtime, %s, (SELECT nombre FROM usuarios WHERE id = %s), %s, %s)
           RETURNING id""",
        (medicamento_id, cantidad, fecha_ingreso, usuario_id, usuario_id, lote, fecha_vencimiento),
    ).fetchone()
    return {
        "movimiento_id": movimiento["id"],
        "medicamento_id": medicamento_id,
        "cantidad_actual": actualizado["cantidad_actual"],
        "fecha_vencimiento": actualizado["fecha_vencimiento"],
    }
