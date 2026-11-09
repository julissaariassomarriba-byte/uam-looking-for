# UAM Looking For v9

Sistema de objetos perdidos y encontrados del campus de la Universidad Americana (UAM).
Hecho solo con **Flask**, **SQLite** (`sqlite3`, incluido en Python), **HTML** y **CSS**. No usa otras librerías:
el aviso por WhatsApp usa `urllib` y las contraseñas `hashlib`, que vienen con Python.

La v9 reorganiza el código en un paquete (`uam/`) por capas, agrega la **validación cruzada de identidad** (un CIF
registrado ya no se puede usar con el nombre de otra persona), revisa en el servidor todos los datos de los
formularios y **elimina la cancelación de reclamaciones**. Los cambios están en `docs/CAMBIOS_v9.md`
(y los de versiones anteriores en `docs/`).

## Ejecutar

Desde esta carpeta:

```bash
pip install flask
python app.py
```

| Dirección | Para quién |
|---|---|
| http://127.0.0.1:5000/login | Estudiantes y encargados |
| http://127.0.0.1:5000/registro | Estudiantes que aún no tienen cuenta |
| http://127.0.0.1:5000/admin | Administrador (credenciales del archivo `.env`) |
| http://127.0.0.1:5000/visitante | Visitantes sin cuenta (también desde el botón «Soy visitante» del login) |

## Archivo .env

El archivo `.env` (en esta carpeta) guarda la configuración. `.env.example` es la plantilla con todas las variables:
cópiala como `.env` y escribe tus valores.

```
ADMIN_USUARIO=admin
ADMIN_CONTRASENA=escribe-aqui-la-clave
ADMIN_NOMBRE=Administrador UAM
ADMIN_CORREO=admin@ejemplo.edu.ni
SECRET_KEY=escribe-aqui-un-texto-largo-y-aleatorio
SITIO_URL=https://tu-usuario.pythonanywhere.com
WHATSAPP_TOKEN=...            (opcional: ver «WhatsApp»)
```

- La contraseña del administrador solo está en `.env`, nunca en la base de datos.
- Si falta `SECRET_KEY`, la app genera una al iniciar (las sesiones se cierran al reiniciar). Para crear una al azar:
  `python -c "import secrets; print(secrets.token_hex(32))"`.
- Opcional: `COOKIE_SEGURA=1` hace que la cookie de sesión solo viaje por HTTPS. Actívalo solo si el sitio abre
  siempre con `https://` (en PythonAnywhere, junto con «Force HTTPS» en la pestaña Web).
- No subas `.env` ni `database.db` a un repositorio (`.gitignore` ya los excluye de git).

## Roles

| Rol | Entra por | Puede |
|---|---|---|
| Estudiante | /login | Ver el catálogo y la guía rápida, reclamar objetos ya entregados y ver «Mis reclamaciones» |
| Encargado | /login | Recibir objetos (con foto y quién los trae), registrar entregas, mover objetos de ubicación, ver los datos privados, cambiar estados, aceptar o rechazar reclamaciones, ver el historial y descargar el PDF |
| Administrador | /admin | Todo lo del encargado, además de crear, editar, desactivar y reactivar cuentas |
| Visitante (sin cuenta) | /visitante | Reportar un objeto perdido con foto y consultar el estado de su reporte |

Los estudiantes pueden crear su propia cuenta con el botón «Crear cuenta», debajo de «Acceder» (/registro): nombre, CIF, correo y contraseña. Siempre reciben el rol Estudiante. Las cuentas de encargados las crea el administrador.

## Recibir un objeto

El formulario «Recibir objeto» tiene tres pasos:
1. **¿Quién lo entrega?** Nombre, tipo (estudiante, docente, personal administrativo o visitante) y contacto opcional. Si la persona ya vino antes, basta con su CIF. Si lo encontró el personal, se marca una casilla y no se pide nada.
   Si el CIF ya está registrado, el nombre escrito debe ser el de esa persona (ver «Validación de identidad»).
