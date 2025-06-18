from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.db import conectar_mysql # Usa tu conexión actual a la base de datos
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
import os
import uuid
import shutil
from PIL import Image
from pathlib import Path

router = APIRouter()

def procesar_url_imagen(img_path):
    """
    Convierte rutas de imagen del otro proyecto a URLs accesibles
    """
    if not img_path:
        return "/static/images/no-image.jpg"
    
    # Si ya es una URL completa
    if img_path.startswith('http'):
        return img_path
    
    # Limpiar la ruta
    clean_path = img_path
    
    # Remover prefijos comunes que pueden estar en la BD
    prefixes = ['/static/images/', 'static/images/', '/images/', 'images/', 'productos/']
    for prefix in prefixes:
        if clean_path.startswith(prefix):
            clean_path = clean_path[len(prefix):]
            break
    
    # Retornar URL usando el mount /images que apunta al otro proyecto
    return f"/images/{clean_path}"


UPLOAD_DIR = Path("/var/www/v4_python_jerk/static/images/productos")
THUMBNAILS_DIR = Path("/var/www/v4_python_jerk/static/images/productos/thumbnails")
TEMP_DIR = Path("/var/www/v4_python_jerk/uploads/temp")
BASE_URL = "http://147.79.74.244:8080/images/productos"

def obtener_conexion_segura():
    """
    Función helper para obtener conexión con manejo de errores.
    """
    try:
        conn = obtener_conexion_segura()
        if conn is None:
            raise Exception("No se pudo conectar a la base de datos")
        return conn
    except Exception as e:
        print(f"Error de conexión: {e}")
        raise HTTPException(status_code=500, detail="Error de conexión a la base de datos")

@router.get("/", response_class=HTMLResponse)
def root(request: Request):
    return request.app.state.templates.TemplateResponse("inicio.html", {
        "request": request
    })
    
