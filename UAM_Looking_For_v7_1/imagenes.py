"""Revisa las fotos que llegan al servidor, sin librerías.

El navegador ya las reduce y comprime (ver templates/foto_script.html). Aquí se comprueba de nuevo, leyendo
la cabecera del archivo, que sea de verdad WebP o JPEG, que no pase del peso ni de las dimensiones máximas
y que no esté cortada. Así nadie puede guardar una foto enorme aunque se salte el formulario.
"""
PESO_MAXIMO = 300 * 1024   # 300 KB (igual que el CHECK de objetos.foto)
LADO_MAXIMO = 1280         # píxeles del lado más largo


# Ancho y alto de un JPEG: se recorren sus bloques hasta el que describe la imagen (marcador SOF).
def medir_jpeg(d):
    if d[-2:] != b'\xff\xd9':          # un JPEG completo termina con FFD9
        return None
    i = 2
    while i + 9 < len(d):
        if d[i] != 0xFF:
            return None
        marcador = d[i + 1]
        if marcador == 0xFF:            # byte de relleno
            i += 1
            continue
        if 0xC0 <= marcador <= 0xCF and marcador not in (0xC4, 0xC8, 0xCC):
            return int.from_bytes(d[i + 7:i + 9], 'big'), int.from_bytes(d[i + 5:i + 7], 'big')
        i += 2 + int.from_bytes(d[i + 2:i + 4], 'big')
    return None


# Ancho y alto de un WebP según su tipo de bloque: con pérdida (VP8), sin pérdida (VP8L) o extendido (VP8X).
def medir_webp(d):
    if int.from_bytes(d[4:8], 'little') + 8 != len(d):   # el tamaño declarado no coincide: archivo cortado
        return None
    bloque = d[12:16]
    if bloque == b'VP8 ' and d[23:26] == b'\x9d\x01\x2a':
        return int.from_bytes(d[26:28], 'little') & 0x3FFF, int.from_bytes(d[28:30], 'little') & 0x3FFF
    if bloque == b'VP8L' and d[20] == 0x2F:
        bits = int.from_bytes(d[21:25], 'little')
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if bloque == b'VP8X':
        return int.from_bytes(d[24:27], 'little') + 1, int.from_bytes(d[27:30], 'little') + 1
    return None


# Formato real según los primeros bytes (no según la extensión del archivo).
def formato(datos):
    if datos[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    if datos[:4] == b'RIFF' and datos[8:12] == b'WEBP':
        return 'image/webp'
    return None


# Devuelve (True, datos), (True, None) si no se subió foto, o (False, mensaje).
def revisar(archivo):
    if not archivo or not archivo.filename:
        return True, None
    datos = archivo.read(PESO_MAXIMO + 1)
    if len(datos) > PESO_MAXIMO:
        return False, ('La foto pesa más de 300 KB. El formulario la reduce sola antes de enviarla: '
                       'recarga la página y vuelve a elegirla (si el problema sigue, usa otro navegador).')
    tipo = formato(datos)
    if not tipo:
        return False, 'Formato no aceptado. Sube una foto JPG, PNG o WebP desde el formulario.'
    medidas = (medir_jpeg if tipo == 'image/jpeg' else medir_webp)(datos)
    if not medidas or min(medidas) < 1:
        return False, 'La foto está dañada o incompleta. Vuelve a elegirla.'
    if max(medidas) > LADO_MAXIMO:
        return False, f'La foto mide {medidas[0]}×{medidas[1]} px; el máximo es {LADO_MAXIMO} px por lado.'
    return True, datos
