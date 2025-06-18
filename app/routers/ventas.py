from fastapi import APIRouter, HTTPException
from app.db import conectar_mysql
from app.schemas.venta_schema import VentaCreate, VentaOut
from pydantic import BaseModel
from typing import List
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import Request
import io
import pandas as pd
from datetime import datetime, timedelta
from fastapi.responses import StreamingResponse
from collections import defaultdict

router = APIRouter(prefix="/ventas", tags=["Ventas"])

@router.get("/", response_model=list[VentaOut])
def obtener_ventas():
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True, buffered=True)  # ✅ AGREGADO BUFFERED=TRUE
    
    try:
        cursor.execute("""
            SELECT 
                vr.id,
                vr.numero_orden,
                c.nombre AS cliente,
                vr.producto,
                vr.fecha_entrega,
                vr.estado,
                vr.sku
            FROM ventas_retail vr
            JOIN clientes c ON vr.cliente_id = c.id
            ORDER BY vr.fecha_entrega DESC
        """)
        resultados = cursor.fetchall()

        # Validar fechas nulas
        for r in resultados:
            fecha = r["fecha_entrega"]
            r["fecha_entrega"] = fecha.strftime("%Y-%m-%d") if fecha else ""

        return resultados
    
    except Exception as e:
        print(f"Error en obtener_ventas: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()


@router.post("/", response_model=VentaOut)
def crear_venta(venta: VentaCreate):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True, buffered=True)  # ✅ AGREGADO BUFFERED=TRUE
    
    try:
        # Log de datos recibidos para debugging
        print(f"📥 Datos de venta recibidos: {venta.dict()}")
        
        # Validaciones básicas
        if not venta.cliente_final or not venta.cliente_final.strip():
            raise HTTPException(status_code=400, detail="cliente_final es obligatorio")
        
        if not venta.producto or not venta.producto.strip():
            raise HTTPException(status_code=400, detail="producto es obligatorio")
        
        if venta.precio is None or venta.precio < 0:
            raise HTTPException(status_code=400, detail="precio debe ser mayor o igual a 0")
        
        # Definir columnas exactamente como están en la base de datos
        columnas = [
            "cliente_id", "numero_orden", "cliente_final", "rut_documento", "email",
            "telefono", "fecha_entrega", "fecha_cliente", "producto", "precio",
            "precio_cliente", "costo_despacho", "comuna", "direccion", "region",
            "sku", "estado", "documento", "razon_social", "rut", "giro",
            "direccion_factura", "courier", "unidades", "users_id", "fecha_compra"
        ]
        
        # Obtener valores, usando valores por defecto para campos opcionales
        valores = [
            venta.cliente_id or 1,
            venta.numero_orden or f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            venta.cliente_final.strip(),
            venta.rut_documento or "",
            venta.email or "",
            venta.telefono or "",
            venta.fecha_entrega or datetime.now().date(),
            venta.fecha_cliente or datetime.now().date(),
            venta.producto.strip(),
            venta.precio or 0,
            venta.precio_cliente or venta.precio or 0,
            venta.costo_despacho or 0,
            venta.comuna or "",
            venta.direccion or "",
            venta.region or "",
            venta.sku or "",
            venta.estado or "nueva",
            venta.documento or "boleta",
            venta.razon_social or venta.cliente_final or "",
            venta.rut or venta.rut_documento or "",
            venta.giro or "Particular",
            venta.direccion_factura or venta.direccion or "",
            venta.courier or "Retiro en tienda",
            venta.unidades or 1,
            venta.users_id or 1,
            venta.fecha_compra or datetime.now().date()
        ]

        placeholders = ", ".join(["%s"] * len(columnas))
        columnas_str = ", ".join(columnas)

        query = f"""
            INSERT INTO ventas_retail ({columnas_str})
            VALUES ({placeholders})
        """
        
        print(f"🔄 Ejecutando query: {query}")
        print(f"📊 Valores: {valores}")
        
        cursor.execute(query, valores)
        conn.commit()
        
        venta_id = cursor.lastrowid
        print(f"✅ Venta creada con ID: {venta_id}")
        
        # Retornar la venta creada
        venta_dict = venta.dict()
        venta_dict["id"] = venta_id
        venta_dict["fecha_entrega"] = str(valores[columnas.index("fecha_entrega")])
        venta_dict["fecha_compra"] = str(valores[columnas.index("fecha_compra")])

        return venta_dict
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error en crear_venta: {e}")
        
        # Proporcionar más detalles del error
        if "Duplicate entry" in str(e):
            raise HTTPException(status_code=400, detail="Ya existe una venta con ese número de orden")
        elif "cannot be null" in str(e):
            raise HTTPException(status_code=400, detail=f"Campo obligatorio faltante: {str(e)}")
        elif "Data too long" in str(e):
            raise HTTPException(status_code=400, detail=f"Datos demasiado largos: {str(e)}")
        else:
            raise HTTPException(status_code=400, detail=f"Error al crear venta: {str(e)}")
    finally:
        cursor.close()
        conn.close()


