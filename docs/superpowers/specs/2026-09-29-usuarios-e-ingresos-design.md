# Baja de usuarios e ingreso de medicamentos — Diseño

Fecha: 2026-09-29 · Origen: `prompts/promptChatBotIpsUsuarios.md` · Extiende: `2026-09-29-chatbot-ips-design.md` · Estado: pendiente de revisión

## 1. Propósito y criterios de éxito

Dos funciones nuevas sobre el MVP existente, sin alterar lo que ya funciona:

1. El **administrador** puede **eliminar usuarios** (con confirmación) además de crearlos y verlos.
2. **Farmacia y almacenista** registran el **ingreso de medicamentos** con lote, vencimiento, fecha de ingreso y responsable, con trazabilidad completa.

Éxito:
- Eliminar pide siempre la confirmación "¿Está seguro de que desea eliminar este usuario?" y no elimina sin confirmar.
- Un ingreso guardado sube la cantidad disponible, queda con lote, vencimiento, fecha y responsable, y aparece en *Movimientos*.
- No se puede guardar información incompleta o inconsistente (validado en backend y en el formulario).
- Las 15 preguntas del chatbot y la prueba de humo siguen funcionando sin cambios.
- Las pruebas nuevas y las 88 existentes (ajustadas donde se indica) pasan.

## 2. Decisiones acordadas

**Eliminar usuarios**
1. "Eliminar" **borra el usuario de la base de datos** (cambio posterior a la primera versión, que era una baja lógica y impedía reutilizar el nombre de usuario). Cada movimiento guarda el **nombre del responsable** al momento de registrarse (`movimientos.responsable`) y `movimientos.usuario_id` pasa a `NULL` al borrar el usuario (`ON DELETE SET NULL`), así el historial conserva quién fue. El nombre de usuario queda libre.
2. El administrador **no puede eliminarse a sí mismo**. Como quien elimina siempre es un administrador activo, esto garantiza que nunca queden cero administradores (no hace falta una regla aparte para "el último administrador").
3. La confirmación usa el cuadro de diálogo del navegador (`confirm`) con el texto exacto.

**Ingreso de medicamentos**
4. En *Movimientos* hay dos acciones: **"Ingreso de medicamentos"** (formulario nuevo) y **"Registrar salida"** (el formulario actual, solo salidas). Las entradas solo se registran por el ingreso, así siempre llevan lote.
5. **Medicamento:** se elige de la lista, o se selecciona "Nuevo medicamento", que pide además principio activo, presentación, stock mínimo y ubicación.
6. **Responsable:** es el usuario con sesión iniciada (campo de solo lectura; el backend lo toma del token, nunca del formulario).
7. **Fecha de ingreso:** por defecto hoy; no puede ser futura. El movimiento se guarda con esa fecha y la hora actual.
8. **Vencimiento del medicamento:** conserva una sola fecha, la **más próxima**: `LEAST(fecha actual del medicamento, vencimiento del lote)` si la actual no ha vencido; si ya venció, la del lote. Así vencimientos, alertas y chatbot no cambian.
9. **Límite conocido:** no se lleva la cantidad por lote; las salidas no descuentan de un lote concreto.

## 3. Datos

`db/init.sql` (se recrea con DROP/CREATE, sin migraciones):

- `movimientos` gana `responsable VARCHAR(100) NOT NULL` (nombre del responsable al registrar), `usuario_id` pasa a admitir `NULL` con `ON DELETE SET NULL`, y además `lote VARCHAR(40) NULL` y `fecha_vencimiento DATE NULL`, con `CHECK (tipo = 'ENTRADA' OR (lote IS NULL AND fecha_vencimiento IS NULL))`. Las entradas del seed llevan lote (`L-2026-001`…) y el vencimiento del medicamento; las salidas quedan sin lote.
- `medicamentos` y `usuarios` no cambian de estructura.

## 4. API

Todos los endpoints exigen token; el rol se valida en el backend.

**`DELETE /usuarios/{id}`** (solo ADMINISTRADOR) → 204.
- 404 si no existe; 409 si `id` es el del usuario que llama.
- `GET /usuarios` pasa a listar **solo usuarios `ACTIVO`**.

