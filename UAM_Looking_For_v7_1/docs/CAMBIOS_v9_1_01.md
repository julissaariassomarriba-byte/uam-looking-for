# UAM Looking For v9.1.01 · Limpiar el historial, ocultar entregados y diseño más limpio

La v9.1.01 parte de la v9 y agrega tres cosas:

1. El administrador puede **limpiar el historial** (único cambio en la base de datos).
2. Los objetos **entregados o devueltos se ocultan del catálogo** después de unos días (sin cambios en la base).
3. Un **diseño más limpio** en todo el programa (sin cambios en la base).

Las reglas, las validaciones y las otras siete tablas quedan igual que en la v9.

# 1. Limpiar el historial

## Qué hace

En la página **Historial**, el administrador ve una sección nueva, «Limpiar historial», con dos opciones:

| Opción | Qué borra |
|---|---|
| Solo los movimientos anteriores a una fecha | Los movimientos registrados antes de ese día |
| Todo el historial | Todos los movimientos |

- Hay que marcar una casilla de confirmación, porque no se puede deshacer. Se recomienda descargar antes el PDF.
- Solo se borran **movimientos del historial**. Los objetos, entregas, reclamaciones, devoluciones y reportes de
  visitantes no se tocan.
- Los movimientos nuevos se siguen anotando como siempre.
- Debajo del formulario se ven las últimas limpiezas: cuándo, quién, qué rango y cuántos movimientos se borraron.
- El encargado no ve la sección; si intenta limpiar igual, se rechaza.

## Base de datos (limpieza del historial)

| | v9 | v9.1.01 |
|---|---|---|
| Tablas | 7 | 8 (+ `limpiezas_historial`) |
| Llaves foráneas | 15 | 16 |
| Índices | 12 | 13 (+ `uq_limpieza_en_curso`) |
| Triggers | 26 | 29 |

**`limpiezas_historial`** (id, usuario_id, antes_de, estado, filas_borradas, fecha_hora) cumple dos funciones:

1. **Permiso.** El historial sigue sin poder borrarse, salvo mientras exista una limpieza «En curso». Por eso
   se reemplazó `trg_historial_sin_borrar`: ahora deja borrar solo dentro de esa limpieza y solo lo que está en su
   rango.
2. **Bitácora.** Al terminar, la limpieza queda «Hecha» con el número de filas borradas, y ya no se puede
   modificar ni borrar.

La app abre la limpieza, borra y la cierra en una sola transacción: si algo falla, no se borra nada y nunca queda
una limpieza abierta.

Triggers nuevos:

| Trigger | Regla |
|---|---|
| `trg_limpieza_valida` | Solo el administrador activo abre una limpieza, y empieza «En curso» |
| `trg_limpieza_cerrar` | Una limpieza solo pasa de «En curso» a «Hecha» una vez, y lo registrado no cambia |
| `trg_limpiezas_sin_borrar` | La bitácora de limpiezas no se borra |

El índice único parcial `uq_limpieza_en_curso` impide que haya dos limpiezas abiertas a la vez.

Una base v9 con datos se actualiza sola al iniciar: se agrega la tabla y se reemplaza el trigger. Los datos no cambian.

# 2. Objetos entregados que se ocultan del catálogo

Un objeto que ya salió de la oficina (Entregado o Devuelto) sigue en el catálogo **5 días** y después deja de
mostrarse. El plazo se cambia en el `.env` con `DIAS_OCULTAR` (de 3 a 7; si falta o no es válido, 5).

- **No se borra nada.** El objeto, su entrega, sus reclamaciones y su historial siguen completos.
- **No cambia la base.** No hay columna «oculto»: cada consulta lo calcula con la fecha de la entrega (o de la
  devolución) más el plazo. Por eso cambiar `DIAS_OCULTAR` surte efecto de inmediato.
- **Con una reclamación pendiente no se oculta**, aunque el plazo haya pasado.
- **Estudiantes:** ya no lo ven en el catálogo ni lo abren por la dirección directa, y ya no pueden reclamarlo
  («El plazo para reclamar este objeto ya terminó»). Quien ya lo había reclamado sí puede seguir viéndolo.