class EstadoUpdate(BaseModel):
    ids: List[int]
    estado: str

@router.put("/cambiar-estado")
def cambiar_estado_ventas(data: EstadoUpdate):
    conn = conectar_mysql()
    cursor = conn.cursor(buffered=True)  # ✅ AGREGADO BUFFERED=TRUE

    try:
        formato = ", ".join(["%s"] * len(data.ids))
        query = f"UPDATE ventas_retail SET estado = %s WHERE id IN ({formato})"
        cursor.execute(query, (data.estado, *data.ids))
        conn.commit()
        return {"mensaje": f"{cursor.rowcount} ventas actualizadas a '{data.estado}'."}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()


class EliminarVentas(BaseModel):
    ids: List[int]

@router.post("/eliminar-varias")
def eliminar_varias_ventas(data: EliminarVentas):
    conn = conectar_mysql()
    cursor = conn.cursor(buffered=True)  # ✅ AGREGADO BUFFERED=TRUE
    
    try:
        placeholders = ", ".join(["%s"] * len(data.ids))
        query = f"DELETE FROM ventas_retail WHERE id IN ({placeholders})"
        cursor.execute(query, data.ids)
        conn.commit()
        return {"mensaje": f"{cursor.rowcount} ventas eliminadas correctamente."}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

templates = Jinja2Templates(directory="templates")

@router.get("/vista", response_class=HTMLResponse)
def vista_ventas(
    request: Request,
    cliente: str = "",
    orden: str = "",
    desde: str = "",
    hasta: str = "",
    estado: str = "",
    ordenarPor: str = "fecha_entrega",
    direccion: str = "desc"
):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)

    filtros = []
    params = []

    if cliente:
        filtros.append("c.nombre LIKE %s")
        params.append(f"%{cliente}%")
    if orden:
        filtros.append("vr.numero_orden LIKE %s")
        params.append(f"%{orden}%")
    if desde:
        filtros.append("vr.fecha_entrega >= %s")
        params.append(desde)
    if hasta:
        filtros.append("vr.fecha_entrega <= %s")
        params.append(hasta)
    if estado:
        filtros.append("vr.estado = %s")
        params.append(estado)

    where_clause = "WHERE " + " AND ".join(filtros) if filtros else ""

    # Validar campos para evitar SQL injection
    columnas_validas = ["numero_orden", "cliente", "producto", "fecha_entrega", "estado"]
    direcciones_validas = ["asc", "desc"]

    if ordenarPor not in columnas_validas:
        ordenarPor = "fecha_entrega"
    if direccion not in direcciones_validas:
        direccion = "desc"

    # Traducir nombre de columna
    orden_columna = "c.nombre" if ordenarPor == "cliente" else f"vr.{ordenarPor}"

    cursor.execute(f"""
        SELECT 
            vr.id,
            vr.numero_orden,
            c.nombre AS cliente,
            vr.producto,
            vr.fecha_entrega,
            vr.estado,
            vr.sku
        FROM ventas_retail vr
        JOIN clientes c ON vr.cliente_id = c.id
        {where_clause}
        ORDER BY {orden_columna} {direccion}
        LIMIT 500
    """, params)

    ventas = cursor.fetchall()
    for v in ventas:
        fecha = v["fecha_entrega"]
        v["fecha_entrega"] = fecha.strftime("%d-%m-%Y") if fecha else ""

    conn.close()

    hx_request = request.headers.get("HX-Request")
    
    contexto = {
        "request": request,
        "ventas": ventas,
        "ordenar_por": ordenarPor,
        "direccion": direccion
    }

    if hx_request:
        return templates.TemplateResponse("partials/tabla_ventas.html", contexto)
    else:
        return templates.TemplateResponse("ventas.html", contexto)

