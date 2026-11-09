# UAM Looking For v8.5 · Módulo de visitantes

La v8.5 parte de la v8 y le agrega un módulo completo para visitantes sin cuenta. Lo de estudiantes, encargados y
administradores sigue igual: las 127 pruebas de la v8 pasan sin cambios.

## 1. Qué se agregó

| Para quién | Qué puede hacer |
|---|---|
| Visitante (sin cuenta) | Botón «Ingresar como visitante» en el login → reportar un objeto perdido con foto obligatoria → recibir un código `UAM-XXXX-XXXX` y un enlace privado → consultar el estado con el código y su teléfono |
| Encargado y administrador | Sección «Reportes de visitantes» (menú «Visitantes» con contador de pendientes, y tarjeta en el panel de administración): ver todos, filtrar por estado, buscar por código, ver la foto y los datos del visitante, llamarlo o escribirle, cambiar el estado, agregar observaciones internas, relacionar el reporte con un objeto encontrado (con sugerencias) y reintentar el aviso de WhatsApp |
| Encargado (WhatsApp) | Aviso automático por WhatsApp Business Cloud API con código, visitante, objeto, descripción, lugar, fecha, teléfono y el enlace al reporte en el panel |

Estados del reporte: Pendiente, En revisión, Localizado, Resuelto y Cerrado.

## 2. Base de datos (cambio no destructivo)

- Tabla nueva **`reportes_visitantes`** con: id autoincremental, código único, hash del token de seguimiento, nombre,
  teléfono y correo del visitante, nombre, categoría y descripción del objeto, lugar y fecha de pérdida, estado, fecha
  de registro, objeto relacionado, observaciones, quién y cuándo lo gestionó, resultado del aviso por WhatsApp
  (estado, intentos, fecha, id del mensaje o motivo del fallo) y la foto (BLOB obligatorio, JPEG o WebP de 300 KB o menos).
- 1 índice nuevo (`estado`) y 3 triggers nuevos: un reporte nace Pendiente y sin gestión; lo que reportó el visitante no
  cambia; solo el personal activo lo gestiona; los intentos de WhatsApp solo aumentan; no se borra.
- Con esto el esquema queda en 7 tablas, 15 llaves foráneas, 12 índices y 25 triggers. Las 6 tablas anteriores no cambian.
- **Actualización automática:** al iniciar, la app ejecuta `schema.sql` (todo con `IF NOT EXISTS`). En una base v7.1 o v8
  con datos, eso agrega la tabla nueva y deja todo lo demás igual. Está comprobado con una base v8 real: el contenido
  de las 6 tablas es idéntico antes y después, y repetir el arranque no duplica nada.
- El visitante **no** se crea como usuario: sus datos viven solo en su reporte.
- Diagrama ER regenerado desde el mismo `schema.sql`: `base_de_datos/UAM_Looking_For_BD_v8_5.drawio` y `.png`
  (reemplazan a los de la v7.1).

## 3. Archivos

| Archivo | Cambio |
|---|---|
| `notificaciones.py` | **Nuevo.** Aviso por WhatsApp Cloud API con `urllib` (biblioteca estándar): plantilla aprobada o texto libre, tiempo máximo de 10 s, nunca lanza errores ni finge un envío |
| `.env.example` | **Nuevo.** Plantilla del `.env` con todas las variables y sin valores reales |
| `CAMBIOS_v8_5.md` | **Nuevo.** Este informe |
| `templates/visitante.html` | **Nuevo.** Portal del visitante (reportar o consultar) |
| `templates/visitante_reportar.html` | **Nuevo.** Formulario en tres pasos con la zona de foto obligatoria |
| `templates/visitante_seguimiento.html` | **Nuevo.** Confirmación con el código y el enlace privado, y el estado |
| `templates/visitante_consultar.html` | **Nuevo.** Consulta con código + teléfono |
| `templates/visitante_estado.html` | **Nuevo.** Tarjeta de estado que comparten la confirmación y la consulta |
| `templates/reportes_visitantes.html` | **Nuevo.** Lista del personal con pestañas por estado y búsqueda por código |
| `templates/reporte_visitante.html` | **Nuevo.** Detalle: foto, datos, contacto, estado, observaciones, objeto relacionado y WhatsApp |
| `app.py` | Rutas `/visitante`, `/visitante/reportar`, `/visitante/seguimiento/<token>`, `/visitante/consultar`, `/reportes-visitantes`, `/reportes-visitantes/<id>`, `/reportes-visitantes/<id>/foto`; contador del menú |
| `logica.py` | Validación del reporte, código y token al azar, aviso y reintento, consulta segura, gestión, relación con objetos, sugerencias y enlaces de contacto |
| `base_datos.py` | Consultas de la tabla nueva (todas con parámetros; las listas no leen la foto) |
| `config.py` | Estados del reporte y código de país (505) para los enlaces de WhatsApp |
| `schema.sql` | Tabla, índice y triggers nuevos |
| `templates/login.html` | Botón «Ingresar como visitante» |
| `templates/base.html` | Enlace «Visitantes» con contador para el personal |
| `templates/admin_panel.html` | Tarjeta «Reportes de visitantes» |
| `templates/macros.html` | La zona de foto puede ser obligatoria (`requerida=true`) |
| `static/css/styles.css` | Estilos del módulo, con los colores y componentes que ya existían |
| `README.md` | Módulo de visitantes, guía de WhatsApp, `.env.example` |
| `base_de_datos/*` | Datos de ejemplo, 22 pruebas negativas nuevas, `probar_bd.py`, `reglas_python.py`, diagrama v8.5 |