2. **¿Qué objeto es?** Nombre, categoría, foto opcional y descripción privada.
3. **¿Dónde se encontró y dónde queda?** Lugar del hallazgo (privado), fecha, hora y el punto de resguardo: Vida Estudiantil, Sala Docente o Edificio A (se eligen, no se escriben).

Si el formulario se envía dos veces (doble clic o recarga), no se crea un objeto repetido.

## Fotos

- **Al subirla**: se arrastra y suelta en la zona punteada o se pulsa «Buscar foto» (en el celular, la zona abre la cámara o la galería).
- **En el navegador** (`templates/parciales/foto_script.html`, con `<canvas>`, sin librerías): la foto se achica a 1280 px como máximo, se vuelve a comprimir en WebP (o JPEG si el navegador no crea WebP) hasta unos 150 KB y pierde sus datos ocultos (como el GPS). Una foto de celular de 1,5 MB queda en unos 100 KB.
- **En el servidor** (`uam/utilidades/imagenes.py`): se lee la cabecera del archivo para comprobar que de verdad es WebP o JPEG, que no está cortada, que pesa 300 KB o menos y que mide 1280 px o menos. Flask corta cualquier envío de más de 2 MB.
- **En la base**: la foto se guarda como BLOB en la columna `objetos.foto`, la última de la fila, así listar objetos no carga imágenes. Al reemplazarla, la nueva ocupa el lugar de la anterior: no quedan fotos sueltas.
- Los estudiantes solo ven la foto si el encargado la marca como pública.

## Entregas, reclamaciones y devoluciones

**Entrega.** Cuando alguien retira un objeto, el encargado registra su nombre, tipo, CIF, teléfono y las señas que dio, y confirma que revisó su carné. Es la única forma de marcar un objeto como «Entregado», y cada objeto tiene **una sola entrega**. Si el CIF ya está registrado, el nombre debe coincidir con el registro.

**Reclamación.** Solo se puede reclamar un objeto ya entregado: un estudiante afirma que era suyo.
1. El estudiante abre el objeto, usa «¿Era tuyo?» y describe sus señas. Sigue el avance en «Mis reclamaciones».
2. El encargado revisa la reclamación y abre el objeto para ver su registro privado y quién lo retiró.
3. Si acepta, el objeto pasa a **«Por recuperar»** (aún lo tiene quien se lo llevó) y las demás reclamaciones pendientes se rechazan con su motivo. Si rechaza, escribe el motivo.

Desde la v9 el estudiante **no puede cancelar** su reclamación: solo el personal la acepta o la rechaza (la base también
lo impide). Las reclamaciones canceladas antes de la v9 se conservan y se ven en la pestaña «Canceladas (antes de v9)».

**Devolución** (tabla `devoluciones`, en dos momentos):
4. El encargado recibe el objeto de quien se lo llevó y pulsa «Registrar recuperación» → **«Recuperado»**. El estudiante ve un aviso en el menú.
5. El encargado revisa el carné del dueño y pulsa «Confirmar devolución» → **«Devuelto»**.

Cada paso queda en el historial, y lo anota la propia base.

## Estados

| Estado | Quién lo pone |
|---|---|
| Activo, En resguardo, En bodega | El personal, a mano, mientras el objeto está bajo custodia |
| Entregado | La base, al registrar la entrega |
| Por recuperar | La base, al aceptar una reclamación |
| Recuperado | La base, al registrar la recuperación |
| Devuelto | La base, al confirmar la devolución al dueño |

## Contraseñas

Se guardan como hash, nunca en texto: PBKDF2-SHA256 con 600 000 iteraciones y una sal aleatoria por cuenta,
usando `hashlib`, que viene incluido en Python (no se instala nada). El formato es `algoritmo$iteraciones$sal$hash`;
si en el futuro se suben las iteraciones, cada hash viejo se recalcula solo cuando su dueño inicia sesión.
La contraseña del administrador sigue solo en el `.env`.

## Validación de identidad (v9)