@router.get("/tabla", response_class=HTMLResponse)
def tabla_ventas(request: Request,
                 cliente: str = "",
                 orden: str = "",
                 desde: str = "",
                 hasta: str = "",
                 estado: str = ""):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)

    filtros = []
    params = []

    if cliente:
        filtros.append("c.nombre LIKE %s")
        params.append(f"%{cliente}%")
    if orden:
        filtros.append("vr.numero_orden LIKE %s")
        params.append(f"%{orden}%")
    if desde:
        filtros.append("vr.fecha_entrega >= %s")
        params.append(desde)
    if hasta:
        filtros.append("vr.fecha_entrega <= %s")
        params.append(hasta)
    if estado:
        filtros.append("vr.estado = %s")
        params.append(estado)

    where_clause = "WHERE " + " AND ".join(filtros) if filtros else ""

    cursor.execute(f"""
        SELECT 
            vr.id,
            vr.numero_orden,
            c.nombre AS cliente,
            vr.producto,
            vr.fecha_entrega,
            vr.estado,
            vr.sku
        FROM ventas_retail vr
        JOIN clientes c ON vr.cliente_id = c.id
        {where_clause}
        ORDER BY vr.fecha_entrega DESC
        LIMIT 500
    """, params)

    ventas = cursor.fetchall()
    for v in ventas:
        fecha = v["fecha_entrega"]
        v["fecha_entrega"] = fecha.strftime("%d-%m-%Y") if fecha else ""

    conn.close()
    return templates.TemplateResponse("partials/tabla_ventas.html", {
        "request": request,
        "ventas": ventas
    })

@router.get("/maestra", response_class=HTMLResponse)
async def vista_maestra(request: Request):
    """Vista principal de la maestra de ventas"""
    return templates.TemplateResponse("ventas/maestra.html", {"request": request})

@router.get("/maestra/datos", response_class=HTMLResponse)
async def datos_maestra(
    request: Request,
    fecha_desde: str = "",
    fecha_hasta: str = "",
    cliente: str = "",
    producto: str = "",
    estado_producto: str = ""  # Filtrar por estado desde ventas_retail
):
    """Obtener datos de la maestra con filtros"""
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Si no hay fechas, usar últimos 7 días
        if not fecha_desde or not fecha_hasta:
            hoy = datetime.now()
            hace_7_dias = hoy - timedelta(days=7)
            fecha_desde = fecha_desde or hace_7_dias.strftime('%Y-%m-%d')
            fecha_hasta = fecha_hasta or hoy.strftime('%Y-%m-%d')
        
        # Construir filtros
        filtros = ["vr.fecha_entrega >= %s", "vr.fecha_entrega <= %s"]
        params = [fecha_desde, fecha_hasta]
        
        if cliente:
            filtros.append("c.id = %s")
            params.append(cliente)
        if producto:
            filtros.append("vr.producto LIKE %s")
            params.append(f"%{producto}%")
        
        # FILTRO POR ESTADO desde ventas_retail
        if estado_producto:
            filtros.append("vr.estado = %s")
            params.append(estado_producto)
            
        where_clause = "WHERE " + " AND ".join(filtros)
        
        # Consulta principal
        query = f"""
        SELECT 
            c.nombre as cliente,
            vr.producto,
            vr.estado as estado_producto,
            DATE(vr.fecha_entrega) as fecha,
            COUNT(*) as cantidad
        FROM ventas_retail vr
        JOIN clientes c ON vr.cliente_id = c.id
        {where_clause}
        GROUP BY c.nombre, vr.producto, vr.estado, DATE(vr.fecha_entrega)
        ORDER BY c.nombre, vr.producto, fecha
        """
        
        cursor.execute(query, params)
        datos = cursor.fetchall()
        
        # Procesar datos
        tabla_datos = procesar_datos_maestra(datos, estado_producto)
        
        return templates.TemplateResponse("partials/tabla_maestra.html", {
            "request": request,
            "tabla_datos": tabla_datos,
            "filtro_estado": estado_producto
        })
        
    except Exception as e:
        return f"<div class='p-4 text-red-600'>Error: {str(e)}</div>"
    finally:
        cursor.close()
        conn.close()

