// Crea elementos DOM de forma segura (los textos nunca se interpretan como HTML).
function el(tag, props = {}, ...hijos) {
  const nodo = document.createElement(tag);
  for (const [clave, valor] of Object.entries(props)) {
    if (clave === "class") nodo.className = valor;
    else if (clave.startsWith("on")) nodo.addEventListener(clave.slice(2), valor);
    else nodo.setAttribute(clave, valor);
  }
  for (const hijo of hijos.flat()) nodo.append(hijo instanceof Node ? hijo : String(hijo ?? ""));
  return nodo;
}

function fechaCorta(iso) {
  const [anio, mes, dia] = String(iso).slice(0, 10).split("-");
  return `${dia}/${mes}/${anio}`;
}

function insignia(texto, tipo) {
  return el("span", { class: `insignia ${tipo}` }, texto);
}

function tabla(columnas, filas) {
  if (filas.length === 0) return el("p", {}, "No hay datos para mostrar.");
  return el(
    "table",
    {},
    el("thead", {}, el("tr", {}, columnas.map((c) => el("th", {}, c)))),
    el("tbody", {}, filas.map((fila) => el("tr", {}, fila.map((celda) => el("td", {}, celda)))))
  );
}