Un CIF ya registrado identifica a **una** persona. Al recibir un objeto, registrar una entrega, crear una cuenta desde
el panel o registrarse como estudiante:
- el nombre escrito debe corresponder al registrado con ese CIF. No hace falta escribirlo idéntico (se ignoran tildes,
  mayúsculas y el orden), pero todas las palabras deben estar en el registro y deben ser al menos dos;
- un estudiante con cuenta no puede quedar anotado como docente, administrativo o visitante;
- un correo que ya pertenece a otra persona se rechaza;
- los datos de una persona registrada nunca se sobrescriben: solo se completa el teléfono o el correo que faltaba.

Si algo no corresponde, el formulario no se guarda, conserva lo escrito y el mensaje dice a nombre de quién está el CIF.

## Seguridad

- Todos los formularios llevan un token CSRF; se rechaza cualquier envío sin token o con uno que no coincide.
- «Cerrar sesión» es un formulario (POST con token): un enlace de otro sitio no puede cerrar tu sesión.
- Todos los datos se revisan otra vez en el servidor: formato del CIF (letras y números), correo, teléfono (8 dígitos o
  más), fechas y horas reales, categorías, estados y ubicaciones de la lista, y el largo máximo de cada texto.
- Cabeceras en todas las páginas: no se pueden mostrar dentro de otro sitio (`X-Frame-Options`), el navegador no
  adivina tipos de archivo (`X-Content-Type-Options`) y no se envía la dirección completa a otros sitios (`Referrer-Policy`).
- Las redirecciones después de un formulario solo van a páginas de este sitio.
- Cookie de sesión `HttpOnly` y `SameSite=Lax` (y `Secure` con `COOKIE_SEGURA=1`).

## Visitantes (v8.5)

**El visitante** (sin cuenta ni contraseña):
1. Pulsa «Soy visitante» en el login y elige «Reportar un objeto perdido».
2. Escribe su nombre, teléfono, correo (opcional), qué objeto perdió, categoría, descripción, dónde y cuándo lo perdió,
   y sube una **foto obligatoria** (se arrastra o se busca; se reduce sola, igual que en «Recibir objeto»).
3. Ve su **código** (`UAM-XXXX-XXXX`) y un **enlace privado** para seguir el reporte.
4. Después consulta el estado con el código **y** su teléfono, o abriendo el enlace privado. Solo ve el estado, el objeto
   y, si se localizó, dónde retirarlo: nunca su teléfono, su correo ni las observaciones del personal.

**El personal** (encargado o administrador), en «Visitantes» del menú o en la tarjeta del panel de administración:
filtra por estado, busca por código, ve la foto y los datos del visitante, lo llama o le escribe (botones de
teléfono, WhatsApp y correo), cambia el estado (Pendiente, En revisión, Localizado, Resuelto, Cerrado), agrega
observaciones internas, relaciona el reporte con un objeto encontrado (el sistema sugiere los de la misma categoría
bajo custodia encontrados desde el día de la pérdida) y reintenta el aviso de WhatsApp si falló.

**Seguridad:** el código es al azar (no consecutivo) y por sí solo no muestra nada: hace falta también el teléfono.
El enlace privado lleva un token de 256 bits que no se guarda en la base (solo su hash SHA-256). Las páginas de
seguimiento no quedan en la caché del navegador. La foto se revisa por sus bytes reales (JPEG o WebP, máx. 300 KB y
1280 px) y se guarda dentro de la base, así que no se usa el nombre del archivo que sube el visitante. Todos los
formularios llevan token CSRF y todas las consultas usan parámetros.

## WhatsApp (aviso al encargado)

Cada reporte nuevo intenta avisar al encargado por **WhatsApp Business Cloud API** (`uam/utilidades/notificaciones.py`). El reporte
se guarda **antes** del aviso: si WhatsApp no está configurado, falla o tarda más de 10 segundos, el reporte queda
guardado igual y el panel muestra el resultado real (`Enviada` con el id del mensaje, `Fallida` con el motivo o
`No configurada`) y un botón para **reintentar**. Nunca se marca como enviado algo que WhatsApp no aceptó.