def procesar_datos_maestra(datos, estado_filtro=None):
    """Procesa los datos para crear la estructura de tabla dinámica"""
    
    # Organizar datos
    tabla = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    fechas = set()
    productos_estados = {}  # Para trackear el estado de cada producto
    
    for row in datos:
        cliente = row['cliente']
        producto = row['producto']
        fecha = row['fecha'].strftime('%d-%m-%Y')
        cantidad = row['cantidad']
        estado_producto = row.get('estado_producto', '')
        
        fechas.add(fecha)
        tabla[cliente][producto][fecha] += cantidad
        productos_estados[producto] = estado_producto
    
    # Ordenar fechas
    fechas_ordenadas = sorted(list(fechas), key=lambda x: datetime.strptime(x, '%d-%m-%Y'))
    
    # Calcular totales
    tabla_con_totales = {}
    totales_por_fecha = {fecha: 0 for fecha in fechas_ordenadas}
    gran_total = 0
    
    for cliente, productos in tabla.items():
        tabla_con_totales[cliente] = {
            'productos': {},
            'totales_por_fecha': {fecha: 0 for fecha in fechas_ordenadas},
            'total_cliente': 0
        }
        
        for producto, fechas_dict in productos.items():
            # Calcular total por producto
            total_producto = sum(fechas_dict.values())
            estado_producto = productos_estados.get(producto, '')
            
            tabla_con_totales[cliente]['productos'][producto] = {
                'fechas': dict(fechas_dict),
                'total': total_producto,
                'estado': estado_producto,
                'es_nuevo': estado_producto.lower() == 'nueva'  # Flag para productos nuevos
            }
            
            # Acumular totales por fecha para este cliente
            for fecha, cantidad in fechas_dict.items():
                tabla_con_totales[cliente]['totales_por_fecha'][fecha] += cantidad
                totales_por_fecha[fecha] += cantidad
                gran_total += cantidad
            
            tabla_con_totales[cliente]['total_cliente'] += total_producto
    
    return {
        'clientes': tabla_con_totales,
        'fechas': fechas_ordenadas,
        'totales_por_fecha': totales_por_fecha,
        'gran_total': gran_total,
        'estado_filtro': estado_filtro,
        'solo_productos_nuevos': estado_filtro == 'nueva'
    }

