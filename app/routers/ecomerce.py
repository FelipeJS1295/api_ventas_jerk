from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from app.db import conectar_mysql  # Usa tu conexión actual a la base de datos
from datetime import datetime
from typing import Optional
from fastapi import UploadFile, File, Form
import os
import uuid
import shutil
from PIL import Image
from pathlib import Path
import logging

router = APIRouter()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def procesar_url_imagen(img_path):
    """
    Convierte rutas de imagen de la BD a URLs accesibles desde /var/www/imagenes_jhk/productos
    """
    if not img_path:
        return "/static/images/no-image.jpg"
    
    # Si ya es una URL completa HTTP, devolverla tal como está
    if img_path.startswith(('http://', 'https://')):
        return img_path
    
    # Limpiar la ruta
    clean_path = img_path.strip()
    
    if not clean_path:
        return "/static/images/no-image.jpg"
    
    # Detectar si estamos en desarrollo local o producción
    is_local_dev = os.getenv('ENVIRONMENT', 'development') == 'development'
    
    if is_local_dev:
        # En desarrollo local, usar imagen por defecto
        return "/static/images/no-image.jpg"
    
    # Extraer el nombre del archivo desde diferentes formatos posibles
    filename = None
    
    if clean_path.startswith('/imagenes/productos/'):
        # Formato correcto: /imagenes/productos/archivo.jpg (como se guarda en productos.py)
        filename = clean_path.replace('/imagenes/productos/', '')
    elif clean_path.startswith('imagenes/productos/'):
        # Formato: imagenes/productos/archivo.jpg
        filename = clean_path.replace('imagenes/productos/', '')
    elif clean_path.startswith('/imagenes_jhk/productos/'):
        # Formato legacy: /imagenes_jhk/productos/archivo.jpg
        filename = clean_path.replace('/imagenes_jhk/productos/', '')
    elif clean_path.startswith('/images/productos/'):
        # Formato legacy: /images/productos/archivo.jpg
        filename = clean_path.replace('/images/productos/', '')
    elif 'productos/' in clean_path:
        # Por si hay variaciones en la ruta
        filename = clean_path.split('productos/')[-1]
    elif '/' not in clean_path and '.' in clean_path:
        # Solo el nombre del archivo
        filename = clean_path
    else:
        # Si no tiene el formato esperado, usar imagen por defecto
        logger.warning(f"⚠️ Formato de imagen no reconocido: {clean_path}")
        return "/static/images/no-image.jpg"
    
    if not filename or not filename.strip():
        return "/static/images/no-image.jpg"
    
    # Las imágenes están servidas directamente por Nginx desde /var/www/imagenes_jhk/productos
    # y son accesibles en /imagenes/productos/ según la configuración de Nginx
    return f"/imagenes/productos/{filename.strip()}"

# Configuración de directorios
UPLOAD_DIR = Path("/var/www/v4_python_jerk/static/images/productos")
THUMBNAILS_DIR = Path("/var/www/v4_python_jerk/static/images/productos/thumbnails")
TEMP_DIR = Path("/var/www/v4_python_jerk/uploads/temp")
BASE_URL = "http://147.79.74.244:8080/images/productos"

def obtener_conexion_segura():
    """
    Función helper para obtener conexión con manejo de errores.
    """
    try:
        conn = conectar_mysql()
        if conn is None:
            logger.error("❌ No se pudo conectar a la base de datos")
            raise HTTPException(status_code=500, detail="Error de conexión a la base de datos")
        
        if not conn.is_connected():
            logger.error("❌ La conexión no está activa")
            raise HTTPException(status_code=500, detail="Conexión a la base de datos inactiva")
            
        return conn
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error en obtener_conexion_segura: {e}")
        raise HTTPException(status_code=500, detail=f"Error de conexión: {str(e)}")

