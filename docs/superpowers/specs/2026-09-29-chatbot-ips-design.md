# MVP Chatbot IPS — Diseño

Fecha: 2026-09-29 · Origen: `promptIPS.md` · Estado: pendiente de revisión

## 1. Propósito y criterios de éxito

MVP académico (Administración en Salud) de un chatbot para una IPS, demostrable ante un profesor.
Flujo a demostrar: **Usuario → Chat → Backend → BD relacional → Respuesta**.

Éxito:
- `docker compose up --build` levanta todo localmente, costo $0, sin servicios externos.
- Las 15 preguntas del prompt (5 por rol) responden con datos reales de la BD.
- Cada rol solo accede a lo que le corresponde (validado en backend).
- Pregunta no entendida → mensaje estándar, sin inventar datos.
- Solo datos ficticios.

## 2. Supuestos acordados

1. El chat es de **consulta**. Registrar entradas/salidas se hace con un formulario en la vista *Movimientos* (farmacia y almacenista), no por chat.
2. El administrador gestiona usuarios (listar y crear) en la vista *Usuarios*; sus consultas de inventario/movimientos son de solo lectura.
3. `GET /servicios` devuelve una tabla pequeña de servicios de la IPS (p. ej. Farmacia, Almacén), sin más alcance.

## 3. Arquitectura

Tres contenedores con Docker Compose:

| Contenedor | Tecnología | Función |
|---|---|---|
| frontend | nginx + HTML/CSS/JS puro | Sirve la web en `localhost:80` y reenvía `/api` al backend (un solo origen, sin CORS). |
| backend | FastAPI (Python) | API REST, autenticación, permisos, chatbot. |
| db | PostgreSQL | Datos; `db/init.sql` crea tablas y datos ficticios al primer arranque. |

Decisiones:
- SQL parametrizado con `psycopg` (sin ORM): se ve el SQL de cada respuesta y evita inyección.
- Login: contraseñas con hash bcrypt, token JWT. Secretos y credenciales en `.env` (se entrega `.env.example`).
- Chatbot por reglas, sin IA de pago (ver §6). Aislado en un módulo para poder cambiarlo luego por un modelo local.

## 4. Estructura del proyecto

```
chatbotIps/
├── docker-compose.yml  .env.example  README.md
├── db/init.sql
├── backend/
│   ├── Dockerfile  requirements.txt
│   ├── app/  main.py  config.py  db.py  auth.py
│   │         routers/ (medicamentos, movimientos, usuarios, servicios, chat)
│   │         chatbot/ (normalizador, intenciones, permisos, respuestas)
│   └── tests/
└── frontend/  Dockerfile  nginx.conf  index.html  css/  js/
```

## 5. Base de datos

- `roles(id, nombre)`
- `usuarios(id, nombre, usuario UNIQUE, password_hash, rol_id → roles, estado)`
- `servicios(id, nombre)`
- `medicamentos(id, nombre, principio_activo, presentacion, cantidad_actual, stock_minimo, fecha_vencimiento, ubicacion, estado)`
- `movimientos(id, medicamento_id → medicamentos, tipo CHECK IN ('ENTRADA','SALIDA'), cantidad CHECK > 0, fecha, usuario_id → usuarios)`

Registrar un movimiento actualiza `cantidad_actual` en la misma transacción (la salida no puede dejar stock negativo).

Datos de prueba: 3 usuarios (uno por rol), 12 medicamentos con niveles variados, 3 bajo el mínimo, 3 que vencen en <30 días, entradas y salidas en varios días del mes en curso y del mes anterior, varias ubicaciones. Las fechas se generan relativas a `CURRENT_DATE` para que la demo no caduque.

## 6. Chatbot

Pipeline de `POST /chat` (`{"mensaje": "..."}` → `{"respuesta": "..."}`):