Eliminados: `base_de_datos/UAM_Looking_For_BD_v7_1.drawio` y `.png`, reemplazados por los de la v8.5 para no tener dos diagramas.
Se reutilizaron sin cambios `imagenes.py` (revisión de la foto) y `foto_script.html` (reducción y arrastrar y soltar).

## 4. Seguridad y datos personales

- El código del reporte es al azar (32^8 combinaciones). Por sí solo no muestra nada: la consulta exige también el teléfono.
- El enlace privado lleva un token de 256 bits. En la base solo se guarda su SHA-256, así que ni quien lea la base puede abrir reportes ajenos.
- Las páginas de seguimiento se envían con `Cache-Control: no-store` y ocultan teléfono, correo, descripción y observaciones.
- La foto se revisa por sus bytes reales (JPEG o WebP, peso y medidas) y se guarda dentro de la base. No se usa el nombre del archivo, así que no hay nombres peligrosos.
- Todo formulario lleva token CSRF, todas las consultas usan parámetros, la búsqueda por código quita los comodines de `LIKE` y los textos tienen un largo máximo.
- Las rutas del panel exigen personal (encargado o administrador); la base lo vuelve a exigir con un trigger.
- Las credenciales de WhatsApp solo están en el `.env`. Ningún motivo de fallo guarda el token.

## 5. Pruebas ejecutadas (resultados reales)

| Prueba | Resultado |
|---|---|
| Batería de la app (`test_v85.py`): las 127 de la v8 + 79 del módulo de visitantes | **206/206** |
| Base de datos en memoria (`python base_de_datos/probar_bd.py`) | **134/134** (96 negativas) |
| Navegador real (Chromium + Playwright): login → visitante → formulario sin foto (el navegador no deja enviar) → foto arrastrada y reducida → confirmación → consulta en otra sesión → panel del encargado → foto visible → relacionar con la mochila sugerida → «Localizado» → el visitante ve dónde retirarlo; celular sin desplazamiento horizontal; sin errores de JavaScript | **18/18** |
| Base v8 con datos abierta con la v8.5 | Tabla nueva creada; 6 tablas idénticas; 25 triggers; integridad correcta |

El aviso por WhatsApp se probó contra un **servidor local que imita a la API de Meta**:
- envío con plantilla (ruta `/v22.0/<id>/messages`, token en la cabecera, 8 variables en orden y sin saltos de línea);
- envío en texto libre;
- error 401 de Meta;
- respuesta sin id;
- sin conexión;
- demora mayor al tiempo máximo;
- sin configuración;
- reintento que funciona, reintento que vuelve a fallar y bloqueo del reenvío.

En todos los casos el reporte se guardó y el estado anotado fue el real. **No se probó contra la API real de Meta**,
porque hacen falta tus credenciales y una plantilla aprobada; el formato de la petición sigue la documentación de la
Cloud API (Graph v22.0).

## 6. Pendientes y decisiones

| Tema | Detalle |
|---|---|
| Probar WhatsApp real | Con tus credenciales y la plantilla aprobada (guía en README, sección «WhatsApp») |
| Confirmación de entrega o lectura | Necesita *webhooks* de Meta; no se implementó. «Enviada» = WhatsApp aceptó el mensaje |
| Límite de reportes y consultas | El formulario público no tiene límite de envíos por persona; contra el spam haría falta un límite o un captcha (regla nueva) |
| Tiempo de espera | El aviso se envía al guardar el reporte; si WhatsApp tarda, el visitante espera hasta 10 s |
| Conservación de datos | Los reportes no se borran (se cierran). Falta decidir cuánto tiempo guardar los datos personales de los visitantes |
| Pendientes de la v8 | Cerrar sesión con POST, límite de intentos de login, verificar el correo al registrarse |

## 7. Cómo actualizar el sitio en PythonAnywhere

1. Respaldo, en el Bash: `cp ~/uam-looking-for/UAM_Looking_For_v7_1/database.db ~/respaldo_antes_v8_5.db`
2. En GitHub, desde la **página principal** del repositorio: **Add file → Upload files**, arrastra la carpeta
   `UAM_Looking_For_v7_1` de `UAM_Looking_For_v8_5_actualizacion.zip` y pulsa **Commit changes**. Trae todo lo que cambió
   desde la v7.1, así que sirve aunque todavía no hayas aplicado la v8. Si quieres, borra en GitHub los dos diagramas
   viejos `base_de_datos/UAM_Looking_For_BD_v7_1.*`.
3. En el Bash: `cd ~/uam-looking-for && git pull`
4. Opcional, para WhatsApp: `nano ~/uam-looking-for/UAM_Looking_For_v7_1/.env` y agrega las variables de `.env.example`.
5. Pestaña Web: **Reload**. Al arrancar, la app agrega la tabla nueva a tu base sin tocar los datos.

**Volver atrás:** sube a GitHub los mismos archivos tomados del ZIP anterior, haz `git pull` y pulsa Reload. La tabla
nueva puede quedarse en la base: la versión anterior simplemente no la usa.
