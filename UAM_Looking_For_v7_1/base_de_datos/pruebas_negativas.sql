-- =====================================================================
-- UAM Looking For v8.5 · Pruebas negativas: cada una DEBE ser rechazada por la base.
-- Cada bloque tiene un encabezado «PRUEBA» con el nombre y el error esperado. Las líneas hasta «-- FALLA»
-- preparan el caso (deben funcionar); la sentencia después de «-- FALLA» es la que debe fallar.
-- probar_bd.py ejecuta cada bloque en una transacción y la deshace al terminar.
-- Caso base: datos_prueba.sql (la calculadora ya fue devuelta a Ana; las llaves siguen Activas).
-- =====================================================================

-- ======================= usuarios =======================
-- PRUEBA: CIF vacío ('') | espera: CHECK constraint failed
-- FALLA
INSERT INTO usuarios (nombre, cif, rol) VALUES ('Sin CIF', '', 'Visitante');

-- PRUEBA: CIF repetido | espera: UNIQUE constraint failed: usuarios.cif
-- FALLA
INSERT INTO usuarios (nombre, cif, rol) VALUES ('Otra Ana', '26010001', 'Estudiante');

-- PRUEBA: CIF repetido con otras mayúsculas | espera: UNIQUE constraint failed: usuarios.cif
-- FALLA
INSERT INTO usuarios (nombre, cif, rol) VALUES ('Copia', 'enc00001', 'Visitante');

-- PRUEBA: correo con formato inválido | espera: CHECK constraint failed
-- FALLA
INSERT INTO usuarios (nombre, correo, rol) VALUES ('Correo malo', 'sin-arroba', 'Visitante');

-- PRUEBA: correo repetido con otras mayúsculas | espera: UNIQUE constraint failed: usuarios.correo
-- FALLA
INSERT INTO usuarios (nombre, correo, rol) VALUES ('Copia', 'AMartinez@UAMV.edu.ni', 'Visitante');

-- PRUEBA: un visitante no puede tener contraseña | espera: CHECK constraint failed
-- FALLA
INSERT INTO usuarios (nombre, cif, correo, rol, contrasena_hash) VALUES ('V', 'V1', 'v@x.ni', 'Visitante', 'pbkdf2_sha256$600000$aaaaaaaaaaaaaaaa$bbbbbbbbbbbbbbbbbbbbbbbb');

-- PRUEBA: una cuenta sin correo | espera: CHECK constraint failed
-- FALLA
INSERT INTO usuarios (nombre, cif, rol, contrasena_hash) VALUES ('Sin correo', 'E9', 'Estudiante', 'pbkdf2_sha256$600000$aaaaaaaaaaaaaaaa$bbbbbbbbbbbbbbbbbbbbbbbb');

-- PRUEBA: contraseña en texto plano | espera: CHECK constraint failed
-- FALLA
UPDATE usuarios SET contrasena_hash = 'clave123' WHERE id = 4;

-- PRUEBA: rol que no existe | espera: CHECK constraint failed
-- FALLA
INSERT INTO usuarios (nombre, rol) VALUES ('X', 'Profesor');

-- PRUEBA: borrar un usuario con registros (ON DELETE RESTRICT) | espera: FOREIGN KEY constraint failed
-- FALLA
DELETE FROM usuarios WHERE id = 7;

-- ======================= objetos =======================
-- PRUEBA: fecha imposible (30 de febrero) | espera: CHECK constraint failed
-- FALLA
UPDATE objetos SET fecha = '2026-02-30' WHERE id = 2;

-- PRUEBA: hora inválida | espera: CHECK constraint failed
-- FALLA
UPDATE objetos SET hora = '25:61' WHERE id = 2;

-- PRUEBA: ubicación inventada | espera: CHECK constraint failed
-- FALLA
UPDATE objetos SET ubicacion = 'Marte' WHERE id = 2;

-- PRUEBA: estado inventado (lo frena el trigger de coherencia; el CHECK es el respaldo) | espera: El estado no coincide
-- FALLA
UPDATE objetos SET estado = 'Perdido' WHERE id = 2;

-- PRUEBA: foto que no es JPEG ni WebP (PNG) | espera: CHECK constraint failed
-- FALLA
UPDATE objetos SET foto = X'89504E470D0A1A0A' WHERE id = 2;

-- PRUEBA: foto de más de 300 KB | espera: CHECK constraint failed
-- FALLA
UPDATE objetos SET foto = X'FFD8FF' || zeroblob(400000) WHERE id = 2;

-- PRUEBA: publicar una foto que no existe | espera: CHECK constraint failed
-- FALLA
UPDATE objetos SET foto_publica = 1 WHERE id = 2;

