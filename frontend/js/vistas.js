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

let avisoMovimientos = "";

function hoyISO(desfaseDias = 0) {
  const d = new Date();
  d.setDate(d.getDate() + desfaseDias);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

function formularioSalida(meds) {
  const medicamento = el("select", { required: "" }, meds.map((m) => el("option", { value: m.id }, m.nombre)));
  const cantidad = el("input", { type: "number", min: "1", max: "100000", required: "", placeholder: "Cantidad" });
  const mensaje = el("p", { class: "error", role: "status" });
  const boton = el("button", { class: "boton", type: "submit" }, "Registrar salida");

  async function enviar(evento) {
    evento.preventDefault();
    mensaje.textContent = "";
    boton.disabled = true;
    try {
      await Api.pedir("/movimientos", {
        method: "POST",
        body: JSON.stringify({ medicamento_id: Number(medicamento.value), tipo: "SALIDA", cantidad: Number(cantidad.value) }),
      });
      avisoMovimientos = "Salida registrada correctamente.";
      mostrar("movimientos");
    } catch (error) {
      mensaje.textContent = error.message;
      boton.disabled = false;
    }
  }

  return el(
    "form",
    { class: "tarjeta formulario-linea", onsubmit: enviar },
    el("label", {}, "Medicamento", medicamento),
    el("label", {}, "Cantidad", cantidad),
    boton,
    mensaje
  );
}

function formularioIngreso(meds, usuario) {
  const medicamento = el(
    "select",
    { required: "" },
    meds.map((m) => el("option", { value: m.id }, m.nombre)),
    el("option", { value: "nuevo" }, "➕ Nuevo medicamento")
  );
  const nombre = el("input", { maxlength: "80", placeholder: "Nombre" });
  const principio = el("input", { maxlength: "80", placeholder: "Principio activo" });
  const presentacion = el("input", { maxlength: "60", placeholder: "Presentación (ej. Tabletas 500 mg)" });
  const stockMinimo = el("input", { type: "number", min: "0", max: "100000", placeholder: "Stock mínimo" });
  const ubicacion = el("input", { maxlength: "60", placeholder: "Ubicación (ej. Estante A1)" });
  const camposNuevo = [nombre, principio, presentacion, stockMinimo, ubicacion];
  const bloqueNuevo = el(
    "div",
    { class: "bloque-nuevo", hidden: "" },
    el("label", {}, "Nombre", nombre),
    el("label", {}, "Principio activo", principio),
    el("label", {}, "Presentación", presentacion),
    el("label", {}, "Stock mínimo", stockMinimo),
    el("label", {}, "Ubicación", ubicacion)
  );
  const cantidad = el("input", { type: "number", min: "1", max: "100000", required: "", placeholder: "Cantidad ingresada" });
  const lote = el("input", {
    required: "",
    maxlength: "40",
    pattern: "[A-Za-z0-9._\\/\\-]+",
    title: "Letras, números y . _ / -",
    placeholder: "Número de lote",
  });
  const hoy = hoyISO();
  const vencimiento = el("input", { type: "date", required: "", min: hoy });
  const ingreso = el("input", { type: "date", required: "", min: hoyISO(-365), max: hoy, value: hoy });
  const responsable = el("input", { readonly: "", value: usuario.nombre });
  const mensaje = el("p", { class: "error", role: "status" });
  const boton = el("button", { class: "boton", type: "submit" }, "Guardar ingreso");

  medicamento.addEventListener("change", () => {
    const esNuevo = medicamento.value === "nuevo";
    bloqueNuevo.hidden = !esNuevo;
    camposNuevo.forEach((campo) => (campo.required = esNuevo));
  });

  async function enviar(evento) {
    evento.preventDefault();
    mensaje.textContent = "";
    if (vencimiento.value <= ingreso.value) {
      mensaje.textContent = "La fecha de vencimiento debe ser posterior a la fecha de ingreso.";
      return;
    }
    const cuerpo = {
      cantidad: Number(cantidad.value),
      lote: lote.value.trim(),
      fecha_vencimiento: vencimiento.value,
      fecha_ingreso: ingreso.value,
    };
    if (medicamento.value === "nuevo") {
      cuerpo.nuevo_medicamento = {
        nombre: nombre.value.trim(),
        principio_activo: principio.value.trim(),
        presentacion: presentacion.value.trim(),
        stock_minimo: Number(stockMinimo.value),
        ubicacion: ubicacion.value.trim(),
      };
    } else {
      cuerpo.medicamento_id = Number(medicamento.value);
    }
    boton.disabled = true;
    try {
      const datos = await Api.pedir("/ingresos", { method: "POST", body: JSON.stringify(cuerpo) });
      avisoMovimientos = `Ingreso registrado. Cantidad disponible: ${datos.cantidad_actual}.`;
      mostrar("movimientos");
    } catch (error) {
      mensaje.textContent = error.message;
      boton.disabled = false;
    }
  }

  return el(
    "form",
    { class: "tarjeta formulario-linea", onsubmit: enviar },
    el("label", {}, "Medicamento", medicamento),
    bloqueNuevo,
    el("label", {}, "Cantidad ingresada", cantidad),
    el("label", {}, "Número de lote", lote),
    el("label", {}, "Fecha de vencimiento", vencimiento),
    el("label", {}, "Fecha de ingreso", ingreso),
    el("label", {}, "Responsable del ingreso", responsable),
    boton,
    mensaje
  );
}

async function vistaMovimientos(usuario) {
  const [movs, meds] = await Promise.all([Api.pedir("/movimientos"), Api.pedir("/medicamentos")]);
  const contenedor = el("div", {}, encabezadoVista("Movimientos"));
  const aviso = avisoMovimientos;
  avisoMovimientos = "";
  if (aviso) contenedor.append(el("p", { class: "aviso", role: "status" }, aviso));
  if (usuario.rol !== "ADMINISTRADOR") {
    const panel = el("div");
    const botonIngreso = el("button", { class: "boton boton-secundario", type: "button" }, "Ingreso de medicamentos");
    const botonSalida = el("button", { class: "boton boton-secundario", type: "button" }, "Registrar salida");
    const abrir = (boton, formulario) => {
      [botonIngreso, botonSalida].forEach((b) => b.classList.toggle("activo", b === boton));
      panel.replaceChildren(formulario);
    };
    botonIngreso.addEventListener("click", () => abrir(botonIngreso, formularioIngreso(meds, usuario)));
    botonSalida.addEventListener("click", () => abrir(botonSalida, formularioSalida(meds)));
    contenedor.append(el("div", { class: "acciones-movimiento" }, botonIngreso, botonSalida), panel);
  }
  contenedor.append(
    tabla(
      ["Fecha", "Medicamento", "Tipo", "Cantidad", "Lote", "Vence", "Responsable"],
      movs.map((m) => [
        fechaCorta(m.fecha),
        m.medicamento,
        insignia(m.tipo === "ENTRADA" ? "Entrada" : "Salida", m.tipo === "ENTRADA" ? "ok" : "alerta"),
        m.cantidad,
        m.lote ?? "—",
        m.fecha_vencimiento ? fechaCorta(m.fecha_vencimiento) : "—",
        m.usuario,
      ])
    )
  );
  return contenedor;
}

async function vistaUsuarios(usuarioActual) {
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

  async function eliminar(u) {
    if (!confirm("¿Está seguro de que desea eliminar este usuario?")) return;
    try {
      await Api.pedir(`/usuarios/${u.id}`, { method: "DELETE" });
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
    tabla(
      ["Nombre", "Usuario", "Rol", "Estado", "Acciones"],
      usuarios.map((u) => [
        u.nombre,
        u.usuario,
        u.rol,
        u.estado,
        u.usuario === usuarioActual.usuario
          ? "—"
          : el("button", { class: "boton boton-peligro", type: "button", onclick: () => eliminar(u) }, "Eliminar"),
      ])
    )
  );
}
