# UAM Looking For v10 · Versión definitiva

La v10 parte de la v9.1.01 (la publicada) y la completa para cumplir los requerimientos funcionales del documento
del SGOP. Se mantuvo todo lo demás igual: mismas pantallas, mismas reglas, mismo diseño (con mejoras en lo nuevo) y
**la misma base de datos**: `schema.sql` es idéntico, byte por byte, al de la v9.1.01.

Los requerimientos que ya estaban resueltos con otra solución (por ejemplo, el reporte en PDF en lugar de Excel) no
se rehicieron: se dejan como están para no duplicar funciones.

## Cumplimiento de los requerimientos funcionales

| ID | Requerimiento | v9.1.01 | v10 | Cómo |
|---|---|---|---|---|
| RF-01 | Iniciar sesión con CIF y contraseña | 🔄 | 🔄 | CIF y contraseña propia del sistema |
| RF-02 | Inicio de sesión del administrador | ✅ | ✅ | /admin |
| RF-03 | Rol automático | ✅ | ✅ | — |
| RF-04 | Gestionar personal autorizado | 🔄 | 🔄 | Cuentas de Encargado |
| RF-05 | Perfil del estudiante | 🟡 | ✅ | **Nuevo:** el registro pide la carrera y hay una página «Mi perfil» |
| RF-06 | Registrar objeto encontrado | 🔄 | 🔄 | Color, marca y condiciones en la descripción |
| RF-07 | Separar información pública y de validación | ✅ | ✅ | — |
| RF-08 | Corregir o despublicar; categorías y zonas | 🟡 | 🟡 | Ver «Lo que no se pudo sin cambiar la base» |
| RF-09 | Catálogo sin datos de validación | ✅ | ✅ | — |
| RF-10 | Buscar y filtrar por categoría, zona, fecha y palabra clave | 🟡 | ✅ | **Nuevo:** buscador y filtro por mes |
| RF-11 | Procedimiento, ubicación y horario | 🟡 | ✅ | **Nuevo:** sección «Dónde y cuándo» en la guía |
| RF-12 | Registrar la entrega con confirmación | 🔄 | 🔄 | **Nuevo:** comprobante para imprimir con firmas |
| RF-13 | Marcar entregado y despublicar | 🔄 | 🔄 | Se oculta a los 5 días |
| RF-14 | Comprobante de entrega por correo | ❌ | ✅ | **Nuevo:** envío por correo (SMTP del `.env`) |
| RF-15 | Ciclo de vida con Donado y Descartado | 🟡 | 🟡 | Ver «Lo que no se pudo sin cambiar la base» |
| RF-16 | Plazos en oficina y bodega, vencimiento y alerta a 3 días | 🟡 | ✅ | **Nuevo:** plazos de custodia calculados |
| RF-17 | Traslados a bodega | 🔄 | 🔄 | Uno por uno, con fecha y responsable en el historial |
| RF-18 | Panel con estados, reclamos y próximos a vencer | 🟡 | ✅ | **Nuevo:** bloque «Plazos de custodia» y actualización cada minuto |
| RF-19 | Búsqueda del personal | 🟡 | ✅ | **Nuevo:** código, CIF, carrera, fechas y estado; reportes por nombre o teléfono |
| RF-20 | Exportar reportes | 🔄 | 🔄 | PDF del historial |

**Resultado:** 11 se cumplen tal como están escritos, 7 con otra solución y 2 en parte (por la base de datos).

## Qué se agregó

### Mi perfil (RF-05)
- El registro de estudiantes pide la **carrera** (obligatoria).
- Página **«Mi perfil»** (`/perfil`, al tocar el nombre en el menú): muestra nombre, CIF, carrera, correo y teléfono.
- Se pueden corregir el correo, la carrera y el teléfono, y cambiar la contraseña (pide la actual).
- El nombre y el CIF no se editan aquí porque son la identidad; los corrige el administrador.
- El administrador ve su perfil, pero sus datos y su contraseña se cambian en el `.env`.

### Búsqueda y filtros (RF-10 y RF-19)
- **Estudiante:** palabra clave (busca solo en el nombre, la descripción pública y la categoría) y filtro por mes.
  Nunca busca en la descripción interna: así no se puede «adivinar» un dato de validación.