@router.get("/maestra/exportar/excel")
async def exportar_excel_maestra(
    fecha_desde: str = "",
    fecha_hasta: str = "",
    cliente: str = "",
    producto: str = "",
    estado_producto: str = ""
):
    """Exportar a Excel con filtro de estado desde ventas_retail"""
    
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Aplicar misma lógica de filtros que en datos_maestra
        if not fecha_desde or not fecha_hasta:
            hoy = datetime.now()
            hace_7_dias = hoy - timedelta(days=7)
            fecha_desde = fecha_desde or hace_7_dias.strftime('%Y-%m-%d')
            fecha_hasta = fecha_hasta or hoy.strftime('%Y-%m-%d')
        
        filtros = ["vr.fecha_entrega >= %s", "vr.fecha_entrega <= %s"]
        params = [fecha_desde, fecha_hasta]
        
        if cliente:
            filtros.append("c.id = %s")
            params.append(cliente)
        if producto:
            filtros.append("vr.producto LIKE %s")
            params.append(f"%{producto}%")
        if estado_producto:
            filtros.append("vr.estado = %s")
            params.append(estado_producto)
            
        where_clause = "WHERE " + " AND ".join(filtros)
        
        query = f"""
        SELECT 
            c.nombre as Cliente,
            vr.producto as Producto,
            vr.estado as 'Estado Producto',
            DATE(vr.fecha_entrega) as Fecha,
            COUNT(*) as Cantidad
        FROM ventas_retail vr
        JOIN clientes c ON vr.cliente_id = c.id
        {where_clause}
        GROUP BY c.nombre, vr.producto, vr.estado, DATE(vr.fecha_entrega)
        ORDER BY c.nombre, vr.producto, Fecha
        """
        
        cursor.execute(query, params)
        datos = cursor.fetchall()
        
        if not datos:
            raise HTTPException(status_code=404, detail="No se encontraron datos para exportar")
        
        # Crear DataFrame
        df = pd.DataFrame(datos)
        
        # Formatear la fecha
        df['Fecha'] = pd.to_datetime(df['Fecha']).dt.strftime('%d/%m/%Y')
        
        # Crear archivo Excel en memoria
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Hoja principal
            df.to_excel(writer, sheet_name='Maestra Ventas', index=False)
            
            # Agregar hoja de resumen si es filtro de productos nuevos
            if estado_producto == 'nueva':
                resumen_df = df.groupby(['Cliente', 'Producto']).agg({
                    'Cantidad': 'sum'
                }).reset_index()
                resumen_df.to_excel(writer, sheet_name='Resumen Productos Nuevos', index=False)
                
                # Hoja de estadísticas por cliente
                stats_cliente = df.groupby('Cliente').agg({
                    'Cantidad': 'sum',
                    'Producto': 'nunique'
                }).reset_index()
                stats_cliente.columns = ['Cliente', 'Total Ventas', 'Productos Diferentes']
                stats_cliente.to_excel(writer, sheet_name='Stats por Cliente', index=False)
        
        output.seek(0)
        
        # Nombre del archivo con indicador de filtro
        nombre_archivo = f"maestra_ventas"
        if estado_producto == 'nueva':
            nombre_archivo += "_productos_nuevos"
        nombre_archivo += f"_{fecha_desde}_{fecha_hasta}.xlsx"
        
        return StreamingResponse(
            io.BytesIO(output.read()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al exportar Excel: {str(e)}")
    finally:
        cursor.close()
        conn.close()

@router.get("/maestra/exportar/pdf") 
async def exportar_pdf_maestra(
    fecha_desde: str = "",
    fecha_hasta: str = "",
    cliente: str = "",
    producto: str = "",
    estado_producto: str = ""
):
    """Exportar a PDF con filtro de estado desde ventas_retail"""
    
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Aplicar misma lógica de filtros
        if not fecha_desde or not fecha_hasta:
            hoy = datetime.now()
            hace_7_dias = hoy - timedelta(days=7)
            fecha_desde = fecha_desde or hace_7_dias.strftime('%Y-%m-%d')
            fecha_hasta = fecha_hasta or hoy.strftime('%Y-%m-%d')
        
        filtros = ["vr.fecha_entrega >= %s", "vr.fecha_entrega <= %s"]
        params = [fecha_desde, fecha_hasta]
        
        if cliente:
            filtros.append("c.id = %s")
            params.append(cliente)
        if producto:
            filtros.append("vr.producto LIKE %s")
            params.append(f"%{producto}%")
        if estado_producto:
            filtros.append("vr.estado = %s")
            params.append(estado_producto)
            
        where_clause = "WHERE " + " AND ".join(filtros)
        
        query = f"""
        SELECT 
            c.nombre as cliente,
            vr.producto,
            vr.estado as estado_producto,
            DATE(vr.fecha_entrega) as fecha,
            COUNT(*) as cantidad
        FROM ventas_retail vr
        JOIN clientes c ON vr.cliente_id = c.id
        {where_clause}
        GROUP BY c.nombre, vr.producto, vr.estado, DATE(vr.fecha_entrega)
        ORDER BY c.nombre, vr.producto, fecha
        """
        
        cursor.execute(query, params)
        datos = cursor.fetchall()
        
        if not datos:
            raise HTTPException(status_code=404, detail="No se encontraron datos para exportar")
        
        # Crear HTML para el PDF
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Maestra de Ventas - Productos Nuevos</title>
            <style>
                body {{ font-family: Arial, sans-serif; font-size: 12px; margin: 20px; }}
                .header {{ text-align: center; margin-bottom: 20px; border-bottom: 2px solid #333; padding-bottom: 10px; }}
                .header h1 {{ margin: 0; color: #333; }}
                .header h2 {{ margin: 5px 0; color: #059669; }}
                .filters {{ margin-bottom: 15px; background: #f5f5f5; padding: 10px; border-radius: 5px; }}
                .stats {{ margin-bottom: 15px; background: #e3f2fd; padding: 10px; border-radius: 5px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; font-weight: bold; }}
                .nuevo {{ background-color: #e8f5e8; }}
                .total-row {{ background-color: #f0f0f0; font-weight: bold; }}
                .footer {{ margin-top: 20px; text-align: center; font-size: 10px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>MAESTRA DE VENTAS POR CLIENTE</h1>
                {'<h2>★ SOLO PRODUCTOS NUEVOS ★</h2>' if estado_producto == 'nueva' else '<h2>Todos los Estados</h2>'}
            </div>
            
            <div class="filters">
                <strong>📊 Filtros aplicados:</strong><br>
                📅 <strong>Período:</strong> {fecha_desde} al {fecha_hasta}<br>
                👤 <strong>Cliente:</strong> {cliente or 'Todos'}<br>
                📦 <strong>Producto:</strong> {producto or 'Todos'}<br>
                ⭐ <strong>Estado:</strong> {estado_producto.title() if estado_producto else 'Todos los estados'}
            </div>
            
            <div class="stats">
                <strong>📈 Resumen:</strong>
                Total de registros: {len(datos)} | 
                Clientes únicos: {len(set(row['cliente'] for row in datos))} | 
                Productos únicos: {len(set(row['producto'] for row in datos))} |
                Total ventas: {sum(row['cantidad'] for row in datos)}
            </div>
            
            <table>
                <thead>
                    <tr>
                        <th>Cliente</th>
                        <th>Producto</th>
                        <th>Estado</th>
                        <th>Fecha</th>
                        <th>Cantidad</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for row in datos:
            clase_fila = 'nuevo' if row['estado_producto'] == 'nueva' else ''
            icono_estado = '⭐' if row['estado_producto'] == 'nueva' else '📦'
            
            html_content += f"""
                    <tr class="{clase_fila}">
                        <td>{row['cliente']}</td>
                        <td>{icono_estado} {row['producto']}</td>
                        <td>{row['estado_producto'].title()}</td>
                        <td>{row['fecha'].strftime('%d/%m/%Y')}</td>
                        <td>{row['cantidad']}</td>
                    </tr>
            """
        
        html_content += f"""
                </tbody>
            </table>
            
            <div class="footer">
                <p>🏢 Sistema de Gestión de Ventas - JerkHome | 
                📅 Generado el {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} | 
                🔍 Filtro aplicado: {estado_producto.title() if estado_producto else 'Sin filtro de estado'}</p>
            </div>
        </body>
        </html>
        """
        
        # Retornar HTML como respuesta
        nombre_archivo = f"maestra_ventas"
        if estado_producto == 'nueva':
            nombre_archivo += "_productos_nuevos"
        nombre_archivo += f"_{fecha_desde}_{fecha_hasta}.html"
        
        return StreamingResponse(
            io.StringIO(html_content),
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al exportar PDF: {str(e)}")
    finally:
        cursor.close()
        conn.close()


@router.get("/productos/estados")
async def obtener_estados_productos():
    """Endpoint para obtener todos los estados de productos disponibles"""
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    try:
        query = "SELECT DISTINCT estado FROM ventas_retail WHERE estado IS NOT NULL ORDER BY estado"
        cursor.execute(query)
        estados = cursor.fetchall()
        
        return [{"value": row["estado"], "label": row["estado"].title()} for row in estados]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener estados: {str(e)}")
    finally:
        cursor.close()
        conn.close()

@router.get("/cargar/falabella", response_class=HTMLResponse)
async def cargar_ventas_falabella(request: Request):
    return templates.TemplateResponse("ventas/cargar/falabella.html", {"request": request})

@router.get("/cargar/cencosud", response_class=HTMLResponse)
async def cargar_ventas_cencosud(request: Request):
    return templates.TemplateResponse("ventas/cargar/cencosud.html", {"request": request})

@router.get("/cargar/walmart", response_class=HTMLResponse)
async def cargar_ventas_walmart(request: Request):
    return templates.TemplateResponse("ventas/cargar/walmart.html", {"request": request})

@router.get("/cargar/ripley", response_class=HTMLResponse)
async def cargar_ventas_ripley(request: Request):
    return templates.TemplateResponse("ventas/cargar/ripley.html", {"request": request})

@router.get("/cargar/hites", response_class=HTMLResponse)
async def cargar_ventas_hites(request: Request):
    return templates.TemplateResponse("ventas/cargar/hites.html", {"request": request})

@router.get("/cargar/manual", response_class=HTMLResponse)
async def cargar_ventas_manual(request: Request):
    return templates.TemplateResponse("ventas/cargar/manual.html", {"request": request})