"""Configuración de UAM Looking For v7.1: archivo .env, roles, categorías y estados."""

RUTA_ENV = '.env'

ROL_ADMIN, ROL_ENCARGADO, ROL_ESTUDIANTE = 'Administrador', 'Encargado', 'Estudiante'
ROLES_GESTIONABLES = (ROL_ESTUDIANTE, ROL_ENCARGADO)   # los que crea el administrador
ROLES_PERSONAL = (ROL_ADMIN, ROL_ENCARGADO)

# Categoría y estado -> ícono (deben coincidir con los CHECK de schema.sql)
CATEGORIAS = {'Electrónicos': 'laptop', 'Documentos/Carné': 'carne', 'Ropa/Accesorios': 'camisa',
              'Llaves': 'llave', 'Útiles/Libros': 'libro', 'Otros': 'paquete'}
# Los tres primeros los pone el personal a mano; los demás los pone la base según los hechos registrados.
ESTADOS = {'Activo': 'activo', 'En resguardo': 'escudo', 'En bodega': 'bodega', 'Entregado': 'check',
           'Por recuperar': 'historial', 'Recuperado': 'bandeja', 'Devuelto': 'mano'}
ESTADOS_MANUALES = ('Activo', 'En resguardo', 'En bodega')   # bajo custodia
ESTADOS_RECLAMACION = ('Pendiente', 'Aceptada', 'Rechazada', 'Cancelada')
TIPOS_PERSONA = ('Estudiante', 'Docente', 'Administrativo', 'Visitante')   # quien trae o retira un objeto
# Puntos de resguardo. Para agregar uno nuevo basta con sumarlo aquí: la base no cambia.
UBICACIONES = ('Vida Estudiantil', 'Sala Docente', 'Edificio A')
MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
         'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')


# Lee el .env (líneas CLAVE=valor, admite comentarios y comillas). Si no existe, devuelve {}.
def leer_env():
    valores = {}
    try:
        with open(RUTA_ENV, encoding='utf-8') as archivo:
            for linea in archivo:
                linea = linea.strip()
                if linea and not linea.startswith('#') and '=' in linea:
                    clave, valor = (parte.strip() for parte in linea.split('=', 1))
                    if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in '"\'':
                        valor = valor[1:-1]
                    valores[clave] = valor
    except OSError:
        pass
    return valores