@router.get("/productos", response_class=HTMLResponse)
def vista_productos(request: Request, tipo: Optional[str] = Query(None)):
    """
    Página principal de productos con manejo de errores de conexión.
    """
    try:
        # Usar la función segura de conexión
        conn = obtener_conexion_segura()
        cursor = conn.cursor(dictionary=True)

        # Base query con condiciones
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
                visitas
            FROM productos
            WHERE tipo_producto_venta = 'local'
              AND img_1 IS NOT NULL AND img_1 != ''
        """

        # Agregar filtro por tipo si corresponde
        if tipo:
            base_query += f" AND tipo_producto LIKE '%{tipo}%'"

        base_query += " ORDER BY COALESCE(visitas, 0) DESC, precio_venta ASC"

        cursor.execute(base_query)
        productos = cursor.fetchall()

        # Procesar URLs de imágenes con manejo de errores
        for producto in productos:
            try:
                if producto.get('imagen'):
                    producto['imagen'] = procesar_url_imagen(producto['imagen'])
            except Exception as e:
                print(f"Error procesando imagen para producto {producto.get('id')}: {e}")
                producto['imagen'] = "/static/images/no-image.jpg"

        cursor.close()
        conn.close()

        # Título dinámico
        titulo_pagina = "Todos los Productos"
        descripcion = "Descubre nuestra colección completa de muebles premium"

        if tipo:
            if tipo.lower() == "camas":
                titulo_pagina = "Camas"
                descripcion = "Camas cómodas para el descanso perfecto"
            elif tipo.lower() == "seccionales":
                titulo_pagina = "Sofás Seccionales"
                descripcion = "Sofás seccionales modulares para espacios amplios"
            elif tipo.lower() == "sofas":
                titulo_pagina = "Sofás"
                descripcion = "Sofás cómodos y elegantes para tu hogar"

        return request.app.state.templates.TemplateResponse("productos.html", {
            "request": request,
            "productos": productos,
            "titulo_pagina": titulo_pagina,
            "descripcion": descripcion,
            "filtro_activo": tipo,
            "now": datetime.now
        })

    except HTTPException:
        # Re-lanzar HTTPException (ya manejada por obtener_conexion_segura)
        raise
    except Exception as e:
        print(f"Error inesperado en vista_productos: {e}")
        import traceback
        traceback.print_exc()
        
        # Retornar página de error amigable
        return request.app.state.templates.TemplateResponse("inicio.html", {
            "request": request,
            "error_message": f"Error cargando productos: {str(e)}",
            "now": datetime.now
        })



@router.get("/inicio", response_class=HTMLResponse)
def vista_inicio(request: Request):
    """
    Página de inicio con hero y productos destacados.
    """
    return request.app.state.templates.TemplateResponse("inicio.html", {
        "request": request,
        "now": datetime.now
    })


@router.get("/nosotros", response_class=HTMLResponse)
def vista_nosotros(request: Request):
    """
    Página Nosotros - Historia, visión, misión y equipo de Jerk Home.
    """
    return request.app.state.templates.TemplateResponse("nosotros.html", {
        "request": request,
        "now": datetime.now
    })


@router.get("/ecomerce", response_class=HTMLResponse)
def vista_publica_ecomerce(request: Request):
    """
    Página pública del ecommerce que muestra el catálogo de productos.
    """
    conn = obtener_conexion_segura()
    cursor = conn.cursor(dictionary=True)

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
        if producto.get('imagen'):
            producto['imagen'] = procesar_url_imagen(producto['imagen'])

    cursor.close()
    conn.close()

    return request.app.state.templates.TemplateResponse("index.html", {
        "request": request,
        "productos": productos,
        "now": datetime.now  # Para usar el año en el footer
    })


@router.get("/sofas", response_class=HTMLResponse)
def vista_sofas(request: Request, categoria: Optional[str] = Query(None)):
    """
    Página específica de sofás.
    """
    conn = obtener_conexion_segura()
    cursor = conn.cursor(dictionary=True)

    # Filtrar por tipo de producto y nombre - todos excepto externos
    where_clause = """WHERE (tipo_producto_venta != 'externo' OR tipo_producto_venta IS NULL)
                      AND (tipo_producto IN ('seccionales', 'sofas') 
                            OR nombre LIKE '%sofa%' 
                            OR nombre LIKE '%sillon%'
                            OR descripcion_producto LIKE '%sofa%')"""
    
    if categoria:
        where_clause += f" AND tipo_producto LIKE '%{categoria}%'"

    cursor.execute(f"""
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
        AND (tipo_producto_venta != 'externo' OR tipo_producto_venta IS NULL)
        AND img_1 IS NOT NULL AND precio_venta > 0
        ORDER BY precio_venta ASC
    """)
    productos = cursor.fetchall()

    cursor.close()
    conn.close()

    return request.app.state.templates.TemplateResponse("categoria.html", {
        "request": request,
        "productos": productos,
        "categoria_titulo": "Sofás",
        "categoria_descripcion": "Descubre nuestra colección de sofás cómodos y elegantes",
        "now": datetime.now
    })


@router.get("/seccionales", response_class=HTMLResponse)
def vista_seccionales(request: Request):
    """
    Página específica de sofás seccionales.
    """
    conn = obtener_conexion_segura()
    cursor = conn.cursor(dictionary=True)

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

    cursor.close()
    conn.close()

    return request.app.state.templates.TemplateResponse("categoria.html", {
        "request": request,
        "productos": productos,
        "categoria_titulo": "Sofás Seccionales",
        "categoria_descripcion": "Sofás seccionales modulares para espacios amplios y versátiles",
        "now": datetime.now
    })


@router.get("/decoracion", response_class=HTMLResponse)
def vista_decoracion(request: Request):
    """
    Página específica de decoración.
    """
    conn = obtener_conexion_segura()
    cursor = conn.cursor(dictionary=True)

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

    cursor.close()
    conn.close()

    return request.app.state.templates.TemplateResponse("categoria.html", {
        "request": request,
        "productos": productos,
        "categoria_titulo": "Decoración",
        "categoria_descripcion": "Complementos perfectos para completar tu hogar",
        "now": datetime.now
    })


@router.get("/producto/{producto_id}", response_class=HTMLResponse)
def vista_producto_detalle(request: Request, producto_id: int):
    """
    Página de detalle de un producto específico (solo local con imagen).
    """
    conn = obtener_conexion_segura()
    cursor = conn.cursor(dictionary=True)

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
            visitas
        FROM productos
        WHERE id = %s 
          AND tipo_producto_venta = 'local'
          AND img_1 IS NOT NULL AND img_1 != ''
    """, (producto_id,))
    
    producto = cursor.fetchone()
    
    if producto:
        for i in range(1, 6):
            img_key = f'img_{i}'
            if producto.get(img_key):
                producto[img_key] = procesar_url_imagen(producto[img_key])

    if not producto:
        cursor.close()
        conn.close()
        return request.app.state.templates.TemplateResponse("index.html", {
            "request": request,
            "productos": [],
            "error_message": "Producto no encontrado",
            "now": datetime.now
        })

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
          AND tipo_producto_venta = 'local'
          AND img_1 IS NOT NULL AND img_1 != ''
        ORDER BY visitas DESC
        LIMIT 4
    """, (producto['tipo_producto'], producto_id))
    
    productos_relacionados = cursor.fetchall()
    
    for producto_rel in productos_relacionados:
        if producto_rel.get('imagen'):
            producto_rel['imagen'] = procesar_url_imagen(producto_rel['imagen'])

    cursor.close()
    conn.close()

    return request.app.state.templates.TemplateResponse("producto_detalle.html", {
        "request": request,
        "producto": producto,
        "productos_relacionados": productos_relacionados,
        "now": datetime.now
    })



@router.get("/buscar", response_class=HTMLResponse)
def buscar_productos(request: Request, q: Optional[str] = Query(None)):
    """
    Búsqueda de productos.
    """
    productos = []
    
    if q and len(q.strip()) >= 2:
        conn = obtener_conexion_segura()
        cursor = conn.cursor(dictionary=True)

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
                visitas DESC,
                precio_venta ASC
            LIMIT 50
        """, (search_term, search_term, search_term, search_term, 
              search_term, search_term, search_term))
        
        productos = cursor.fetchall()
        cursor.close()
        conn.close()

    return request.app.state.templates.TemplateResponse("busqueda.html", {
        "request": request,
        "productos": productos,
        "query": q,
        "total_resultados": len(productos),
        "now": datetime.now
    })