-- PRUEBA: registrado_por que no existe (llave foránea) | espera: Solo el personal activo registra objetos
-- FALLA
INSERT INTO objetos (titulo, descripcion, categoria, lugar_encontrado, ubicacion, fecha, registrado_por) VALUES ('X', 'X', 'Otros', 'X', 'Edificio A', '2026-11-01', 999);

-- PRUEBA: un estudiante registra un objeto | espera: Solo el personal activo registra objetos
-- FALLA
INSERT INTO objetos (titulo, descripcion, categoria, lugar_encontrado, ubicacion, fecha, registrado_por) VALUES ('X', 'X', 'Otros', 'X', 'Edificio A', '2026-11-01', 4);

-- PRUEBA: una encargada desactivada registra un objeto | espera: Solo el personal activo registra objetos
-- FALLA
INSERT INTO objetos (titulo, descripcion, categoria, lugar_encontrado, ubicacion, fecha, registrado_por) VALUES ('X', 'X', 'Otros', 'X', 'Edificio A', '2026-11-01', 10);

-- PRUEBA: un objeto nuevo ya «Entregado» | espera: Un objeto nuevo empieza bajo custodia
-- FALLA
INSERT INTO objetos (titulo, descripcion, categoria, lugar_encontrado, ubicacion, fecha, estado, registrado_por) VALUES ('X', 'X', 'Otros', 'X', 'Edificio A', '2026-11-01', 'Entregado', 2);

-- PRUEBA: quien lo trajo es quien lo registró | espera: CHECK constraint failed
-- FALLA
UPDATE objetos SET reportado_por = registrado_por WHERE id = 2;

-- PRUEBA: cambiar quién registró el objeto | espera: Quién registró el objeto no cambia
-- FALLA
UPDATE objetos SET registrado_por = 2 WHERE id = 2;

-- PRUEBA: borrar un objeto con historial (ON DELETE RESTRICT) | espera: FOREIGN KEY constraint failed
-- FALLA
DELETE FROM objetos WHERE id = 2;

-- ======================= estado del objeto coherente con los hechos =======================
-- PRUEBA: «Entregado» sin entrega | espera: El estado no coincide con lo registrado
-- FALLA
UPDATE objetos SET estado = 'Entregado' WHERE id = 2;

-- PRUEBA: «Devuelto» sin devolución | espera: El estado no coincide con lo registrado
-- FALLA
UPDATE objetos SET estado = 'Devuelto' WHERE id = 2;

-- PRUEBA: un objeto entregado vuelve a «En resguardo» a mano | espera: El estado no coincide con lo registrado
INSERT INTO entregas (id, objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 2, 4, 3, 'Llavero rojo', '2026-11-03 10:00:00');
-- FALLA
UPDATE objetos SET estado = 'En resguardo' WHERE id = 2;

-- PRUEBA: «Recuperado» sin devolución | espera: El estado no coincide con lo registrado
INSERT INTO entregas (id, objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 2, 4, 3, 'Llavero rojo', '2026-11-03 10:00:00');
INSERT INTO reclamaciones (id, entrega_id, usuario_id, descripcion, fecha_solicitud) VALUES (10, 2, 5, 'Son mías', '2026-11-03 11:00:00');
UPDATE reclamaciones SET estado = 'Aceptada', fecha_resolucion = '2026-11-03 12:00:00', resuelto_por = 3 WHERE id = 10;
-- FALLA
UPDATE objetos SET estado = 'Recuperado' WHERE id = 2;

-- PRUEBA: la calculadora devuelta no vuelve a «Entregado» | espera: El estado no coincide con lo registrado
-- FALLA
UPDATE objetos SET estado = 'Entregado' WHERE id = 1;

-- ======================= entregas =======================
-- PRUEBA: una entrega hecha por un visitante | espera: Solo el personal activo registra entregas
-- FALLA
INSERT INTO entregas (objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 4, 7, 'x', '2026-11-03 10:00:00');

-- PRUEBA: una entrega hecha por un estudiante | espera: Solo el personal activo registra entregas
-- FALLA
INSERT INTO entregas (objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 5, 4, 'x', '2026-11-03 10:00:00');

-- PRUEBA: entregar un objeto que no está bajo custodia | espera: Solo se entrega un objeto que está bajo custodia
INSERT INTO entregas (id, objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 2, 4, 3, 'Llavero rojo', '2026-11-03 10:00:00');
-- FALLA
INSERT INTO entregas (objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 5, 3, 'x', '2026-11-03 11:00:00');

