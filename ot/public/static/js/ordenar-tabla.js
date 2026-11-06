// Orden por columna en el cliente, para listados que ya vienen completos.
// Contrato: contenedor [data-ordenable]; títulos .th-orden[data-orden=k]
// (data-tipo="n" numérico, "t" texto); filas [data-fila] con data-o-k="valor".
// Click: mayor→menor, de nuevo: menor→mayor, de nuevo: orden original del
// server (más nuevas arriba). Los vacíos quedan siempre al final.
(function () {
  document.querySelectorAll("[data-ordenable]").forEach(function (cont) {
    var filas = Array.prototype.slice.call(cont.querySelectorAll("[data-fila]"));
    filas.forEach(function (f, i) { f._i = i; });
    var estado = { k: null, dir: "desc" };

    function valor(f, k, tipo) {
      var v = f.getAttribute("data-o-" + k);
      if (v === null || v === "") return null;
      if (tipo === "n") { var n = parseFloat(v); return isNaN(n) ? null : n; }
      return v.toLowerCase();
    }

    function aplicar() {
      var th = estado.k && cont.querySelector('.th-orden[data-orden="' + estado.k + '"]');
      var tipo = th ? th.getAttribute("data-tipo") || "t" : "t";
      var k = estado.k, sign = estado.dir === "asc" ? 1 : -1;
      var lista = filas.slice().sort(function (a, b) {
        if (!k) return a._i - b._i;
        var va = valor(a, k, tipo), vb = valor(b, k, tipo);
        if (va === null && vb === null) return a._i - b._i;
        if (va === null) return 1;
        if (vb === null) return -1;
        if (va < vb) return -sign;
        if (va > vb) return sign;
        return a._i - b._i;
      });
      lista.forEach(function (f) { f.parentNode.appendChild(f); });
      cont.querySelectorAll(".th-orden").forEach(function (h) {
        var activo = h.getAttribute("data-orden") === k;
        h.classList.toggle("is-orden", activo);
        h.setAttribute("aria-sort", activo ? (estado.dir === "asc" ? "ascending" : "descending") : "none");
        var fl = h.querySelector(".th-orden__flecha");
        if (fl) fl.textContent = activo ? (estado.dir === "asc" ? "▲" : "▼") : "";
      });
    }

    function click(th) {
      var k = th.getAttribute("data-orden");
      if (estado.k !== k) { estado.k = k; estado.dir = "desc"; }
      else if (estado.dir === "desc") { estado.dir = "asc"; }
      else { estado.k = null; estado.dir = "desc"; }
      aplicar();
    }

    cont.addEventListener("click", function (e) {
      var th = e.target.closest(".th-orden");
      if (th) click(th);
    });
    cont.addEventListener("keydown", function (e) {
      var th = e.target.closest(".th-orden");
      if (th && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); click(th); }
    });
  });
})();
