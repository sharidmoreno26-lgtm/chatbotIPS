const SUGERENCIAS = {
  ADMINISTRADOR: [
    "¿Cuántos medicamentos tenemos registrados actualmente?",
    "¿Cuáles son los medicamentos que están por debajo del mínimo establecido?",
    "¿Qué medicamentos están próximos a vencer durante los próximos 30 días?",
    "¿Cuántas entradas y salidas de medicamentos se registraron durante este mes?",
    "¿Qué medicamento tiene mayor movimiento durante este mes?",
  ],
  FARMACIA: [
    "¿Cuántas unidades hay disponibles de acetaminofén?",
    "¿Cuáles son los medicamentos que están por debajo del mínimo establecido?",
    "¿Qué medicamentos están próximos a vencer?",
    "¿Cuántas unidades de acetaminofén ingresaron durante este mes?",
    "¿Cuántas unidades de acetaminofén salieron durante este mes?",
  ],
  ALMACENISTA: [
    "¿Dónde está ubicada la insulina?",
    "¿Cuántas unidades hay disponibles de insulina?",
    "¿Cuándo fue registrada la última entrada de acetaminofén?",
    "¿Cuándo fue registrada la última salida de acetaminofén?",
    "¿Qué medicamentos debo revisar por vencimiento?",
  ],
};

function vistaChat(usuario) {
  const mensajes = el("div", { class: "mensajes", "aria-live": "polite" });
  const entrada = el("input", { type: "text", placeholder: "Escribe tu pregunta...", maxlength: "500", required: "", autocomplete: "off" });

  function agregar(quien, texto) {
    mensajes.append(
      el(
        "div",
        { class: `burbuja ${quien}` },
        el("span", { class: "quien" }, quien === "bot" ? "🤖 Asistente IPS" : "👤 Tú"),
        el("div", { class: "texto" }, texto)
      )
    );
    mensajes.scrollTop = mensajes.scrollHeight;
  }

  async function enviar(texto) {
    texto = texto.trim();
    if (!texto) return;
    agregar("usuario", texto);
    entrada.value = "";
    try {
      const datos = await Api.pedir("/chat", { method: "POST", body: JSON.stringify({ mensaje: texto }) });
      agregar("bot", datos.respuesta);
    } catch (error) {
      agregar("bot", `No pude completar la consulta: ${error.message}`);
    }
  }

  agregar("bot", "Hola, ¿en qué puedo ayudarte?");

  return el(
    "div",
    { class: "chat" },
    encabezadoVista("Chat"),
    mensajes,
    el(
      "div",
      { class: "sugerencias" },
      SUGERENCIAS[usuario.rol].map((s) => el("button", { type: "button", onclick: () => enviar(s) }, s))
    ),
    el(
      "form",
      { class: "entrada-chat", onsubmit: (evento) => { evento.preventDefault(); enviar(entrada.value); } },
      entrada,
      el("button", { class: "boton", type: "submit" }, "Enviar")
    )
  );
}