-- PRUEBA: segunda entrega del mismo objeto, aunque se quiten los triggers (el UNIQUE la impide) | espera: UNIQUE constraint failed: entregas.objeto_id
DROP TRIGGER trg_entrega_valida;
-- FALLA
INSERT INTO entregas (objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (1, 5, 3, 'x', '2026-11-03 11:00:00');

-- PRUEBA: entrega anterior al hallazgo | espera: La entrega no puede ser anterior al hallazgo
-- FALLA
INSERT INTO entregas (objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 4, 3, 'x', '2026-10-01 10:00:00');

-- PRUEBA: modificar una entrega | espera: Una entrega registrada no se modifica
-- FALLA
UPDATE entregas SET retirado_por = 5 WHERE id = 1;

-- PRUEBA: borrar una entrega | espera: Una entrega registrada no se borra
-- FALLA
DELETE FROM entregas WHERE id = 1;

-- ======================= reclamaciones =======================
-- PRUEBA: reclamar un objeto que ya fue devuelto | espera: Solo se reclama un objeto que sigue entregado
-- FALLA
INSERT INTO reclamaciones (entrega_id, usuario_id, descripcion, fecha_solicitud) VALUES (1, 5, 'Es mía', '2026-11-03 10:00:00');

-- PRUEBA: quien retiró el objeto lo reclama | espera: Quien retiró el objeto no puede reclamarlo
INSERT INTO entregas (id, objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 2, 4, 3, 'Llavero rojo', '2026-11-03 10:00:00');
-- FALLA
INSERT INTO reclamaciones (entrega_id, usuario_id, descripcion, fecha_solicitud) VALUES (2, 4, 'Son mías', '2026-11-03 11:00:00');

-- PRUEBA: reclamar sin cuenta (persona de ventanilla) | espera: Para reclamar se necesita una cuenta activa
INSERT INTO entregas (id, objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 2, 4, 3, 'Llavero rojo', '2026-11-03 10:00:00');
-- FALLA
INSERT INTO reclamaciones (entrega_id, usuario_id, descripcion, fecha_solicitud) VALUES (2, 8, 'Son mías', '2026-11-03 11:00:00');

-- PRUEBA: reclamar con una cuenta desactivada | espera: Para reclamar se necesita una cuenta activa
INSERT INTO entregas (id, objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 2, 4, 3, 'Llavero rojo', '2026-11-03 10:00:00');
-- FALLA
INSERT INTO reclamaciones (entrega_id, usuario_id, descripcion, fecha_solicitud) VALUES (2, 10, 'Son mías', '2026-11-03 11:00:00');

-- PRUEBA: reclamación anterior a la entrega | espera: La reclamación no puede ser anterior a la entrega
INSERT INTO entregas (id, objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 2, 4, 3, 'Llavero rojo', '2026-11-03 10:00:00');
-- FALLA
INSERT INTO reclamaciones (entrega_id, usuario_id, descripcion, fecha_solicitud) VALUES (2, 5, 'Son mías', '2026-11-02 11:00:00');

-- PRUEBA: una reclamación nueva ya aceptada | espera: Una reclamación nueva empieza como Pendiente
INSERT INTO entregas (id, objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 2, 4, 3, 'Llavero rojo', '2026-11-03 10:00:00');
-- FALLA
INSERT INTO reclamaciones (entrega_id, usuario_id, descripcion, estado, fecha_solicitud, fecha_resolucion, resuelto_por) VALUES (2, 5, 'Mías', 'Aceptada', '2026-11-03 11:00:00', '2026-11-03 11:00:00', 3);

-- PRUEBA: dos pendientes de la misma persona por la misma entrega | espera: UNIQUE constraint failed: reclamaciones.entrega_id, reclamaciones.usuario_id
INSERT INTO entregas (id, objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 2, 4, 3, 'Llavero rojo', '2026-11-03 10:00:00');
INSERT INTO reclamaciones (entrega_id, usuario_id, descripcion, fecha_solicitud) VALUES (2, 5, 'Son mías', '2026-11-03 11:00:00');
-- FALLA
INSERT INTO reclamaciones (entrega_id, usuario_id, descripcion, fecha_solicitud) VALUES (2, 5, 'Insisto, son mías', '2026-11-03 11:05:00');

-- PRUEBA: dos aceptadas sobre la misma entrega | espera: UNIQUE constraint failed: reclamaciones.entrega_id
INSERT INTO entregas (id, objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 2, 4, 3, 'Llavero rojo', '2026-11-03 10:00:00');
INSERT INTO reclamaciones (id, entrega_id, usuario_id, descripcion, fecha_solicitud) VALUES (10, 2, 5, 'Son mías', '2026-11-03 11:00:00');
INSERT INTO reclamaciones (id, entrega_id, usuario_id, descripcion, fecha_solicitud) VALUES (11, 2, 6, 'Son mías', '2026-11-03 11:10:00');
UPDATE reclamaciones SET estado = 'Aceptada', fecha_resolucion = '2026-11-03 12:00:00', resuelto_por = 3 WHERE id = 10;
-- FALLA
UPDATE reclamaciones SET estado = 'Aceptada', fecha_resolucion = '2026-11-03 12:05:00', resuelto_por = 3 WHERE id = 11;

-- PRUEBA: un estudiante acepta una reclamación | espera: Solo el personal activo acepta o rechaza reclamaciones
INSERT INTO entregas (id, objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 2, 4, 3, 'Llavero rojo', '2026-11-03 10:00:00');
INSERT INTO reclamaciones (id, entrega_id, usuario_id, descripcion, fecha_solicitud) VALUES (10, 2, 5, 'Son mías', '2026-11-03 11:00:00');
-- FALLA
UPDATE reclamaciones SET estado = 'Aceptada', fecha_resolucion = '2026-11-03 12:00:00', resuelto_por = 6 WHERE id = 10;

-- PRUEBA: aceptar sin indicar quién resolvió | espera: Solo el personal activo acepta o rechaza
INSERT INTO entregas (id, objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 2, 4, 3, 'Llavero rojo', '2026-11-03 10:00:00');
INSERT INTO reclamaciones (id, entrega_id, usuario_id, descripcion, fecha_solicitud) VALUES (10, 2, 5, 'Son mías', '2026-11-03 11:00:00');
-- FALLA
UPDATE reclamaciones SET estado = 'Aceptada', fecha_resolucion = '2026-11-03 12:00:00' WHERE id = 10;

-- PRUEBA: una pendiente con fecha de resolución | espera: CHECK constraint failed
INSERT INTO entregas (id, objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 2, 4, 3, 'Llavero rojo', '2026-11-03 10:00:00');
-- FALLA
INSERT INTO reclamaciones (entrega_id, usuario_id, descripcion, fecha_solicitud, fecha_resolucion) VALUES (2, 5, 'Mías', '2026-11-03 11:00:00', '2026-11-03 12:00:00');

-- PRUEBA: rechazar sin motivo | espera: CHECK constraint failed
INSERT INTO entregas (id, objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 2, 4, 3, 'Llavero rojo', '2026-11-03 10:00:00');
INSERT INTO reclamaciones (id, entrega_id, usuario_id, descripcion, fecha_solicitud) VALUES (10, 2, 5, 'Son mías', '2026-11-03 11:00:00');
-- FALLA
UPDATE reclamaciones SET estado = 'Rechazada', fecha_resolucion = '2026-11-03 12:00:00', resuelto_por = 3 WHERE id = 10;

-- PRUEBA: una cancelación con encargado | espera: CHECK constraint failed
INSERT INTO entregas (id, objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 2, 4, 3, 'Llavero rojo', '2026-11-03 10:00:00');
INSERT INTO reclamaciones (id, entrega_id, usuario_id, descripcion, fecha_solicitud) VALUES (10, 2, 5, 'Son mías', '2026-11-03 11:00:00');
-- FALLA
UPDATE reclamaciones SET estado = 'Cancelada', fecha_resolucion = '2026-11-03 12:00:00', resuelto_por = 3 WHERE id = 10;

-- PRUEBA: resolver antes de la solicitud | espera: CHECK constraint failed
INSERT INTO entregas (id, objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 2, 4, 3, 'Llavero rojo', '2026-11-03 10:00:00');
INSERT INTO reclamaciones (id, entrega_id, usuario_id, descripcion, fecha_solicitud) VALUES (10, 2, 5, 'Son mías', '2026-11-03 11:00:00');
-- FALLA
UPDATE reclamaciones SET estado = 'Aceptada', fecha_resolucion = '2026-11-01 08:00:00', resuelto_por = 3 WHERE id = 10;

-- PRUEBA: fecha de pérdida después de la solicitud | espera: CHECK constraint failed
INSERT INTO entregas (id, objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 2, 4, 3, 'Llavero rojo', '2026-11-03 10:00:00');
-- FALLA
INSERT INTO reclamaciones (entrega_id, usuario_id, descripcion, fecha_perdida, fecha_solicitud) VALUES (2, 5, 'Mías', '2026-12-31', '2026-11-03 11:00:00');

-- PRUEBA: lugar de pérdida vacío | espera: CHECK constraint failed
INSERT INTO entregas (id, objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 2, 4, 3, 'Llavero rojo', '2026-11-03 10:00:00');
-- FALLA
INSERT INTO reclamaciones (entrega_id, usuario_id, descripcion, lugar_perdida, fecha_solicitud) VALUES (2, 5, 'Mías', '', '2026-11-03 11:00:00');

-- PRUEBA: cambiar el autor de una reclamación pendiente | espera: No se cambia la entrega, el autor ni la fecha
INSERT INTO entregas (id, objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 2, 4, 3, 'Llavero rojo', '2026-11-03 10:00:00');
INSERT INTO reclamaciones (id, entrega_id, usuario_id, descripcion, fecha_solicitud) VALUES (10, 2, 5, 'Son mías', '2026-11-03 11:00:00');
-- FALLA
UPDATE reclamaciones SET usuario_id = 6 WHERE id = 10;

-- PRUEBA: reabrir una reclamación rechazada | espera: Una reclamación resuelta no se modifica
-- FALLA
UPDATE reclamaciones SET estado = 'Pendiente', fecha_resolucion = NULL, resuelto_por = NULL WHERE id = 2;

-- PRUEBA: corregir el texto de una reclamación ya aceptada | espera: Una reclamación resuelta no se modifica
-- FALLA
UPDATE reclamaciones SET respuesta = 'Otra nota' WHERE id = 1;

-- PRUEBA: borrar una reclamación | espera: Una reclamación no se borra
-- FALLA
DELETE FROM reclamaciones WHERE id = 3;

-- ======================= devoluciones =======================
-- PRUEBA: devolución de una reclamación rechazada | espera: Solo se registra la devolución de una reclamación aceptada
-- FALLA
INSERT INTO devoluciones (reclamacion_id, recibido_por, fecha_recepcion) VALUES (2, 3, '2026-11-03 10:00:00');

-- PRUEBA: segunda devolución de la misma reclamación | espera: UNIQUE constraint failed: devoluciones.reclamacion_id
-- FALLA
INSERT INTO devoluciones (reclamacion_id, recibido_por, fecha_recepcion) VALUES (1, 3, '2026-11-03 10:00:00');

-- PRUEBA: un estudiante recibe el objeto de vuelta | espera: Solo el personal activo recibe objetos de vuelta
INSERT INTO entregas (id, objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 2, 4, 3, 'Llavero rojo', '2026-11-03 10:00:00');
INSERT INTO reclamaciones (id, entrega_id, usuario_id, descripcion, fecha_solicitud) VALUES (10, 2, 5, 'Son mías', '2026-11-03 11:00:00');
UPDATE reclamaciones SET estado = 'Aceptada', fecha_resolucion = '2026-11-03 12:00:00', resuelto_por = 3 WHERE id = 10;
-- FALLA
INSERT INTO devoluciones (reclamacion_id, recibido_por, fecha_recepcion) VALUES (10, 5, '2026-11-03 13:00:00');

-- PRUEBA: devolución anterior a la aceptación | espera: La devolución no puede ser anterior a la aceptación
INSERT INTO entregas (id, objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 2, 4, 3, 'Llavero rojo', '2026-11-03 10:00:00');
INSERT INTO reclamaciones (id, entrega_id, usuario_id, descripcion, fecha_solicitud) VALUES (10, 2, 5, 'Son mías', '2026-11-03 11:00:00');
UPDATE reclamaciones SET estado = 'Aceptada', fecha_resolucion = '2026-11-03 12:00:00', resuelto_por = 3 WHERE id = 10;
-- FALLA
INSERT INTO devoluciones (reclamacion_id, recibido_por, fecha_recepcion) VALUES (10, 3, '2026-11-03 11:30:00');

-- PRUEBA: registrar los dos momentos de una sola vez | espera: El momento 2 se registra después
INSERT INTO entregas (id, objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 2, 4, 3, 'Llavero rojo', '2026-11-03 10:00:00');
INSERT INTO reclamaciones (id, entrega_id, usuario_id, descripcion, fecha_solicitud) VALUES (10, 2, 5, 'Son mías', '2026-11-03 11:00:00');
UPDATE reclamaciones SET estado = 'Aceptada', fecha_resolucion = '2026-11-03 12:00:00', resuelto_por = 3 WHERE id = 10;
-- FALLA
INSERT INTO devoluciones (reclamacion_id, recibido_por, fecha_recepcion, devuelto_por, fecha_devolucion) VALUES (10, 3, '2026-11-03 13:00:00', 2, '2026-11-03 14:00:00');

-- PRUEBA: momento 2 a medias (quién sin cuándo) | espera: CHECK constraint failed
INSERT INTO entregas (id, objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 2, 4, 3, 'Llavero rojo', '2026-11-03 10:00:00');
INSERT INTO reclamaciones (id, entrega_id, usuario_id, descripcion, fecha_solicitud) VALUES (10, 2, 5, 'Son mías', '2026-11-03 11:00:00');
UPDATE reclamaciones SET estado = 'Aceptada', fecha_resolucion = '2026-11-03 12:00:00', resuelto_por = 3 WHERE id = 10;
INSERT INTO devoluciones (id, reclamacion_id, recibido_por, fecha_recepcion) VALUES (2, 10, 3, '2026-11-03 13:00:00');
-- FALLA
UPDATE devoluciones SET devuelto_por = 2 WHERE id = 2;

-- PRUEBA: un estudiante devuelve el objeto al dueño | espera: Solo el personal activo devuelve objetos
INSERT INTO entregas (id, objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 2, 4, 3, 'Llavero rojo', '2026-11-03 10:00:00');
INSERT INTO reclamaciones (id, entrega_id, usuario_id, descripcion, fecha_solicitud) VALUES (10, 2, 5, 'Son mías', '2026-11-03 11:00:00');
UPDATE reclamaciones SET estado = 'Aceptada', fecha_resolucion = '2026-11-03 12:00:00', resuelto_por = 3 WHERE id = 10;
INSERT INTO devoluciones (id, reclamacion_id, recibido_por, fecha_recepcion) VALUES (2, 10, 3, '2026-11-03 13:00:00');
-- FALLA
UPDATE devoluciones SET devuelto_por = 4, fecha_devolucion = '2026-11-03 14:00:00' WHERE id = 2;

-- PRUEBA: devolver al dueño antes de recuperarlo | espera: CHECK constraint failed
INSERT INTO entregas (id, objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 2, 4, 3, 'Llavero rojo', '2026-11-03 10:00:00');
INSERT INTO reclamaciones (id, entrega_id, usuario_id, descripcion, fecha_solicitud) VALUES (10, 2, 5, 'Son mías', '2026-11-03 11:00:00');
UPDATE reclamaciones SET estado = 'Aceptada', fecha_resolucion = '2026-11-03 12:00:00', resuelto_por = 3 WHERE id = 10;
INSERT INTO devoluciones (id, reclamacion_id, recibido_por, fecha_recepcion) VALUES (2, 10, 3, '2026-11-03 13:00:00');
-- FALLA
UPDATE devoluciones SET devuelto_por = 2, fecha_devolucion = '2026-11-03 12:30:00' WHERE id = 2;

-- PRUEBA: completar una devolución dos veces | espera: Una devolución solo se completa una vez
-- FALLA
UPDATE devoluciones SET devuelto_por = 3, fecha_devolucion = '2026-11-04 09:00:00' WHERE id = 1;

-- PRUEBA: borrar una devolución | espera: Una devolución registrada no se borra
-- FALLA
DELETE FROM devoluciones WHERE id = 1;

-- ======================= historial =======================
-- PRUEBA: modificar el historial | espera: El historial no se modifica
-- FALLA
UPDATE historial SET accion = 'Registro' WHERE id = 1;

-- PRUEBA: borrar el historial | espera: El historial no se borra
-- FALLA
DELETE FROM historial WHERE id = 1;

-- PRUEBA: una acción del personal firmada por un estudiante | espera: Esta acción solo la hace el personal activo
-- FALLA
INSERT INTO historial (objeto_id, usuario_id, accion, fecha_hora) VALUES (2, 4, 'Foto', '2026-11-03 10:00:00');

-- PRUEBA: «Entrega» que deja el objeto «Activo» | espera: CHECK constraint failed
-- FALLA
INSERT INTO historial (objeto_id, usuario_id, accion, estado_nuevo, fecha_hora) VALUES (2, 3, 'Entrega', 'Activo', '2026-11-03 10:00:00');

-- PRUEBA: «Foto» con estado_nuevo | espera: CHECK constraint failed
-- FALLA
INSERT INTO historial (objeto_id, usuario_id, accion, estado_nuevo, fecha_hora) VALUES (2, 3, 'Foto', 'Activo', '2026-11-03 10:00:00');

-- PRUEBA: cambio de estado sin decir cómo quedó | espera: CHECK constraint failed
-- FALLA
INSERT INTO historial (objeto_id, usuario_id, accion, fecha_hora) VALUES (2, 3, 'Cambio de estado', '2026-11-03 10:00:00');

-- PRUEBA: el historial dice un estado distinto al real | espera: El historial debe decir el estado real del objeto
-- FALLA
INSERT INTO historial (objeto_id, usuario_id, accion, estado_nuevo, fecha_hora) VALUES (2, 3, 'Cambio de estado', 'En bodega', '2026-11-03 10:00:00');

-- PRUEBA: fecha y hora con formato incorrecto | espera: CHECK constraint failed
-- FALLA
INSERT INTO historial (objeto_id, usuario_id, accion, fecha_hora) VALUES (2, 3, 'Foto', '03/11/2026 10:00');

-- ======================= reportes_visitantes (v8.5) =======================
-- Caso base: el reporte 1 de Sofía (Localizado, relacionado con la mochila, un intento de WhatsApp fallido).
-- PRUEBA: reporte sin foto | espera: NOT NULL constraint failed
-- FALLA
INSERT INTO reportes_visitantes (codigo, token_hash, nombre, telefono, objeto_nombre, categoria, descripcion, lugar_perdida, fecha_perdida, fecha_registro) VALUES ('UAM-AAAA-BBBB', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'Ana', '8888 1111', 'Celular', 'Electrónicos', 'Negro', 'Cafetería', '2026-11-01', '2026-11-01 10:00:00');

-- PRUEBA: foto que no es JPEG ni WebP (PNG) | espera: CHECK constraint failed
-- FALLA
INSERT INTO reportes_visitantes (codigo, token_hash, nombre, telefono, objeto_nombre, categoria, descripcion, lugar_perdida, fecha_perdida, fecha_registro, foto) VALUES ('UAM-AAAA-BBBB', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'Ana', '8888 1111', 'Celular', 'Electrónicos', 'Negro', 'Cafetería', '2026-11-01', '2026-11-01 10:00:00', X'89504E470D0A1A0A');

-- PRUEBA: código con otro formato | espera: CHECK constraint failed
-- FALLA
INSERT INTO reportes_visitantes (codigo, token_hash, nombre, telefono, objeto_nombre, categoria, descripcion, lugar_perdida, fecha_perdida, fecha_registro, foto) VALUES ('REP-1', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'Ana', '8888 1111', 'Celular', 'Electrónicos', 'Negro', 'Cafetería', '2026-11-01', '2026-11-01 10:00:00', X'FFD8FFE000104A46494600FFD9');

-- PRUEBA: código repetido | espera: UNIQUE constraint failed
-- FALLA
INSERT INTO reportes_visitantes (codigo, token_hash, nombre, telefono, objeto_nombre, categoria, descripcion, lugar_perdida, fecha_perdida, fecha_registro, foto) VALUES ('UAM-7K3P-Q9XD', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'Ana', '8888 1111', 'Celular', 'Electrónicos', 'Negro', 'Cafetería', '2026-11-01', '2026-11-01 10:00:00', X'FFD8FFE000104A46494600FFD9');

-- PRUEBA: token de seguimiento que no es un SHA-256 | espera: CHECK constraint failed
-- FALLA
INSERT INTO reportes_visitantes (codigo, token_hash, nombre, telefono, objeto_nombre, categoria, descripcion, lugar_perdida, fecha_perdida, fecha_registro, foto) VALUES ('UAM-AAAA-BBBB', 'enlace-en-texto-plano', 'Ana', '8888 1111', 'Celular', 'Electrónicos', 'Negro', 'Cafetería', '2026-11-01', '2026-11-01 10:00:00', X'FFD8FFE000104A46494600FFD9');

-- PRUEBA: categoría inventada | espera: CHECK constraint failed
-- FALLA
INSERT INTO reportes_visitantes (codigo, token_hash, nombre, telefono, objeto_nombre, categoria, descripcion, lugar_perdida, fecha_perdida, fecha_registro, foto) VALUES ('UAM-AAAA-BBBB', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'Ana', '8888 1111', 'Celular', 'Mascotas', 'Negro', 'Cafetería', '2026-11-01', '2026-11-01 10:00:00', X'FFD8FFE000104A46494600FFD9');

-- PRUEBA: correo sin formato de correo | espera: CHECK constraint failed
-- FALLA
INSERT INTO reportes_visitantes (codigo, token_hash, nombre, telefono, correo, objeto_nombre, categoria, descripcion, lugar_perdida, fecha_perdida, fecha_registro, foto) VALUES ('UAM-AAAA-BBBB', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'Ana', '8888 1111', 'ana-arroba-correo', 'Celular', 'Electrónicos', 'Negro', 'Cafetería', '2026-11-01', '2026-11-01 10:00:00', X'FFD8FFE000104A46494600FFD9');

-- PRUEBA: se perdió después de reportarlo | espera: CHECK constraint failed
-- FALLA
INSERT INTO reportes_visitantes (codigo, token_hash, nombre, telefono, objeto_nombre, categoria, descripcion, lugar_perdida, fecha_perdida, fecha_registro, foto) VALUES ('UAM-AAAA-BBBB', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'Ana', '8888 1111', 'Celular', 'Electrónicos', 'Negro', 'Cafetería', '2026-11-05', '2026-11-01 10:00:00', X'FFD8FFE000104A46494600FFD9');

-- PRUEBA: reporte nuevo que ya nace «Localizado» | espera: Un reporte de visitante nuevo empieza Pendiente
-- FALLA
INSERT INTO reportes_visitantes (codigo, token_hash, nombre, telefono, objeto_nombre, categoria, descripcion, lugar_perdida, fecha_perdida, fecha_registro, estado, foto) VALUES ('UAM-AAAA-BBBB', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'Ana', '8888 1111', 'Celular', 'Electrónicos', 'Negro', 'Cafetería', '2026-11-01', '2026-11-01 10:00:00', 'Localizado', X'FFD8FFE000104A46494600FFD9');

-- PRUEBA: reporte nuevo ya relacionado con un objeto | espera: Un reporte de visitante nuevo empieza Pendiente
-- FALLA
INSERT INTO reportes_visitantes (codigo, token_hash, nombre, telefono, objeto_nombre, categoria, descripcion, lugar_perdida, fecha_perdida, fecha_registro, objeto_id, foto) VALUES ('UAM-AAAA-BBBB', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'Ana', '8888 1111', 'Celular', 'Electrónicos', 'Negro', 'Cafetería', '2026-11-01', '2026-11-01 10:00:00', 2, X'FFD8FFE000104A46494600FFD9');

-- PRUEBA: reporte nuevo con un aviso de WhatsApp «ya enviado» | espera: Un reporte de visitante nuevo empieza Pendiente
-- FALLA
INSERT INTO reportes_visitantes (codigo, token_hash, nombre, telefono, objeto_nombre, categoria, descripcion, lugar_perdida, fecha_perdida, fecha_registro, whatsapp_estado, whatsapp_intentos, whatsapp_fecha, whatsapp_detalle, foto) VALUES ('UAM-AAAA-BBBB', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'Ana', '8888 1111', 'Celular', 'Electrónicos', 'Negro', 'Cafetería', '2026-11-01', '2026-11-01 10:00:00', 'Enviada', 1, '2026-11-01 10:00:01', 'wamid.falso', X'FFD8FFE000104A46494600FFD9');

-- PRUEBA: cambiar el teléfono que dio el visitante | espera: Lo que reportó el visitante no se modifica
-- FALLA
UPDATE reportes_visitantes SET telefono = '8000 0000' WHERE id = 1;

-- PRUEBA: cambiar la foto del reporte | espera: Lo que reportó el visitante no se modifica
-- FALLA
UPDATE reportes_visitantes SET foto = X'FFD8FF00FFD9' WHERE id = 1;

-- PRUEBA: cambiar el código del reporte | espera: Lo que reportó el visitante no se modifica
-- FALLA
UPDATE reportes_visitantes SET codigo = 'UAM-ZZZZ-ZZZZ' WHERE id = 1;

-- PRUEBA: un estudiante gestiona un reporte | espera: Solo el personal activo gestiona los reportes de visitantes
-- FALLA
UPDATE reportes_visitantes SET estado = 'Cerrado', actualizado_por = 4, fecha_actualizacion = '2026-11-01 10:00:00' WHERE id = 1;

-- PRUEBA: la encargada desactivada gestiona un reporte | espera: Solo el personal activo gestiona los reportes de visitantes
-- FALLA
UPDATE reportes_visitantes SET observaciones = 'Revisado', actualizado_por = 10, fecha_actualizacion = '2026-11-01 10:00:00' WHERE id = 1;

-- PRUEBA: estado de reporte inventado | espera: CHECK constraint failed
-- FALLA
UPDATE reportes_visitantes SET estado = 'Perdido', actualizado_por = 2, fecha_actualizacion = '2026-11-01 10:00:00' WHERE id = 1;

-- PRUEBA: relacionar un objeto que no existe | espera: FOREIGN KEY constraint failed
-- FALLA
UPDATE reportes_visitantes SET objeto_id = 999, actualizado_por = 2, fecha_actualizacion = '2026-11-01 10:00:00' WHERE id = 1;

-- PRUEBA: gestión con fecha anterior al reporte | espera: CHECK constraint failed
-- FALLA
UPDATE reportes_visitantes SET estado = 'Cerrado', actualizado_por = 2, fecha_actualizacion = '2026-10-01 10:00:00' WHERE id = 1;

-- PRUEBA: «borrar» un intento fallido de WhatsApp | espera: Los intentos de WhatsApp solo aumentan
-- FALLA
UPDATE reportes_visitantes SET whatsapp_estado = 'Pendiente', whatsapp_intentos = 0 WHERE id = 1;

-- PRUEBA: WhatsApp «Enviada» sin id del mensaje | espera: CHECK constraint failed
-- FALLA
UPDATE reportes_visitantes SET whatsapp_estado = 'Enviada', whatsapp_intentos = 2, whatsapp_detalle = NULL WHERE id = 1;

-- PRUEBA: borrar un reporte de visitante | espera: Un reporte de visitante no se borra
-- FALLA
DELETE FROM reportes_visitantes WHERE id = 1;