- **Personal:** el catálogo tiene una pestaña **«Ocultos»**; el catálogo y el panel del administrador avisan cuántos
  objetos se ocultaron; la ficha dice cuándo se ocultará o desde cuándo está oculto. El historial y el PDF siguen
  incluyendo todos los objetos.

# 3. Diseño más limpio

Mismos colores, tipografía y distribución que la v9, con acabados más cuidados:

- **Panel de administración:** tarjetas con cifras, reclamaciones pendientes, objetos por estado en barras y actividad
  reciente, cada bloque con enlace a su pantalla.
- **Cuentas:** el formulario «Nueva cuenta» queda plegado; filtros por rol con contador, buscador, iniciales de color por
  rol y acciones compactas. En el celular, la tabla se vuelve tarjetas.
- **Catálogo, ficha, historial, reclamaciones y reportes de visitantes:** títulos con subtítulo, tarjetas de cifras
  uniformes y avisos más claros.
- Todo se revisó en computadora y en celular, sin desplazamiento horizontal.

# Archivos cambiados

| Archivo | Cambio |
|---|---|
| `schema.sql` | Tabla, índice y 3 triggers nuevos; `trg_historial_sin_borrar` reemplazado |
| `uam/datos/objetos.py` | `contar_historial`, `limpiar_historial`, `listar_limpiezas` |
| `uam/servicios/historial.py` | Nuevo: reglas de la limpieza (solo admin, rango, fecha válida, confirmación) |
| `uam/rutas/objetos.py` | Ruta `POST /historial/limpiar` |
| `templates/objetos/historial.html` | Sección «Limpiar historial» (solo el administrador) y diseño |
| `uam/datos/objetos.py` (plazo) | Cálculo de «oculto» en las consultas, `contar_ocultos`, `configurar_plazo` |
| `uam/rutas/objetos.py`, `uam/servicios/reclamaciones.py`, `uam/__init__.py` | Pestaña «Ocultos», 404 y reclamo cerrado para ocultos, plazo desde el `.env`, avisos |
| `uam/rutas/admin.py` | Contadores por rol en «Cuentas» |
| `templates/base.html`, `admin/*`, `objetos/index.html`, `objetos/detalle.html`, `reclamaciones/*`, `visitantes/reportes_visitantes.html` | Diseño más limpio y avisos del plazo |
| `static/css/styles.css` | Estilos del nuevo diseño y de la limpieza |
| `.env.example` | `DIAS_OCULTAR=5` |
| `base_de_datos/UAM_Looking_For_BD_v9_1_01.*` | Diagrama actualizado (reemplaza al de la v8.5) |
| `tests/probar_app.py`, `base_de_datos/probar_bd.py` | Pruebas nuevas y conteos actualizados |

## Pruebas

| Prueba | Resultado |
|---|---|
| `tests/probar_app.py` sin argumentos | **257/257** |
| `tests/probar_app.py` + migración desde v6.2 y actualización desde v8.5 | **278/278** |
| `base_de_datos/probar_bd.py` | **135/135** (97 negativas) |
| Navegador real (computadora y celular) | Panel, cuentas, catálogo, ocultos, ficha e historial se ven bien; sin desplazamiento horizontal; un objeto oculto da 404 al estudiante |

Las 19 pruebas de la limpieza cubren: quién ve la sección, el encargado rechazado, sin confirmar, fecha inválida, rango vacío,
limpieza por fecha (borra solo lo anterior), limpieza total, la bitácora, que los objetos no se tocan, que lo nuevo se
sigue anotando, y cuatro intentos de saltarse la app directo en la base.

Las 18 pruebas del plazo cubren: el rango 3–7 de `DIAS_OCULTAR`, que recién entregado se sigue viendo, que al cumplirse
el plazo desaparece para el estudiante (también por la dirección directa) y ya no se puede reclamar, que una reclamación
pendiente lo mantiene visible, la pestaña «Ocultos» solo para el personal, los avisos, que el historial y el PDF lo
siguen incluyendo y que el objeto queda completo en la base.
