"""Constantes del sistema (roles, categorías, estados) y lectura del archivo .env.

Los valores que también revisa la base (CHECK de schema.sql) deben coincidir con los de aquí.
"""

ROL_ADMIN, ROL_ENCARGADO, ROL_ESTUDIANTE = 'Administrador', 'Encargado', 'Estudiante'
ROLES_GESTIONABLES = (ROL_ESTUDIANTE, ROL_ENCARGADO)   # los que crea el administrador desde el panel
ROLES_PERSONAL = (ROL_ADMIN, ROL_ENCARGADO)

# Categoría -> ícono
CATEGORIAS = {'Electrónicos': 'laptop', 'Documentos/Carné': 'carne', 'Ropa/Accesorios': 'camisa',
              'Llaves': 'llave', 'Útiles/Libros': 'libro', 'Otros': 'paquete'}

# Estado del objeto -> ícono. Los tres primeros los pone el personal a mano (bajo custodia);
# los demás los pone la base según los hechos registrados (entrega, reclamación, devolución).
ESTADOS = {'Activo': 'activo', 'En resguardo': 'escudo', 'En bodega': 'bodega', 'Entregado': 'check',
           'Por recuperar': 'historial', 'Recuperado': 'bandeja', 'Devuelto': 'mano'}
ESTADOS_MANUALES = ('Activo', 'En resguardo', 'En bodega')

# v9: las reclamaciones ya no se cancelan. «Cancelada» solo existe en reclamaciones antiguas (se siguen mostrando).
ESTADOS_RECLAMACION = ('Pendiente', 'Aceptada', 'Rechazada')
ESTADO_RECLAMACION_ANTIGUO = 'Cancelada'

TIPOS_PERSONA = ('Estudiante', 'Docente', 'Administrativo', 'Visitante')   # quien trae o retira un objeto

# Reportes de visitantes: estado -> clase CSS
ESTADOS_REPORTE = {'Pendiente': 'pendiente', 'En revisión': 'revision', 'Localizado': 'localizado',
                   'Resuelto': 'resuelto', 'Cerrado': 'cerrado'}

CODIGO_PAIS = '505'   # Nicaragua: se antepone a los teléfonos de 8 dígitos para los enlaces de WhatsApp

# Puntos de resguardo. Para agregar uno basta con sumarlo aquí: la base no cambia.
UBICACIONES = ('Vida Estudiantil', 'Sala Docente', 'Edificio A')

MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
         'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')

# Largos máximos de los textos que escribe la gente (el formulario los limita y el servidor lo vuelve a revisar).
LARGO_MAXIMO = {'nombre': 100, 'cif': 20, 'correo': 120, 'telefono': 30, 'carrera': 100, 'titulo': 150,
                'descripcion': 2000, 'descripcion_publica': 500, 'lugar': 200, 'senas': 1000, 'nota': 1000,
                'observaciones': 2000, 'contrasena': 128}

TAMANO_MAXIMO_ENVIO = 2 * 1024 * 1024   # bytes: Flask corta cualquier envío mayor antes de leerlo


def leer_env(ruta):
    """Lee un archivo .env (líneas CLAVE=valor; admite comentarios y comillas). Si no existe, devuelve {}."""
    valores = {}
    try:
        with open(ruta, encoding='utf-8') as archivo:
            for linea in archivo:
                linea = linea.strip()
                if not linea or linea.startswith('#') or '=' not in linea:
                    continue
                clave, valor = (parte.strip() for parte in linea.split('=', 1))
                if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in '"\'':
                    valor = valor[1:-1]
                valores[clave] = valor
    except OSError:
        pass
    return valores
