from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from transbank.webpay.webpay_plus.transaction import Transaction
from transbank.common.options import WebpayOptions
from transbank.common.integration_type import IntegrationType
from app.db import conectar_mysql
import os
import logging
from datetime import datetime
import json

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# Configurar templates con función `now` global (igual que en main.py)
templates = Jinja2Templates(directory="templates")
templates.env.globals['now'] = datetime.now  # ✅ Agregar esta línea

# Configuración según el ambiente
ENVIRONMENT = os.getenv("ENVIRONMENT", "testing")

if ENVIRONMENT == "production":
    COMMERCE_CODE = os.getenv("WEBPAY_COMMERCE_CODE")
    API_KEY = os.getenv("WEBPAY_API_KEY") 
    INTEGRATION_TYPE = IntegrationType.LIVE
    
    if not COMMERCE_CODE or not API_KEY:
        raise ValueError("En producción debes configurar WEBPAY_COMMERCE_CODE y WEBPAY_API_KEY")
else:
    COMMERCE_CODE = "597055555532"
    API_KEY = "579B532A7440BB0C9079DED94D31EA1615BACEB56610332264630D42D0A36B1C"
    INTEGRATION_TYPE = IntegrationType.TEST

# Inicializar WebPay con las opciones
webpay_options = WebpayOptions(COMMERCE_CODE, API_KEY, INTEGRATION_TYPE)
transaction = Transaction(webpay_options)

@router.post("/webpay/iniciar")
async def iniciar_transaccion(
    request: Request,
    monto: int = Form(...),
    orden: str = Form(...)
):
    """Iniciar transacción WebPay Plus"""
    try:
        logger.info(f"Iniciando transacción - Orden: {orden}, Monto: {monto}")
        
        # Validaciones básicas
        if monto <= 0:
            raise HTTPException(status_code=400, detail="El monto debe ser mayor a 0")
        
        if not orden:
            raise HTTPException(status_code=400, detail="El número de orden es obligatorio")
        
        # Verificar que la orden existe en la base de datos
        conn = conectar_mysql()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM ventas_retail 
            WHERE numero_orden = %s
        """, (orden,))
        
        result = cursor.fetchone()
        
        if result['count'] == 0:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Orden no encontrada")
        
        cursor.close()
        conn.close()
        
        # Generar session_id único
        session_id = f"session_{orden}_{datetime.now().timestamp()}"
        
        # URL de retorno - ajustar según tu dominio
        base_url = str(request.base_url).rstrip('/')
        return_url = f"{base_url}/webpay/confirmar"
        
        logger.info(f"URL de retorno: {return_url}")
        
        # Crear transacción en WebPay
        response = transaction.create(
            buy_order=orden,
            session_id=session_id,
            amount=monto,
            return_url=return_url
        )
        
        logger.info(f"Respuesta WebPay: {response}")
        
        # Guardar información de la transacción en la base de datos
        conn = conectar_mysql()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO transacciones_webpay 
            (numero_orden, token, session_id, monto, estado, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
        """, (orden, response['token'], session_id, monto, 'iniciada'))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Redirigir a WebPay
        webpay_url = f"{response['url']}?token_ws={response['token']}"
        logger.info(f"Redirigiendo a WebPay: {webpay_url}")
        
        return RedirectResponse(url=webpay_url, status_code=303)
        
    except Exception as e:
        logger.error(f"Error iniciando transacción: {str(e)}")
        
        # Guardar el error en logs para debugging
        try:
            conn = conectar_mysql()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO logs_webpay 
                (numero_orden, tipo, mensaje, created_at)
                VALUES (%s, %s, %s, NOW())
            """, (orden, 'error_inicio', str(e)))
            conn.commit()
            cursor.close()
            conn.close()
        except:
            pass  # Si no puede logear, continuar
        
        # Redirigir a página de error con mensaje
        return templates.TemplateResponse("webpay/error.html", {
            "request": request,
            "error_message": f"Error al procesar el pago: {str(e)}",
            "numero_orden": orden,
            "datetime": datetime
        })

@router.post("/webpay/confirmar")
@router.get("/webpay/confirmar")
async def confirmar_pago(
    request: Request,
    token_ws: str = Form(None)
):
    """Confirmar transacción WebPay Plus"""
    try:
        # El token puede venir por POST o GET
        if not token_ws:
            token_ws = request.query_params.get('token_ws')
        
        if not token_ws:
            raise HTTPException(status_code=400, detail="Token de transacción no encontrado")
        
        logger.info(f"Confirmando transacción con token: {token_ws}")
        
        # Confirmar transacción con WebPay
        result = transaction.commit(token_ws)
        
        logger.info(f"Resultado WebPay: {json.dumps(result, indent=2)}")
        
        # Extraer información de la respuesta
        buy_order = result.get('buy_order')
        status = result.get('status')
        amount = result.get('amount')
        authorization_code = result.get('authorization_code')
        payment_type_code = result.get('payment_type_code')
        response_code = result.get('response_code')
        
        # Actualizar transacción en la base de datos
        conn = conectar_mysql()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE transacciones_webpay 
            SET 
                estado = %s,
                authorization_code = %s,
                payment_type_code = %s,
                response_code = %s,
                resultado_completo = %s,
                updated_at = NOW()
            WHERE token = %s
        """, (
            'completada' if status == 'AUTHORIZED' else 'fallida',
            authorization_code,
            payment_type_code,
            response_code,
            json.dumps(result),
            token_ws
        ))
        
        # Si el pago fue exitoso, actualizar las ventas
        if status == 'AUTHORIZED':
            cursor.execute("""
                UPDATE ventas_retail 
                SET 
                    estado = 'pagada',
                    metodo_pago = 'webpay',
                    fecha_pago = NOW(),
                    codigo_autorizacion = %s
                WHERE numero_orden = %s
            """, (authorization_code, buy_order))
            
            logger.info(f"Pago exitoso - Orden: {buy_order}, Autorización: {authorization_code}")
        else:
            logger.warning(f"Pago fallido - Orden: {buy_order}, Status: {status}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Determinar template según el resultado
        if status == 'AUTHORIZED':
            template_name = "webpay/pago_exitoso.html"
            context = {
                "request": request,
                "orden": buy_order,
                "monto": amount,
                "codigo_autorizacion": authorization_code,
                "tipo_pago": get_payment_type_description(payment_type_code),
                "fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "datetime": datetime
            }
        else:
            template_name = "webpay/pago_fallido.html"
            context = {
                "request": request,
                "orden": buy_order,
                "monto": amount,
                "codigo_respuesta": response_code,
                "mensaje_error": get_response_description(response_code),
                "datetime": datetime
            }
        
        return templates.TemplateResponse(template_name, context)
        
    except Exception as e:
        logger.error(f"Error confirmando transacción: {str(e)}")
        
        # Intentar extraer número de orden del token para logging
        numero_orden = "desconocido"
        try:
            conn = conectar_mysql()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT numero_orden 
                FROM transacciones_webpay 
                WHERE token = %s
            """, (token_ws,))
            result = cursor.fetchone()
            if result:
                numero_orden = result['numero_orden']
            cursor.close()
            conn.close()
        except:
            pass
        
        # Logear error
        try:
            conn = conectar_mysql()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO logs_webpay 
                (numero_orden, token, tipo, mensaje, created_at)
                VALUES (%s, %s, %s, %s, NOW())
            """, (numero_orden, token_ws, 'error_confirmacion', str(e)))
            conn.commit()
            cursor.close()
            conn.close()
        except:
            pass
        
        return templates.TemplateResponse("webpay/error.html", {
            "request": request,
            "error_message": f"Error procesando el resultado del pago: {str(e)}",
            "token": token_ws,
            "datetime": datetime
        })