1. Normalizar texto (minúsculas, sin tildes ni signos).
2. Detectar el medicamento buscando en la BD nombre o principio activo dentro del texto.
3. Detectar la intención por palabras clave/sinónimos ("cuánto/cuántas/cantidad/queda/hay/tenemos" + medicamento → `CONSULTAR_INVENTARIO_MEDICAMENTO`).
4. Verificar que el rol del token permite la intención; si no: "Esa consulta no está disponible para tu rol."
5. Ejecutar la consulta SQL y armar la respuesta con el formato del prompt (listas con viñetas, cantidades dinámicas).
6. Sin intención reconocida (o intención que requiere medicamento y no se encontró): "No pude identificar tu consulta. Puedes preguntarme sobre inventario, medicamentos, movimientos, vencimientos o ubicaciones."

Intenciones y roles:

| Intención | Admin | Farmacia | Almacén |
|---|---|---|---|
| TOTAL_MEDICAMENTOS | ✅ | – | – |
| MOVIMIENTOS_DEL_MES | ✅ | – | – |
| MAYOR_MOVIMIENTO_MES | ✅ | – | – |
| BAJO_STOCK | ✅ | ✅ | – |
| PROXIMOS_A_VENCER | ✅ | ✅ | ✅ |
| REVISION_VENCIMIENTO ("¿qué debo revisar por vencimiento?") | ✅ | ✅ | ✅ |
| CONSULTAR_INVENTARIO_MEDICAMENTO | ✅ | ✅ | ✅ |
| ENTRADAS_MEDICAMENTO_MES | – | ✅ | – |
| SALIDAS_MEDICAMENTO_MES | – | ✅ | – |
| UBICACION_MEDICAMENTO | – | – | ✅ |
| ULTIMA_ENTRADA / ULTIMA_SALIDA | – | – | ✅ |

"Próximos a vencer" usa ventana de 30 días. Los límites y la configuración del chatbot viven en constantes en `chatbot/`.

## 7. API

Todos los endpoints (salvo login) exigen token y validan rol con una dependencia de FastAPI.

- `POST /auth/login`, `GET /auth/me`
- `GET /medicamentos`, `/medicamentos/{id}`, `/medicamentos/bajo-stock`, `/medicamentos/proximos-vencer`, `/medicamentos/{id}/inventario`
- `GET /movimientos`, `/movimientos/entradas`, `/movimientos/salidas`; `POST /movimientos` (farmacia, almacén)
- `GET /usuarios`, `POST /usuarios` (solo admin); `GET /servicios`
- `POST /chat`

Validación de entrada con modelos Pydantic (mensaje no vacío y de longitud limitada, cantidad > 0, etc.). Errores 401/403/404/422 con mensajes claros.

## 8. Frontend

- Pantalla de login → interfaz según rol.
- Encabezado "IPS Centro de Salud — Asistente Virtual"; menú lateral (Inicio, Chat, Medicamentos, Inventario, Movimientos, Vencimientos, Usuarios) filtrado por rol.
- Chat con burbujas, sugerencias de preguntas según rol y respuesta con formato de lista.
- Vistas de tabla simples para Medicamentos/Inventario/Movimientos/Vencimientos; formulario de movimiento; lista y alta de usuarios (admin).
- Paleta azul/verde clínico, tipografía legible, responsive para computador.
- El menú solo oculta opciones; la seguridad real está en el backend.

## 9. Pruebas

`pytest` contra una BD de prueba con los datos ficticios:
- Un test por cada una de las 15 preguntas (admin, farmacia, almacén) verificando las cifras esperadas.
- Variantes de redacción que mapean a la misma intención.
- Rechazo por rol (403 en API, mensaje de rol en chat).
- Pregunta no reconocida, login inválido, movimiento inválido (stock negativo).

## 10. Fuera de alcance

Microservicios, Kubernetes, nube, IA de pago, datos clínicos reales, integraciones con sistemas de salud, historial de conversaciones persistente.

## 11. Etapas de implementación

1 Estructura · 2 BD · 3 Backend/endpoints · 4 Usuarios y roles · 5 Chatbot · 6 Frontend · 7 Integración · 8 Pruebas · 9 README.