@router.get("/contacto", response_class=HTMLResponse)
def vista_contacto(request: Request):
    """
    Página de contacto.
    """
    return request.app.state.templates.TemplateResponse("contacto.html", {
        "request": request,
        "now": datetime.now
    })


# Endpoint para obtener productos por tipo
@router.get("/api/productos/tipo/{tipo}")
async def productos_por_tipo(tipo: str):
    """
    API para obtener productos filtrados por tipo.
    """
    conn = obtener_conexion_segura()
    cursor = conn.cursor(dictionary=True)

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
        ORDER BY visitas DESC
        LIMIT 20
    """, (tipo,))
    
    productos = cursor.fetchall()
    cursor.close()
    conn.close()

    return {"productos": productos}


@router.get("/api/productos/stats")
async def estadisticas_productos():
    """
    Endpoint para obtener estadísticas de productos.
    """
    conn = obtener_conexion_segura()
    cursor = conn.cursor(dictionary=True)

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
    
    cursor.close()
    conn.close()

    return {
        "estadisticas_generales": stats,
        "estadisticas_por_tipo": stats_por_tipo
    }

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
        print(f"Error optimizando imagen: {e}")
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
        print(f"Error creando thumbnail: {e}")
        return False

@router.get("/politicas", response_class=HTMLResponse)
def vista_politicas_legales(request: Request):
    """
    Página de Términos, Privacidad y Cookies.
    """
    return request.app.state.templates.TemplateResponse("politicas.html", {
        "request": request,
        "now": datetime.now
    })

@router.get("/carrito", response_class=HTMLResponse)
def vista_carrito(request: Request):
    """
    Página del carrito de compras.
    """
    return request.app.state.templates.TemplateResponse("carrito.html", {
        "request": request,
        "now": datetime.now
    })

@router.get("/checkout", response_class=HTMLResponse)
def vista_checkout(request: Request):
    """
    Página de checkout para finalizar compra.
    """
    return request.app.state.templates.TemplateResponse("checkout.html", {
        "request": request,
        "now": datetime.now
    })

@router.get("/compra-exitosa", response_class=HTMLResponse)
def vista_compra_exitosa(request: Request):
    """
    Página de confirmación de compra exitosa.
    """
    return request.app.state.templates.TemplateResponse("compra_exitosa.html", {
        "request": request,
        "now": datetime.now
    })

@router.post("/procesar-venta")
async def procesar_venta_checkout(venta_data: dict):
    """
    Procesar una venta desde el checkout.
    """
    try:
        conn = obtener_conexion_segura()
        cursor = conn.cursor()
        
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
            venta_data.get('cliente_id', 9),
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
        cursor.close()
        conn.close()
        
        return {"success": True, "message": "Venta procesada correctamente"}
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
            cursor.close()
            conn.close()
        
        return {"success": False, "error": str(e)}