**`POST /ingresos`** (FARMACIA, ALMACENISTA) → 201.

Cuerpo:
```json
{
  "medicamento_id": 1,
  "nuevo_medicamento": null,
  "cantidad": 100,
  "lote": "L-2026-041",
  "fecha_vencimiento": "2027-03-31",
  "fecha_ingreso": "2026-09-29"
}
```
- Exactamente uno de `medicamento_id` o `nuevo_medicamento` (`{nombre, principio_activo, presentacion, stock_minimo, ubicacion}`).
- Respuesta: `{"movimiento_id", "medicamento_id", "cantidad_actual", "fecha_vencimiento"}`.
- Todo ocurre en una transacción: crear medicamento (si es nuevo, con cantidad 0), sumar cantidad, actualizar vencimiento según la regla 8 e insertar el movimiento `ENTRADA` con lote, vencimiento, fecha y `usuario_id` del token.

Validaciones (422 salvo indicación):
- `cantidad`: entero, 1 a 100000.
- `lote`: 1 a 40 caracteres tras quitar espacios; solo letras, dígitos y `. _ / -`.
- `fecha_vencimiento` posterior a `fecha_ingreso` y no anterior a hoy (no se ingresan lotes ya vencidos); `fecha_ingreso` no futura ni anterior a un año (evita errores de digitación como un año equivocado).
- `nuevo_medicamento`: `nombre` ≤ 80, `principio_activo` ≤ 80, `presentacion` ≤ 60, `ubicacion` ≤ 60, todos no vacíos y sin NUL; `stock_minimo` entero 0 a 100000. Nombre repetido (sin distinguir mayúsculas, incluyendo inactivos; lo garantiza un índice único en la BD) → 409.
- Ambos o ninguno de `medicamento_id`/`nuevo_medicamento` → 422; `medicamento_id` inexistente → 404.

**`POST /movimientos`** acepta solo `SALIDA` (`tipo: "ENTRADA"` → 422). `GET /movimientos`, `/movimientos/entradas` y `/movimientos/salidas` devuelven además `lote` y `fecha_vencimiento` por movimiento (nulos en entradas antiguas y en salidas).

## 5. Frontend

- **Usuarios:** la tabla suma una columna de acciones con botón "Eliminar". Al pulsarlo aparece la confirmación exacta; solo al aceptar se llama al `DELETE` y se recarga la lista. El botón no aparece en la fila del propio administrador. Los errores se muestran en español.
- **Movimientos:** pestañas o botones "Ingreso de medicamentos" y "Registrar salida" (no visibles para el administrador, como hoy). El formulario de ingreso tiene los campos de la sección 2, con `required`, `min/max` y fecha de ingreso limitada a hoy; el bloque "Nuevo medicamento" se muestra solo al elegir esa opción. Tras guardar, mensaje de éxito y tabla actualizada, que ahora muestra columnas Lote y Vencimiento.
- Sin cambios en el resto de vistas, en el chatbot ni en el diseño general.

## 6. Pruebas

- Backend (`pytest`, BD real): eliminación de usuario (204, la fila desaparece, no puede iniciar sesión, el nombre de usuario se puede reutilizar, sus movimientos conservan el nombre del responsable, 404 repetido, 409 a sí mismo, 403 a otros roles); ingreso (stock sube, movimiento con lote/vencimiento/responsable del token, regla de vencimiento en sus tres casos, medicamento nuevo, atomicidad ante error, todas las validaciones y los 403/404/409 anteriores); `POST /movimientos` rechaza `ENTRADA`.
- Se ajustan los tests actuales que registraban entradas por `POST /movimientos` para usar `POST /ingresos`.
- Prueba de humo y las 15 preguntas: sin cambios y deben seguir en verde.
- Frontend: recorrido manual (lista de comprobación en el plan).

## 7. Fuera de alcance

Cantidad por lote y descuento FIFO de salidas, edición o reactivación de usuarios, borrado físico, eliminar o editar medicamentos, migraciones de BD con datos existentes.

## 8. Documentación

Se actualiza el README (endpoints nuevos, tabla de roles, límite de lotes).
