import mysql.connector
from mysql.connector import Error
import logging

# Configurar logging para debug
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def conectar_mysql():
    """
    Función para conectar a MySQL con manejo de errores mejorado
    """
    connection = None
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",  # Cambia si tienes contraseña
            database="integracion",
            autocommit=True,  # Para evitar problemas de transacciones
            pool_name="mypool",
            pool_size=5,
            pool_reset_session=True,
            connection_timeout=10,
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
        
        if connection.is_connected():
            logger.info("✅ Conexión exitosa a MySQL")
            return connection
            
    except Error as e:
        logger.error(f"❌ Error al conectar a MySQL: {e}")
        print(f"Error al conectar a MySQL: {e}")
        
        # Sugerencias de solución según el tipo de error
        if "Can't connect" in str(e):
            print("💡 Sugerencia: Verifica que MySQL esté ejecutándose")
            print("   - Windows: Servicios -> MySQL")
            print("   - macOS: brew services start mysql")
            print("   - Linux: sudo systemctl start mysql")
        elif "Access denied" in str(e):
            print("💡 Sugerencia: Verifica usuario y contraseña")
        elif "Unknown database" in str(e):
            print("💡 Sugerencia: Crea la base de datos 'integracion'")
            
        return None
        
    except Exception as e:
        logger.error(f"❌ Error inesperado: {e}")
        print(f"Error inesperado: {e}")
        return None