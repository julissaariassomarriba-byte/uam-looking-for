# UAM Looking For v8

Sistema de objetos perdidos y encontrados del campus de la Universidad Americana (UAM).
Hecho solo con **Flask**, **SQLite** (`sqlite3`, incluido en Python), **HTML** y **CSS**. No usa otras librerías.
La v8 ordena el código y refuerza la seguridad sin tocar la base de datos (el esquema sigue siendo el v7.1);
los cambios están en `CAMBIOS_v8.md`.

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

## Archivo .env

El archivo `.env` (en esta carpeta) guarda la configuración:

```
ADMIN_USUARIO=admin
ADMIN_CONTRASENA=escribe-aqui-la-clave
ADMIN_NOMBRE=Administrador UAM
ADMIN_CORREO=admin@ejemplo.edu.ni
SECRET_KEY=escribe-aqui-un-texto-largo-y-aleatorio
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

Los estudiantes pueden crear su propia cuenta con el botón «Crear cuenta de estudiante», debajo de «Acceder» (/registro): nombre, CIF, correo y contraseña. Siempre reciben el rol Estudiante. Las cuentas de encargados las crea el administrador.

## Recibir un objeto

El formulario «Recibir objeto» tiene tres pasos:
1. **¿Quién lo entrega?** Nombre, tipo (estudiante, docente, personal administrativo o visitante) y contacto opcional. Si la persona ya vino antes, basta con su CIF. Si lo encontró el personal, se marca una casilla y no se pide nada.
2. **¿Qué objeto es?** Nombre, categoría, foto opcional y descripción privada.
3. **¿Dónde se encontró y dónde queda?** Lugar del hallazgo (privado), fecha, hora y el punto de resguardo: Vida Estudiantil, Sala Docente o Edificio A (se eligen, no se escriben).

Si el formulario se envía dos veces (doble clic o recarga), no se crea un objeto repetido.

## Fotos

- **Al subirla**: se arrastra y suelta en la zona punteada o se pulsa «Buscar foto» (en el celular, la zona abre la cámara o la galería).
- **En el navegador** (`templates/foto_script.html`, con `<canvas>`, sin librerías): la foto se achica a 1280 px como máximo, se vuelve a comprimir en WebP (o JPEG si el navegador no crea WebP) hasta unos 150 KB y pierde sus datos ocultos (como el GPS). Una foto de celular de 1,5 MB queda en unos 100 KB.
- **En el servidor** (`imagenes.py`): se lee la cabecera del archivo para comprobar que de verdad es WebP o JPEG, que no está cortada, que pesa 300 KB o menos y que mide 1280 px o menos. Flask corta cualquier envío de más de 2 MB.
- **En la base**: la foto se guarda como BLOB en la columna `objetos.foto`, la última de la fila, así listar objetos no carga imágenes. Al reemplazarla, la nueva ocupa el lugar de la anterior: no quedan fotos sueltas.
- Los estudiantes solo ven la foto si el encargado la marca como pública.

## Entregas, reclamaciones y devoluciones

**Entrega.** Cuando alguien retira un objeto, el encargado registra su nombre, tipo, CIF, teléfono y las señas que dio, y confirma que revisó su carné. Es la única forma de marcar un objeto como «Entregado», y cada objeto tiene **una sola entrega**.

**Reclamación.** Solo se puede reclamar un objeto ya entregado: un estudiante afirma que era suyo.
1. El estudiante abre el objeto, usa «¿Era tuyo?» y describe sus señas. Sigue el avance en «Mis reclamaciones».
2. El encargado revisa la reclamación y abre el objeto para ver su registro privado y quién lo retiró.
3. Si acepta, el objeto pasa a **«Por recuperar»** (aún lo tiene quien se lo llevó) y las demás reclamaciones pendientes se rechazan con su motivo. Si rechaza, escribe el motivo.

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

## Seguridad

- Todos los formularios llevan un token CSRF; se rechaza cualquier envío sin token o con uno que no coincide.
- Cabeceras en todas las páginas: no se pueden mostrar dentro de otro sitio (`X-Frame-Options`), el navegador no
  adivina tipos de archivo (`X-Content-Type-Options`) y no se envía la dirección completa a otros sitios (`Referrer-Policy`).
- Las redirecciones después de un formulario solo van a páginas de este sitio.
- Cookie de sesión `HttpOnly` y `SameSite=Lax` (y `Secure` con `COOKIE_SEGURA=1`).

## Base de datos

Seis tablas normalizadas hasta 3FN (`schema.sql`, el mismo de la entrega de base de datos v7.1):

| Tabla | Guarda |
|---|---|
| usuarios | Todas las personas, una fila por persona: cuentas (administrador, encargados, estudiantes) y quien llega a ventanilla sin cuenta. |
| objetos | Cada objeto encontrado: datos públicos y privados, dónde se guarda, quién lo trajo, su foto y su estado actual. |
| entregas | La entrega inicial de cada objeto (una por objeto): quién lo retiró, sus señas y qué encargado lo entregó. |
| reclamaciones | Quien dice ser dueño de un objeto entregado. Apunta a la entrega. |
| devoluciones | La recuperación y la devolución al dueño de una reclamación aceptada (una por reclamación). |
| historial | Una fila por acción: qué pasó, a qué objeto, quién, cuándo y en qué estado quedó. |

**Dónde vive cada regla:**
- **CHECK** (una sola fila): fechas y horas válidas, textos no vacíos, toda cuenta tiene CIF y correo, foto JPEG/WebP de 300 KB o menos, un rechazo lleva motivo, quien trae el objeto no es quien lo registra.
- **Triggers** (miran otra tabla): solo el personal activo registra, entrega, resuelve y devuelve; el estado del objeto coincide con lo registrado; no se reclama lo que uno mismo retiró; las fechas siguen el orden de los hechos; entregas, historial, reclamaciones y devoluciones no se borran; y el historial de los hechos se escribe solo.
- **Python** (`logica.py`): lo que depende de quién está conectado (por ejemplo, que solo el autor cancele su reclamación) y el hash de las contraseñas.

Las operaciones de varios pasos (entregar, aceptar una reclamación) se hacen en una sola transacción: si la base rechaza un paso, se deshace todo y se muestra el motivo.

`database.db` va limpia: solo contiene el registro del administrador del `.env`.

### Migración

Si tienes una base de la v6.2, `app.py` la pasa sola a la v7.1 al iniciar (también: `python migrar.py`):
crea un respaldo `database_respaldo_<fecha>.db`, arma la base nueva en memoria, convierte las contraseñas a hash,
pasa cada entrega al dueño a la tabla `devoluciones` (sus señas quedan en observaciones), revisa
`PRAGMA integrity_check`, `PRAGMA foreign_key_check` y que no falte ningún registro, y solo entonces reemplaza la base.
Si algo que la v7.1 exige no está en la base vieja (por ejemplo, un objeto sin ubicación), no toca nada y dice qué revisar.
Una base más antigua que la v6.2 se abre primero con la v6.2.

### Probar la base

La carpeta `base_de_datos/` tiene el diagrama ER (`.drawio` y `.png`), datos de ejemplo y 74 pruebas negativas.
`python base_de_datos/probar_bd.py` ejecuta todo (104 pruebas).

## Estructura

```
app.py            Rutas, sesiones y permisos
config.py         Lectura del .env, roles, categorías y estados
base_datos.py     Conexión, transacciones y consultas SQL
logica.py         Validaciones y reglas (contraseñas, cuentas, objetos, entregas, reclamaciones, devoluciones)
migrar.py         Migración de una base v6.2 a v7.1
imagenes.py       Revisión de las fotos en el servidor (formato, peso y medidas)
reporte_pdf.py    PDF del historial sin librerías
schema.sql        Esquema de la base de datos
templates/        Páginas HTML (Jinja)
static/           Estilos e imágenes
base_de_datos/    Diagrama ER, datos de ejemplo y pruebas de la base
```
