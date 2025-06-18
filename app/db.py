import mysql.connector
from mysql.connector import Error

def conectar_mysql():
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",  # o tu contraseña si tienes una
            database="integracion"
        )
        return connection
    except Error as e:
        print("Error al conectar a MySQL:", e)
        return None
