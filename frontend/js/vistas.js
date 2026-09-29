const DESCRIPCION_ROL = {
  ADMINISTRADOR: "Puedes consultar información general, reportes de movimientos y administrar usuarios.",
  FARMACIA: "Puedes revisar inventario, vencimientos y controlar entradas y salidas de medicamentos.",
  ALMACENISTA: "Puedes consultar existencias y ubicaciones, y registrar entradas y salidas.",
};

function encabezadoVista(titulo) {
  return el("h2", {}, titulo);
}

function vistaInicio(usuario) {
  return el(
    "div",
    {},
    encabezadoVista(`Hola, ${usuario.nombre}`),
    el(
      "div",
      { class: "tarjeta" },
      el("p", {}, DESCRIPCION_ROL[usuario.rol]),
      el("p", {}, "Usa el menú de la izquierda o pregúntale al asistente virtual."),
      el("button", { class: "boton", type: "button", onclick: () => mostrar("chat") }, "Ir al chat")
    )
  );
}

async function vistaMedicamentos() {
  const meds = await Api.pedir("/medicamentos");
  return el(
    "div",
    {},
    encabezadoVista("Medicamentos"),
    tabla(
      ["Nombre", "Principio activo", "Presentación", "Ubicación"],
      meds.map((m) => [m.nombre, m.principio_activo, m.presentacion, m.ubicacion])
    )
  );
}

async function vistaInventario() {
  const meds = await Api.pedir("/medicamentos");
  return el(
    "div",
    {},
    encabezadoVista("Inventario"),
    tabla(
      ["Medicamento", "Cantidad actual", "Stock mínimo", "Estado"],
      meds.map((m) => [
        m.nombre,
        m.cantidad_actual,
        m.stock_minimo,
        m.cantidad_actual < m.stock_minimo ? insignia("Stock bajo", "alerta") : insignia("Normal", "ok"),
      ])
    )
  );
}

async function vistaVencimientos() {
  const meds = await Api.pedir("/medicamentos/proximos-vencer");
  return el(
    "div",
    {},
    encabezadoVista("Próximos a vencer (30 días)"),
    tabla(
      ["Medicamento", "Vence", "Días restantes", "Cantidad", "Ubicación"],
      meds.map((m) => [m.nombre, fechaCorta(m.fecha_vencimiento), m.dias_restantes, m.cantidad_actual, m.ubicacion])
    )
  );
}

function formularioMovimiento(meds) {
  const medicamento = el("select", { required: "" }, meds.map((m) => el("option", { value: m.id }, m.nombre)));
  const tipo = el("select", {}, el("option", { value: "ENTRADA" }, "Entrada"), el("option", { value: "SALIDA" }, "Salida"));
  const cantidad = el("input", { type: "number", min: "1", max: "100000", required: "", placeholder: "Cantidad" });
  const mensaje = el("p", { class: "error", role: "status" });

  async function enviar(evento) {
    evento.preventDefault();
    try {
      await Api.pedir("/movimientos", {
        method: "POST",
        body: JSON.stringify({ medicamento_id: Number(medicamento.value), tipo: tipo.value, cantidad: Number(cantidad.value) }),
      });
      mostrar("movimientos");
    } catch (error) {
      mensaje.textContent = error.message;
    }
  }

  return el(
    "form",
    { class: "tarjeta formulario-linea", onsubmit: enviar },
    el("label", {}, "Medicamento", medicamento),
    el("label", {}, "Tipo", tipo),
    el("label", {}, "Cantidad", cantidad),
    el("button", { class: "boton", type: "submit" }, "Registrar"),
    mensaje
  );
}

async function vistaMovimientos(usuario) {
  const [movs, meds] = await Promise.all([Api.pedir("/movimientos"), Api.pedir("/medicamentos")]);
  const contenedor = el("div", {}, encabezadoVista("Movimientos"));
  if (usuario.rol !== "ADMINISTRADOR") contenedor.append(formularioMovimiento(meds));
  contenedor.append(
    tabla(
      ["Fecha", "Medicamento", "Tipo", "Cantidad", "Responsable"],
      movs.map((m) => [
        fechaCorta(m.fecha),
        m.medicamento,
        insignia(m.tipo === "ENTRADA" ? "Entrada" : "Salida", m.tipo === "ENTRADA" ? "ok" : "alerta"),
        m.cantidad,
        m.usuario,
      ])
    )
  );
  return contenedor;
}

async function vistaUsuarios() {
  const usuarios = await Api.pedir("/usuarios");
  const nombre = el("input", { required: "", maxlength: "100" });
  const login = el("input", { required: "", pattern: "[a-z0-9_]{3,30}", title: "3 a 30 letras minúsculas, números o _" });
  const clave = el("input", { type: "password", required: "", minlength: "8", maxlength: "72" });
  const rol = el(
    "select",
    {},
    el("option", { value: "FARMACIA" }, "Responsable de farmacia"),
    el("option", { value: "ALMACENISTA" }, "Almacenista"),
    el("option", { value: "ADMINISTRADOR" }, "Administrador")
  );
  const mensaje = el("p", { class: "error", role: "status" });

  async function crear(evento) {
    evento.preventDefault();
    try {
      await Api.pedir("/usuarios", {
        method: "POST",
        body: JSON.stringify({ nombre: nombre.value, usuario: login.value, password: clave.value, rol: rol.value }),
      });
      mostrar("usuarios");
    } catch (error) {
      mensaje.textContent = error.message;
    }
  }

  return el(
    "div",
    {},
    encabezadoVista("Usuarios"),
    el(
      "form",
      { class: "tarjeta formulario-linea", onsubmit: crear },
      el("label", {}, "Nombre", nombre),
      el("label", {}, "Usuario", login),
      el("label", {}, "Contraseña", clave),
      el("label", {}, "Rol", rol),
      el("button", { class: "boton", type: "submit" }, "Crear usuario"),
      mensaje
    ),
    tabla(["Nombre", "Usuario", "Rol", "Estado"], usuarios.map((u) => [u.nombre, u.usuario, u.rol, u.estado]))
  );
}