- **Personal:** palabra clave también en la descripción interna y el lugar del hallazgo; por código (`#12` o `12`); por
  nombre, CIF o carrera de quien trajo o retiró el objeto; por rango de fechas y por estado.
- Elegir una categoría o una ubicación conserva la búsqueda.
- `%` y `_` se buscan como letras, no como comodines.
- **Reportes de visitantes:** se buscan por código, nombre, teléfono u objeto perdido.

### Guía: dónde y cuándo (RF-11)
- Nueva sección con los lugares donde se guardan los objetos y el horario de atención (`HORARIO_ATENCION` del `.env`).
- Nueva sección «Encontré algo» con los pasos para entregar un objeto encontrado.

### Comprobante de entrega (RF-12 y RF-14)
- Desde la ficha de un objeto entregado: **«Comprobante para imprimir»** abre una página lista para imprimir con el
  código, el objeto, quién lo retira (nombre, tipo, CIF o cédula, carrera, teléfono), la fecha y hora, quién lo
  entrega y **dos líneas de firma**. Al imprimir se ocultan el menú y los botones.
- **«Enviar por correo»** manda el mismo comprobante al correo de quien lo retiró (o al que se escriba).
- El comprobante **no lleva las señas ni la descripción interna**: puede reenviarse, y esos datos prueban quién es el dueño.
- El correo usa `smtplib` (viene con Python). Se configura en el `.env` (`SMTP_SERVIDOR`, `SMTP_PUERTO`,
  `SMTP_USUARIO`, `SMTP_CONTRASENA`, `SMTP_REMITENTE`). Sin esos datos, el sistema lo dice y sugiere imprimir.

### Plazos de custodia (RF-16 y RF-18)
- Cada objeto bajo custodia tiene una **fecha de vencimiento calculada** (no se guarda; no cambia la base):
  - En oficina (Activo o En resguardo): `PLAZO_OFICINA_DIAS` desde la fecha del hallazgo.
  - En bodega: `PLAZO_BODEGA_DIAS` desde que entró a bodega (según el historial).
- **Aviso a 3 días:** las tarjetas del catálogo del personal dicen «Vence en N días» o «Plazo vencido»; la ficha
  explica el plazo; hay una pestaña **«Por vencer»** (primero lo vencido).
- **Panel del administrador:** bloque «Plazos de custodia» con los objetos por vencer, y la página se actualiza sola cada minuto.
- El estudiante no ve los plazos: son información interna.

### Diseño
- Buscador integrado en el catálogo, avisos de plazo con colores (ámbar por vencer, rojo vencido), comprobante con
  formato de documento, página de perfil y sección «Dónde y cuándo» en la guía.
- El nombre del usuario en el menú ahora lleva a «Mi perfil».
- Pie de página: «Proyecto final de Programación Estructurada».
- Revisado en computadora y celular (390 px), sin desplazamiento horizontal.

## Lo que no se pudo sin cambiar la base

La base revisa con `CHECK` las listas cerradas de estados, categorías y ubicaciones. Cambiarlas exige modificar
`schema.sql`, y en esta versión la base no se tocó.

| ID | Qué falta | Qué haría falta |
|---|---|---|
| RF-15 | Estados «Donado» y «Descartado» | Agregarlos al `CHECK` de `objetos.estado` y a los triggers de estado |
| RF-08 | Agregar o editar categorías y zonas desde la aplicación | Una tabla de categorías y otra de zonas en lugar de los `CHECK` |
| RF-08 | Despublicar un objeto a mano | Una columna para marcarlo (hoy se despublica solo, al cumplir su plazo) |

Mientras tanto, cuando un plazo de custodia vence, la ficha indica «Decide con la oficina si pasa a bodega, se dona
o se descarta».

## Decisiones pendientes (no se inventaron reglas)

| Tema | Valor puesto | Por qué es pendiente |
|---|---|---|
| Plazo en oficina | 30 días (`PLAZO_OFICINA_DIAS`) | El documento pide que sea configurable, pero no da el número. Es **provisional** |
| Plazo en bodega | 60 días (`PLAZO_BODEGA_DIAS`) | Igual: **provisional** hasta que la oficina lo defina |
| Horario de atención | Vacío (`HORARIO_ATENCION`) | Falta el horario oficial. Si se deja vacío, la guía no lo muestra |
| Cuenta de correo | Sin configurar | Hace falta una cuenta de correo de la oficina para enviar comprobantes |