@router.get("/", response_class=HTMLResponse)
def root(request: Request):
    """Página de inicio"""
    try:
        return request.app.state.templates.TemplateResponse("inicio.html", {
            "request": request
        })
    except Exception as e:
        logger.error(f"❌ Error en ruta raíz: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@router.get("/productos", response_class=HTMLResponse)
def vista_productos(request: Request, tipo: Optional[str] = Query(None)):
    """
    Página principal de productos con filtrado.
    """
    conn = None
    cursor = None
    
    try:
        logger.info(f"🔍 Consultando productos. Filtro tipo: {tipo}")
        
        conn = obtener_conexion_segura()
        cursor = conn.cursor(dictionary=True, buffered=True)

        # Query para obtener productos válidos
        base_query = """
            SELECT 
                id,
                nombre,
                precio_venta,
                precio_descuento,
                img_1 AS imagen,
                descripcion_producto,
                tipo_producto,
                material,
                colores_disponibles,
                dimensiones,
                tiempo_entrega,
                COALESCE(visitas, 0) as visitas
            FROM productos
            WHERE 1=1
                AND (tipo_producto_venta = 'local' OR tipo_producto_venta IS NULL)
                AND img_1 IS NOT NULL 
                AND img_1 != '' 
                AND TRIM(img_1) != ''
                AND LENGTH(TRIM(img_1)) > 5
                AND precio_venta IS NOT NULL
                AND precio_venta > 0
                AND nombre IS NOT NULL 
                AND TRIM(nombre) != ''
        """

        params = []
        
        if tipo:
            base_query += " AND tipo_producto LIKE %s"
            params.append(f"%{tipo}%")

        base_query += """
            ORDER BY visitas DESC, precio_venta ASC 
            LIMIT 100
        """

        cursor.execute(base_query, params)
        productos = cursor.fetchall()

        logger.info(f"✅ Se encontraron {len(productos)} productos válidos")

        # Procesar URLs de imágenes
        for producto in productos:
            try:
                if producto.get('imagen'):
                    imagen_limpia = producto['imagen'].strip()
                    if imagen_limpia and len(imagen_limpia) > 5:
                        producto['imagen'] = procesar_url_imagen(imagen_limpia)
                        logger.debug(f"🖼️ Imagen procesada: {imagen_limpia} -> {producto['imagen']}")
                    else:
                        logger.warning(f"⚠️ Imagen inválida para producto {producto.get('id')}")
                        producto['imagen'] = "/static/images/no-image.jpg"
                else:
                    producto['imagen'] = "/static/images/no-image.jpg"
            except Exception as e:
                logger.warning(f"⚠️ Error procesando imagen para producto {producto.get('id')}: {e}")
                producto['imagen'] = "/static/images/no-image.jpg"

        # Título dinámico
        titulo_pagina = "Todos los Productos"
        descripcion = "Descubre nuestra colección completa de muebles premium"

        if tipo:
            tipo_lower = tipo.lower()
            if tipo_lower in ["cama", "camas"]:
                titulo_pagina = "Camas"
                descripcion = "Camas cómodas para el descanso perfecto"
            elif tipo_lower in ["seccional", "seccionales"]:
                titulo_pagina = "Sofás Seccionales"
                descripcion = "Sofás seccionales modulares para espacios amplios"
            elif tipo_lower in ["sofa", "sofas"]:
                titulo_pagina = "Sofás"
                descripcion = "Sofás cómodos y elegantes para tu hogar"
            else:
                titulo_pagina = f"{tipo.title()}"
                descripcion = f"Productos de {tipo}"

        return request.app.state.templates.TemplateResponse("productos.html", {
            "request": request,
            "productos": productos,
            "titulo_pagina": titulo_pagina,
            "descripcion": descripcion,
            "filtro_activo": tipo,
            "now": datetime.now
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error inesperado en vista_productos: {e}")
        import traceback
        traceback.print_exc()
        
        return request.app.state.templates.TemplateResponse("productos.html", {
            "request": request,
            "productos": [],
            "titulo_pagina": "Productos",
            "descripcion": "Nuestros productos",
            "filtro_activo": tipo,
            "now": datetime.now,
            "error_message": f"Error cargando productos: {str(e)}"
        })
        
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if conn and conn.is_connected():
            try:
                conn.close()
            except:
                pass

@router.get("/inicio", response_class=HTMLResponse)
def vista_inicio(request: Request):
    """
    Página de inicio con hero y productos destacados.
    """
    try:
        return request.app.state.templates.TemplateResponse("inicio.html", {
            "request": request,
            "now": datetime.now
        })
    except Exception as e:
        logger.error(f"❌ Error en vista_inicio: {e}")
        raise HTTPException(status_code=500, detail="Error cargando página de inicio")

@router.get("/nosotros", response_class=HTMLResponse)
def vista_nosotros(request: Request):
    """
    Página Nosotros - Historia, visión, misión y equipo de Jerk Home.
    """
    try:
        return request.app.state.templates.TemplateResponse("nosotros.html", {
            "request": request,
            "now": datetime.now
        })
    except Exception as e:
        logger.error(f"❌ Error en vista_nosotros: {e}")
        raise HTTPException(status_code=500, detail="Error cargando página nosotros")

@router.get("/ecomerce", response_class=HTMLResponse)
def vista_publica_ecomerce(request: Request):
    """
    Página pública del ecommerce que muestra el catálogo de productos.
    """
    conn = None
    cursor = None
    
    try:
        conn = obtener_conexion_segura()
        cursor = conn.cursor(dictionary=True, buffered=True)

        # Consulta productos básicos - todos excepto externos
        cursor.execute("""
            SELECT 
                id,
                nombre,
                precio_venta,
                img_1 AS imagen,
                descripcion_producto,
                tipo_producto,
                material,
                colores_disponibles,
                dimensiones,
                precio_descuento
            FROM productos
            WHERE (tipo_producto_venta != 'externo' OR tipo_producto_venta IS NULL)
            ORDER BY RAND()
            LIMIT 20
        """)
        productos = cursor.fetchall()

        # Procesar URLs de imágenes
        for producto in productos:
            try:
                if producto.get('imagen'):
                    producto['imagen'] = procesar_url_imagen(producto['imagen'])
            except Exception as e:
                logger.warning(f"⚠️ Error procesando imagen: {e}")
                producto['imagen'] = "/static/images/no-image.jpg"

        return request.app.state.templates.TemplateResponse("index.html", {
            "request": request,
            "productos": productos,
            "now": datetime.now  # Para usar el año en el footer
        })
        
    except Exception as e:
        logger.error(f"❌ Error en vista_publica_ecomerce: {e}")
        return request.app.state.templates.TemplateResponse("index.html", {
            "request": request,
            "productos": [],
            "now": datetime.now,
            "error_message": "Error cargando productos"
        })
        
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if conn and conn.is_connected():
            try:
                conn.close()
            except:
                pass

@router.get("/sofas", response_class=HTMLResponse)
def vista_sofas(request: Request, categoria: Optional[str] = Query(None)):
    """
    Página específica de sofás.
    """
    conn = None
    cursor = None
    
    try:
        conn = obtener_conexion_segura()
        cursor = conn.cursor(dictionary=True, buffered=True)

        # Filtrar por tipo de producto y nombre - todos excepto externos
        where_clause = """WHERE (tipo_producto_venta != 'externo' OR tipo_producto_venta IS NULL)
                          AND (tipo_producto IN ('seccionales', 'sofas') 
                                OR nombre LIKE '%sofa%' 
                                OR nombre LIKE '%sillon%'
                                OR descripcion_producto LIKE '%sofa%')"""
        
        params = []
        if categoria:
            where_clause += " AND tipo_producto LIKE %s"
            params.append(f"%{categoria}%")

        query = f"""
            SELECT 
                id,
                nombre,
                precio_venta,
                img_1 AS imagen,
                descripcion_producto,
                tipo_producto,
                material,
                colores_disponibles,
                dimensiones,
                precio_descuento
            FROM productos
            {where_clause}
            AND img_1 IS NOT NULL AND precio_venta > 0
            ORDER BY precio_venta ASC
        """

        cursor.execute(query, params)
        productos = cursor.fetchall()

        # Procesar URLs de imágenes
        for producto in productos:
            try:
                if producto.get('imagen'):
                    producto['imagen'] = procesar_url_imagen(producto['imagen'])
            except Exception as e:
                logger.warning(f"⚠️ Error procesando imagen: {e}")
                producto['imagen'] = "/static/images/no-image.jpg"

        return request.app.state.templates.TemplateResponse("categoria.html", {
            "request": request,
            "productos": productos,
            "categoria_titulo": "Sofás",
            "categoria_descripcion": "Descubre nuestra colección de sofás cómodos y elegantes",
            "now": datetime.now
        })
        
    except Exception as e:
        logger.error(f"❌ Error en vista_sofas: {e}")
        return request.app.state.templates.TemplateResponse("categoria.html", {
            "request": request,
            "productos": [],
            "categoria_titulo": "Sofás",
            "categoria_descripcion": "Descubre nuestra colección de sofás cómodos y elegantes",
            "now": datetime.now,
            "error_message": "Error cargando sofás"
        })
        
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if conn and conn.is_connected():
            try:
                conn.close()
            except:
                pass

@router.get("/seccionales", response_class=HTMLResponse)
def vista_seccionales(request: Request):
    """
    Página específica de sofás seccionales.
    """
    conn = None
    cursor = None
    
    try:
        conn = obtener_conexion_segura()
        cursor = conn.cursor(dictionary=True, buffered=True)

        cursor.execute("""
            SELECT 
                id,
                nombre,
                precio_venta,
                img_1 AS imagen,
                descripcion_producto,
                tipo_producto,
                material,
                colores_disponibles,
                dimensiones,
                precio_descuento
            FROM productos
            WHERE (tipo_producto_venta != 'externo' OR tipo_producto_venta IS NULL)
            AND (tipo_producto = 'seccionales' 
                   OR nombre LIKE '%seccional%'
                   OR descripcion_producto LIKE '%seccional%')
            ORDER BY precio_venta ASC
        """)
        productos = cursor.fetchall()

        # Procesar URLs de imágenes
        for producto in productos:
            try:
                if producto.get('imagen'):
                    producto['imagen'] = procesar_url_imagen(producto['imagen'])
            except Exception as e:
                logger.warning(f"⚠️ Error procesando imagen: {e}")
                producto['imagen'] = "/static/images/no-image.jpg"

        return request.app.state.templates.TemplateResponse("categoria.html", {
            "request": request,
            "productos": productos,
            "categoria_titulo": "Sofás Seccionales",
            "categoria_descripcion": "Sofás seccionales modulares para espacios amplios y versátiles",
            "now": datetime.now
        })
        
    except Exception as e:
        logger.error(f"❌ Error en vista_seccionales: {e}")
        return request.app.state.templates.TemplateResponse("categoria.html", {
            "request": request,
            "productos": [],
            "categoria_titulo": "Sofás Seccionales",
            "categoria_descripcion": "Sofás seccionales modulares para espacios amplios y versátiles",
            "now": datetime.now,
            "error_message": "Error cargando seccionales"
        })
        
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if conn and conn.is_connected():
            try:
                conn.close()
            except:
                pass

@router.get("/decoracion", response_class=HTMLResponse)
def vista_decoracion(request: Request):
    """
    Página específica de decoración.
    """
    conn = None
    cursor = None
    
    try:
        conn = obtener_conexion_segura()
        cursor = conn.cursor(dictionary=True, buffered=True)

        cursor.execute("""
            SELECT 
                id,
                nombre,
                precio_venta,
                img_1 AS imagen,
                descripcion_producto,
                tipo_producto,
                material,
                colores_disponibles,
                dimensiones,
                precio_descuento
            FROM productos
            WHERE (tipo_producto_venta != 'externo' OR tipo_producto_venta IS NULL)
            AND (tipo_producto NOT IN ('seccionales', 'sofas', 'camas') 
                   OR nombre LIKE '%mesa%' 
                   OR nombre LIKE '%decoracion%'
                   OR nombre LIKE '%accesorio%'
                   OR descripcion_producto LIKE '%decorativo%')
            ORDER BY precio_venta ASC
        """)
        productos = cursor.fetchall()

        # Procesar URLs de imágenes
        for producto in productos:
            try:
                if producto.get('imagen'):
                    producto['imagen'] = procesar_url_imagen(producto['imagen'])
            except Exception as e:
                logger.warning(f"⚠️ Error procesando imagen: {e}")
                producto['imagen'] = "/static/images/no-image.jpg"

        return request.app.state.templates.TemplateResponse("categoria.html", {
            "request": request,
            "productos": productos,
            "categoria_titulo": "Decoración",
            "categoria_descripcion": "Complementos perfectos para completar tu hogar",
            "now": datetime.now
        })
        
    except Exception as e:
        logger.error(f"❌ Error en vista_decoracion: {e}")
        return request.app.state.templates.TemplateResponse("categoria.html", {
            "request": request,
            "productos": [],
            "categoria_titulo": "Decoración",
            "categoria_descripcion": "Complementos perfectos para completar tu hogar",
            "now": datetime.now,
            "error_message": "Error cargando decoración"
        })
        
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if conn and conn.is_connected():
            try:
                conn.close()
            except:
                pass

@router.get("/producto/{producto_id}", response_class=HTMLResponse)
def vista_producto_detalle(request: Request, producto_id: int):
    """
    Página de detalle de un producto específico.
    """
    conn = None
    cursor = None
    
    try:
        logger.info(f"🔍 Consultando producto ID: {producto_id}")
        
        conn = obtener_conexion_segura()
        cursor = conn.cursor(dictionary=True, buffered=True)

        # Obtener producto específico con todos los detalles
        cursor.execute("""
            SELECT 
                id,
                nombre,
                precio_venta,
                precio_descuento,
                img_1,
                img_2,
                img_3,
                img_4,
                img_5,
                descripcion_producto,
                tipo_producto,
                material,
                colores_disponibles,
                dimensiones,
                tiempo_entrega,
                COALESCE(visitas, 0) as visitas
            FROM productos
            WHERE id = %s 
              AND (tipo_producto_venta = 'local' OR tipo_producto_venta IS NULL)
              AND img_1 IS NOT NULL AND img_1 != ''
        """, (producto_id,))
        
        producto = cursor.fetchone()
        
        if not producto:
            logger.warning(f"⚠️ Producto no encontrado: {producto_id}")
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        
        # Procesar todas las imágenes del producto
        for i in range(1, 6):
            img_key = f'img_{i}'
            if producto.get(img_key):
                try:
                    original_path = producto[img_key]
                    producto[img_key] = procesar_url_imagen(original_path)
                    logger.debug(f"🖼️ {img_key}: {original_path} -> {producto[img_key]}")
                except Exception as e:
                    logger.warning(f"⚠️ Error procesando {img_key}: {e}")
                    producto[img_key] = "/static/images/no-image.jpg"

        # Incrementar visitas
        cursor.execute("""
            UPDATE productos 
            SET visitas = COALESCE(visitas, 0) + 1 
            WHERE id = %s
        """, (producto_id,))
        conn.commit()

        # Obtener productos relacionados del mismo tipo
        cursor.execute("""
            SELECT 
                id,
                nombre,
                precio_venta,
                img_1 AS imagen,
                precio_descuento
            FROM productos
            WHERE tipo_producto = %s 
              AND id != %s
              AND (tipo_producto_venta = 'local' OR tipo_producto_venta IS NULL)
              AND img_1 IS NOT NULL AND img_1 != ''
            ORDER BY visitas DESC
            LIMIT 4
        """, (producto['tipo_producto'], producto_id))
        
        productos_relacionados = cursor.fetchall()
        
        # Procesar imágenes de productos relacionados
        for producto_rel in productos_relacionados:
            try:
                if producto_rel.get('imagen'):
                    producto_rel['imagen'] = procesar_url_imagen(producto_rel['imagen'])
            except Exception as e:
                logger.warning(f"⚠️ Error procesando imagen relacionada: {e}")
                producto_rel['imagen'] = "/static/images/no-image.jpg"

        return request.app.state.templates.TemplateResponse("producto_detalle.html", {
            "request": request,
            "producto": producto,
            "productos_relacionados": productos_relacionados,
            "now": datetime.now
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error en vista_producto_detalle: {e}")
        raise HTTPException(status_code=500, detail="Error cargando detalle del producto")
        
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if conn and conn.is_connected():
            try:
                conn.close()
            except:
                pass

@router.get("/buscar", response_class=HTMLResponse)
def buscar_productos(request: Request, q: Optional[str] = Query(None)):
    """
    Búsqueda de productos.
    """
    conn = None
    cursor = None
    productos = []
    
    try:
        if q and len(q.strip()) >= 2:
            conn = obtener_conexion_segura()
            cursor = conn.cursor(dictionary=True, buffered=True)

            # Búsqueda mejorada en múltiples campos - no externos
            search_term = f"%{q.strip()}%"
            cursor.execute("""
                SELECT 
                    id,
                    nombre,
                    precio_venta,
                    img_1 AS imagen,
                    descripcion_producto,
                    tipo_producto,
                    material,
                    precio_descuento
                FROM productos
                WHERE (tipo_producto_venta != 'externo' OR tipo_producto_venta IS NULL)
                AND (nombre LIKE %s 
                       OR descripcion_producto LIKE %s 
                       OR tipo_producto LIKE %s
                       OR material LIKE %s)
                ORDER BY 
                    CASE 
                        WHEN nombre LIKE %s THEN 1
                        WHEN tipo_producto LIKE %s THEN 2
                        WHEN descripcion_producto LIKE %s THEN 3
                        ELSE 4
                    END,
                    COALESCE(visitas, 0) DESC,
                    precio_venta ASC
                LIMIT 50
            """, (search_term, search_term, search_term, search_term, 
                  search_term, search_term, search_term))
            
            productos = cursor.fetchall()
            
            # Procesar URLs de imágenes
            for producto in productos:
                try:
                    if producto.get('imagen'):
                        producto['imagen'] = procesar_url_imagen(producto['imagen'])
                except Exception as e:
                    logger.warning(f"⚠️ Error procesando imagen: {e}")
                    producto['imagen'] = "/static/images/no-image.jpg"

        return request.app.state.templates.TemplateResponse("busqueda.html", {
            "request": request,
            "productos": productos,
            "query": q,
            "total_resultados": len(productos),
            "now": datetime.now
        })
        
    except Exception as e:
        logger.error(f"❌ Error en buscar_productos: {e}")
        return request.app.state.templates.TemplateResponse("busqueda.html", {
            "request": request,
            "productos": [],
            "query": q,
            "total_resultados": 0,
            "now": datetime.now,
            "error_message": "Error en la búsqueda"
        })
        
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if conn and conn.is_connected():
            try:
                conn.close()
            except:
                pass

@router.get("/contacto", response_class=HTMLResponse)
def vista_contacto(request: Request):
    """
    Página de contacto.
    """
    try:
        return request.app.state.templates.TemplateResponse("contacto.html", {
            "request": request,
            "now": datetime.now
        })
    except Exception as e:
        logger.error(f"❌ Error en vista_contacto: {e}")
        raise HTTPException(status_code=500, detail="Error cargando página de contacto")

# Endpoint para obtener productos por tipo
@router.get("/api/productos/tipo/{tipo}")
async def productos_por_tipo(tipo: str):
    """
    API para obtener productos filtrados por tipo.
    """
    conn = None
    cursor = None
    
    try:
        conn = obtener_conexion_segura()
        cursor = conn.cursor(dictionary=True, buffered=True)

        cursor.execute("""
            SELECT 
                id,
                nombre,
                precio_venta,
                img_1 AS imagen,
                tipo_producto,
                precio_descuento
            FROM productos
            WHERE tipo_producto = %s 
            AND (tipo_producto_venta != 'externo' OR tipo_producto_venta IS NULL)
            ORDER BY COALESCE(visitas, 0) DESC
            LIMIT 20
        """, (tipo,))
        
        productos = cursor.fetchall()
        
        # Procesar URLs de imágenes
        for producto in productos:
            try:
                if producto.get('imagen'):
                    producto['imagen'] = procesar_url_imagen(producto['imagen'])
            except Exception as e:
                logger.warning(f"⚠️ Error procesando imagen API: {e}")
                producto['imagen'] = "/static/images/no-image.jpg"

        return {"productos": productos}
        
    except Exception as e:
        logger.error(f"❌ Error en productos_por_tipo: {e}")
        return {"productos": [], "error": str(e)}
        
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if conn and conn.is_connected():
            try:
                conn.close()
            except:
                pass

@router.get("/api/productos/stats")
async def estadisticas_productos():
    """
    Endpoint para obtener estadísticas de productos.
    """
    conn = None
    cursor = None
    
    try:
        conn = obtener_conexion_segura()
        cursor = conn.cursor(dictionary=True, buffered=True)

        cursor.execute("""
            SELECT 
                COUNT(*) as total_productos,
                COUNT(CASE WHEN img_1 IS NOT NULL THEN 1 END) as productos_con_imagen,
                COUNT(DISTINCT tipo_producto) as tipos_productos,
                AVG(precio_venta) as precio_promedio,
                MIN(precio_venta) as precio_minimo,
                MAX(precio_venta) as precio_maximo,
                SUM(COALESCE(visitas, 0)) as total_visitas
            FROM productos
            WHERE (tipo_producto_venta != 'externo' OR tipo_producto_venta IS NULL)
        """)
        
        stats = cursor.fetchone()
        
        # Estadísticas por tipo de producto - no externos
        cursor.execute("""
            SELECT 
                tipo_producto,
                COUNT(*) as cantidad,
                AVG(precio_venta) as precio_promedio
            FROM productos
            WHERE (tipo_producto_venta != 'externo' OR tipo_producto_venta IS NULL)
            AND tipo_producto IS NOT NULL
            GROUP BY tipo_producto
            ORDER BY cantidad DESC
        """)
        
        stats_por_tipo = cursor.fetchall()

        return {
            "estadisticas_generales": stats,
            "estadisticas_por_tipo": stats_por_tipo
        }
        
    except Exception as e:
        logger.error(f"❌ Error en estadisticas_productos: {e}")
        return {
            "estadisticas_generales": {},
            "estadisticas_por_tipo": [],
            "error": str(e)
        }
        
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if conn and conn.is_connected():
            try:
                conn.close()
            except:
                pass

# Funciones de utilidad para imágenes
def test_image_urls():
    """
    Función para testear diferentes rutas de imagen
    """
    test_paths = [
        "/images/productos/1_a1b6b386.jpg",
        "/images/productos/2_729557df.jpg", 
        "images/productos/3_388caa02.jpg",
        "productos/4_e37099c7.jpg",
        "1_a1b6b386.jpg",
        None,
        "",
        "   ",
        "http://example.com/image.jpg"
    ]
    
    print("🧪 TESTING IMAGE URL PROCESSING:")
    print("=" * 50)
    
    for path in test_paths:
        result = procesar_url_imagen(path)
        print(f"'{path}' -> '{result}'")
    
    print("=" * 50)

def optimize_image(input_path: Path, output_path: Path, quality: int = 85, max_width: int = 1200) -> bool:
    """Optimizar imagen manteniendo calidad"""
    try:
        with Image.open(input_path) as img:
            # Convertir a RGB si es necesario
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # Redimensionar si es muy grande
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
            
            # Guardar optimizada
            img.save(output_path, 'JPEG', quality=quality, optimize=True)
            return True
            
    except Exception as e:
        logger.error(f"❌ Error optimizando imagen: {e}")
        return False

def create_thumbnail(image_path: Path, thumb_path: Path, size: tuple = (300, 300)) -> bool:
    """Crear thumbnail de imagen"""
    try:
        with Image.open(image_path) as img:
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            img.thumbnail(size, Image.Resampling.LANCZOS)
            img.save(thumb_path, 'JPEG', quality=80, optimize=True)
            return True
            
    except Exception as e:
        logger.error(f"❌ Error creando thumbnail: {e}")
        return False

# Rutas adicionales del ecommerce
@router.get("/politicas", response_class=HTMLResponse)
def vista_politicas_legales(request: Request):
    """
    Página de Términos, Privacidad y Cookies.
    """
    try:
        return request.app.state.templates.TemplateResponse("politicas.html", {
            "request": request,
            "now": datetime.now
        })
    except Exception as e:
        logger.error(f"❌ Error en vista_politicas_legales: {e}")
        raise HTTPException(status_code=500, detail="Error cargando políticas")

@router.get("/carrito", response_class=HTMLResponse)
def vista_carrito(request: Request):
    """
    Página del carrito de compras.
    """
    try:
        return request.app.state.templates.TemplateResponse("carrito.html", {
            "request": request,
            "now": datetime.now
        })
    except Exception as e:
        logger.error(f"❌ Error en vista_carrito: {e}")
        raise HTTPException(status_code=500, detail="Error cargando carrito")

@router.get("/checkout", response_class=HTMLResponse)
def vista_checkout(request: Request):
    """
    Página de checkout para finalizar compra.
    """
    try:
        return request.app.state.templates.TemplateResponse("checkout.html", {
            "request": request,
            "now": datetime.now
        })
    except Exception as e:
        logger.error(f"❌ Error en vista_checkout: {e}")
        raise HTTPException(status_code=500, detail="Error cargando checkout")

@router.get("/compra-exitosa", response_class=HTMLResponse)
def vista_compra_exitosa(request: Request):
    """
    Página de confirmación de compra exitosa.
    """
    try:
        return request.app.state.templates.TemplateResponse("compra_exitosa.html", {
            "request": request,
            "now": datetime.now
        })
    except Exception as e:
        logger.error(f"❌ Error en vista_compra_exitosa: {e}")
        raise HTTPException(status_code=500, detail="Error cargando página de éxito")

@router.post("/procesar-venta")
async def procesar_venta_checkout(venta_data: dict):
    """
    Procesar una venta desde el checkout.
    """
    conn = None
    cursor = None
    
    try:
        logger.info(f"🛒 Procesando venta: {venta_data.get('numero_orden', 'N/A')}")
        
        conn = obtener_conexion_segura()
        cursor = conn.cursor(buffered=True)
        
        # Insertar la venta
        cursor.execute("""
            INSERT INTO ventas_retail (
                cliente_id, numero_orden, cliente_final, rut_documento, email, telefono,
                fecha_compra, fecha_entrega, producto, precio, precio_cliente, 
                costo_despacho, comuna, direccion, region, sku, estado, unidades,
                created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                NOW(), NOW()
            )
        """, (
            venta_data.get('cliente_id', 1),  # Cliente por defecto
            venta_data.get('numero_orden'),
            venta_data.get('cliente_final'),
            venta_data.get('rut_documento'),
            venta_data.get('email'),
            venta_data.get('telefono'),
            venta_data.get('fecha_compra'),
            venta_data.get('fecha_entrega'),
            venta_data.get('producto'),
            venta_data.get('precio'),
            venta_data.get('precio_cliente'),
            venta_data.get('costo_despacho', 0),
            venta_data.get('comuna'),
            venta_data.get('direccion'),
            venta_data.get('region'),
            venta_data.get('sku', ''),
            venta_data.get('estado', 'nueva'),
            venta_data.get('unidades', 1)
        ))
        
        conn.commit()
        venta_id = cursor.lastrowid
        
        logger.info(f"✅ Venta procesada exitosamente. ID: {venta_id}")
        
        return {"success": True, "message": "Venta procesada correctamente", "venta_id": venta_id}
        
    except Exception as e:
        logger.error(f"❌ Error procesando venta: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
        
        return {"success": False, "error": str(e)}
        
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if conn and conn.is_connected():
            try:
                conn.close()
            except:
                pass