@router.get("/webpay/estado/{numero_orden}")
async def consultar_estado_pago(numero_orden: str):
    """Consultar estado de un pago"""
    try:
        conn = conectar_mysql()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                t.*,
                v.cliente_final,
                v.email,
                v.producto
            FROM transacciones_webpay t
            LEFT JOIN ventas_retail v ON t.numero_orden = v.numero_orden
            WHERE t.numero_orden = %s
            ORDER BY t.created_at DESC
            LIMIT 1
        """, (numero_orden,))
        
        transaccion = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not transaccion:
            raise HTTPException(status_code=404, detail="Transacción no encontrada")
        
        return {
            "numero_orden": transaccion['numero_orden'],
            "estado": transaccion['estado'],
            "monto": transaccion['monto'],
            "fecha_creacion": transaccion['created_at'],
            "codigo_autorizacion": transaccion.get('authorization_code'),
            "cliente": transaccion.get('cliente_final')
        }
        
    except Exception as e:
        logger.error(f"Error consultando estado: {str(e)}")
        raise HTTPException(status_code=500, detail="Error consultando estado del pago")

def get_payment_type_description(payment_type_code):
    """Obtener descripción del tipo de pago"""
    types = {
        'VD': 'Tarjeta de Débito',
        'VN': 'Tarjeta de Crédito',
        'VC': 'Tarjeta de Crédito',
        'SI': 'Sin Interés',
        'S2': '2 cuotas sin interés',
        'S3': '3 cuotas sin interés',
        'N2': '2 cuotas con interés',
        'N3': '3 cuotas con interés',
        'N4': '4 cuotas con interés'
    }
    return types.get(payment_type_code, f'Tipo {payment_type_code}')

def get_response_description(response_code):
    """Obtener descripción del código de respuesta"""
    codes = {
        '0': 'Transacción aprobada',
        '-1': 'Rechazo - Transacción rechazada',
        '-2': 'Transacción debe reintentarse',
        '-3': 'Error en transacción',
        '-4': 'Rechazo - Transacción rechazada',
        '-5': 'Rechazo - Transacción rechazada',
        '-6': 'Rechazo - Transacción rechazada',
        '-7': 'Rechazo - Transacción rechazada',
        '-8': 'Rechazo - Transacción rechazada'
    }
    return codes.get(str(response_code), f'Código {response_code}')