**Configurarlo:**
1. En https://developers.facebook.com crea una app de tipo **Business** y agrégale el producto **WhatsApp**.
2. En WhatsApp → **Configuración de la API** copia el **Identificador del número de teléfono** (Phone number ID)
   en `WHATSAPP_NUMERO_ID`.
3. **Token** (`WHATSAPP_TOKEN`): para probar sirve el token temporal de esa misma página (dura 24 horas). Para uso real,
   en la configuración del negocio (business.facebook.com → Usuarios del sistema) crea un usuario del sistema,
   asígnale la app y genera un token **permanente** con el permiso `whatsapp_business_messaging`.
4. **Destino** (`WHATSAPP_DESTINO`): el número del encargado con código de país, por ejemplo `50588887777`. Con el número
   de prueba de Meta, primero agrega ese número a la lista de destinatarios permitidos y verifícalo con el código que llega.
5. **Plantilla** (`WHATSAPP_PLANTILLA`, recomendada): en el Administrador de WhatsApp → Plantillas crea una de categoría
   **Utilidad**, idioma **Español** (`WHATSAPP_IDIOMA=es`; si eliges otra variante, por ejemplo `es_MX`, escribe ese código),
   con nombre `nuevo_reporte_visitante` y este texto (las 8 variables, en este orden):
   ```
   Nuevo reporte de objeto perdido {{1}} en UAM Looking For.
   Visitante: {{2}}
   Objeto: {{3}}
   Descripción: {{4}}
   Lugar: {{5}}
   Fecha de pérdida: {{6}}
   Teléfono de contacto: {{7}}
   Revisa el reporte aquí: {{8}} (requiere iniciar sesión).
   ```
   Espera a que Meta la apruebe. Sin plantilla se envía texto libre, pero Meta solo lo entrega si el encargado le escribió
   a ese número en las últimas 24 horas.
6. `SITIO_URL` con la dirección pública (`https://tu-usuario.pythonanywhere.com`): es el enlace del aviso.
7. Guarda el `.env` y pulsa **Reload** en PythonAnywhere. Haz un reporte de prueba como visitante y revisa su estado en el panel.

Notas: en PythonAnywhere (cuenta gratuita) `.facebook.com` está en la lista de sitios permitidos. «Enviada» significa
que WhatsApp **aceptó** el mensaje; confirmar la entrega o la lectura necesitaría *webhooks*, que no se implementaron.
El aviso lleva el nombre y el teléfono del visitante, así que esos datos pasan por los servidores de Meta.

## Base de datos

Siete tablas normalizadas hasta 3FN (`schema.sql`; la v8.5 solo agregó `reportes_visitantes`):

| Tabla | Guarda |
|---|---|
| usuarios | Todas las personas, una fila por persona: cuentas (administrador, encargados, estudiantes) y quien llega a ventanilla sin cuenta. |
| objetos | Cada objeto encontrado: datos públicos y privados, dónde se guarda, quién lo trajo, su foto y su estado actual. |
| entregas | La entrega inicial de cada objeto (una por objeto): quién lo retiró, sus señas y qué encargado lo entregó. |
| reclamaciones | Quien dice ser dueño de un objeto entregado. Apunta a la entrega. |
| devoluciones | La recuperación y la devolución al dueño de una reclamación aceptada (una por reclamación). |
| historial | Una fila por acción: qué pasó, a qué objeto, quién, cuándo y en qué estado quedó. |
| reportes_visitantes | Lo que reporta un visitante sin cuenta (con su foto), su estado, la gestión del personal, el objeto relacionado y el resultado real del aviso por WhatsApp. |