## Archivos cambiados

| Archivo | Cambio |
|---|---|
| `uam/datos/objetos.py` | Búsqueda y filtros, plazos de custodia calculados, meses con objetos |
| `uam/datos/usuarios.py`, `uam/datos/reclamaciones.py`, `uam/datos/visitantes.py` | Actualizar perfil, datos del comprobante, búsqueda de reportes |
| `uam/servicios/cuentas.py` | Carrera en el registro, actualizar perfil y cambiar contraseña |
| `uam/servicios/comprobantes.py`, `uam/utilidades/correo.py` | Nuevos: comprobante y envío por correo |
| `uam/rutas/objetos.py`, `acceso.py`, `admin.py`, `visitantes.py`, `uam/__init__.py` | Filtros, comprobante, perfil, panel y configuración de plazos |
| `templates/objetos/index.html`, `detalle.html`, `guia.html` | Buscador, plazos, comprobante y «Dónde y cuándo» |
| `templates/objetos/comprobante.html`, `templates/acceso/perfil.html` | Nuevas |
| `templates/base.html`, `acceso/login.html`, `admin/admin_panel.html`, `visitantes/reportes_visitantes.html` | Enlace al perfil, carrera, plazos y búsqueda |
| `static/css/styles.css` | Sección 14: estilos de lo nuevo e impresión |
| `.env.example` | Plazos, horario y correo |
| `tests/probar_app.py` | 46 pruebas nuevas |

## Pruebas

| Prueba | Resultado |
|---|---|
| `tests/probar_app.py` | **303/303** |
| `tests/probar_app.py` + migración desde v6.2 y actualización desde v8.5 | **324/324** |
| `base_de_datos/probar_bd.py` | **135/135** (97 negativas) |
| `schema.sql` comparado con la v9.1.01 | Idéntico |
| Navegador real, computadora y celular | Catálogo, «Por vencer», ficha, comprobante, perfil, guía, panel y reportes de visitantes; sin desplazamiento horizontal |

---

# v10.1 · Un solo administrador

**Problema:** en «Cuentas» aparecían dos administradores: Nancy (la del `.env`) y «Administrador UAM» (CIF ADMIN), la
cuenta de prueba de versiones anteriores, que seguía guardada en la tabla `usuarios`. No podía entrar (el único
administrador que entra es el del `.env`), pero ocupaba un lugar en la lista.

**Solución:** cada vez que la aplicación arranca, deja como administrador solo al del `.env`:

- Un administrador anterior que **nunca hizo nada** se **borra**.
- Uno que **figura en el historial** (por ejemplo, porque registró objetos) se **desactiva**: no puede entrar y no
  aparece en «Cuentas», pero su nombre se conserva en lo que hizo. La base no deja borrar a alguien que tiene
  movimientos a su nombre.

**La base de datos no cambia:** no se tocan tablas, columnas ni triggers; solo esa fila de `usuarios`.

| Archivo | Cambio |
|---|---|
| `uam/datos/usuarios.py` | `quitar_admins_sobrantes`; «Cuentas» y sus contadores no muestran administradores desactivados |
| `uam/servicios/cuentas.py` | `sincronizar_admin` llama a `quitar_admins_sobrantes` al arrancar |
| `tests/probar_app.py` | 7 pruebas nuevas: el caso sin movimientos (se borra) y con movimientos (se desactiva) |

**Pruebas:** `tests/probar_app.py` **310/310**; `base_de_datos/probar_bd.py` **135/135**; `schema.sql` idéntico.

---

# v10.2 · Comentarios en el código

Solo cambian los comentarios; el funcionamiento es idéntico al de la v10.1.

- Cada función y clase de `app.py` y `uam/` tiene encima **un comentario corto con `#`** que dice qué hace
  (por ejemplo, `# Registra la entrega de un objeto.`).
- Las explicaciones largas entre comillas triples (`"""..."""`) se cambiaron por esos comentarios de una línea.
- Los comentarios largos de varias líneas se resumieron en una.
- `schema.sql`, las plantillas, el CSS y las pruebas no cambian.

**Comprobación:** el código sin comentarios es idéntico al de la v10.1 (comparado con el árbol de sintaxis de
Python). `tests/probar_app.py` **310/310**; `base_de_datos/probar_bd.py` **135/135**.
