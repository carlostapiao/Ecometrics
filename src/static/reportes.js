(() => {
 const tipo = document.getElementById("id_tipo");
 const estado = document.getElementById("id_estado");
 const nota = document.getElementById("criterio-fecha");
 if (!tipo || !estado) return;
 function actualizar() {
   const generacion = tipo.value === "generacion";
   estado.closest(".campo-estado").hidden = generacion;
   estado.disabled = generacion;
   if (generacion) estado.value = "";
   const textos = {
     generacion: "Las fechas filtran la generación del residuo.",
     retiros: "Las fechas filtran la salida. La recepción muestra el dato actual, aunque corresponda a otro periodo.",
     recepciones: "Las fechas filtran la recepción. Solo se incluyen retiros con peso y fecha de recepción registrados."
   };
   if (nota) nota.textContent = textos[tipo.value] || textos.generacion;
 }
 tipo.addEventListener("change", actualizar);
 actualizar();
})();