**Dónde vive cada regla:**
- **CHECK** (una sola fila): fechas y horas válidas, textos no vacíos, toda cuenta tiene CIF y correo, foto JPEG/WebP de 300 KB o menos, un rechazo lleva motivo, quien trae el objeto no es quien lo registra.
- **Triggers** (miran otra tabla): solo el personal activo registra, entrega, resuelve y devuelve; el estado del objeto coincide con lo registrado; no se reclama lo que uno mismo retiró; las fechas siguen el orden de los hechos; entregas, historial, reclamaciones y devoluciones no se borran; y el historial de los hechos se escribe solo.
- **Python** (`uam/servicios/`): lo que depende de quién está conectado, la validación cruzada de identidad (comparar nombres no se puede hacer bien en SQL) y el hash de las contraseñas.

Las operaciones de varios pasos (entregar, aceptar una reclamación) se hacen en una sola transacción: si la base rechaza un paso, se deshace todo y se muestra el motivo.

`database.db` no viene en el ZIP: la app la crea al iniciar. **Una base v7.1, v8 o v8.5 que ya tiene datos se actualiza
sola** al iniciar la v9: todo el esquema usa `IF NOT EXISTS`, así que solo se agrega lo que falta (en una base v8.5, el
trigger `trg_reclamacion_sin_cancelar`). Los datos no cambian (comprobado con una base v8.5 con datos). Igual haz un
respaldo antes de actualizar.

### Migración

Si tienes una base de la v6.2, la app la pasa sola al esquema actual al iniciar (`uam/datos/migrar.py`):
crea un respaldo `database_respaldo_<fecha>.db`, arma la base nueva en memoria, convierte las contraseñas a hash,
pasa cada entrega al dueño a la tabla `devoluciones` (sus señas quedan en observaciones), revisa
`PRAGMA integrity_check`, `PRAGMA foreign_key_check` y que no falte ningún registro, y solo entonces reemplaza la base.
Si algo que la v7.1 exige no está en la base vieja (por ejemplo, un objeto sin ubicación), no toca nada y dice qué revisar.
Una base más antigua que la v6.2 se abre primero con la v6.2.

### Pruebas

- `python tests/probar_app.py` prueba la aplicación completa (220 pruebas: cuentas, objetos, entregas, reclamaciones,
  visitantes, WhatsApp con un servidor simulado, seguridad y la validación de identidad). Trabaja en una carpeta temporal:
  no toca tu `database.db` ni tu `.env`.
- `python base_de_datos/probar_bd.py` prueba la base sola (135 pruebas, 97 de ellas negativas). La carpeta
  `base_de_datos/` también tiene el diagrama ER (`.drawio` y `.png`) y los datos de ejemplo.

## Estructura

```
app.py                  Punto de entrada (el WSGI de PythonAnywhere importa «app» de aquí)
uam/
  __init__.py           crear_app(): configuración, base, seguridad de cada petición, rutas y errores
  config.py             Roles, categorías, estados, ubicaciones, largos máximos y lectura del .env
  validacion.py         Revisión de datos: CIF, correo, teléfono, fechas, horas y comparación de nombres
  seguridad.py          Contraseñas (PBKDF2), tokens y comparación segura
  datos/                Acceso a SQLite: conexion.py y un módulo por grupo de tablas (+ migrar.py)
  servicios/            Reglas del sistema: cuentas, personas (identidad), objetos, reclamaciones, visitantes
  rutas/                Blueprints de Flask: acceso, objetos, reclamaciones, visitantes, admin (+ comun.py)
  utilidades/           imagenes.py (fotos), notificaciones.py (WhatsApp), reporte_pdf.py (PDF)
templates/              Páginas HTML (Jinja), una carpeta por sección; parciales/ tiene macros y el script de fotos
static/                 Estilos e imágenes
schema.sql              Esquema de la base de datos
base_de_datos/          Diagrama ER, datos de ejemplo y pruebas de la base
tests/                  Pruebas de la aplicación
docs/                   Informes de cambios de cada versión
.env.example            Plantilla del .env (sin valores reales)
```

Cada petición recorre las capas en orden: **ruta** (lee el formulario) → **servicio** (valida y aplica la regla) →
**datos** (consulta con parámetros) → **base** (CHECK y triggers lo vuelven a revisar) → **plantilla**.
