from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routers import ecomerce
from datetime import datetime
from app.routers import ventas
from app.routers import webpay
import os
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="JerkHome Ecommerce",
    description="Plataforma de ecommerce para muebles premium",
    version="1.0.0"
)

# Archivos estáticos del proyecto
app.mount("/static", StaticFiles(directory="static"), name="static")

# Montar imágenes desde la ubicación correcta
# Esto permite acceder a /imagenes/productos/archivo.jpg 
# que físicamente está en /var/www/imagenes_jhk/productos/archivo.jpg
imagenes_path = "/var/www/imagenes_jhk"

if os.path.exists(imagenes_path):
    app.mount("/imagenes", StaticFiles(directory=imagenes_path), name="imagenes")
    logger.info(f"✅ Imágenes montadas desde {imagenes_path}")
    
    # Verificar subdirectorios
    productos_path = os.path.join(imagenes_path, "productos")
    show_path = os.path.join(imagenes_path, "show")
    
    if os.path.exists(productos_path):
        total_productos = len([f for f in os.listdir(productos_path) if os.path.isfile(os.path.join(productos_path, f))])
        logger.info(f"📸 Productos: {total_productos} imágenes disponibles")
    else:
        logger.warning(f"⚠️ Carpeta de productos no encontrada: {productos_path}")
    
    if os.path.exists(show_path):
        total_show = len([f for f in os.listdir(show_path) if os.path.isfile(os.path.join(show_path, f))])
        logger.info(f"🎭 Show: {total_show} imágenes disponibles")
    else:
        logger.warning(f"⚠️ Carpeta de show no encontrada: {show_path}")
        
else:
    logger.error(f"❌ Carpeta de imágenes no encontrada: {imagenes_path}")
    logger.error("🔧 Asegúrate de que la carpeta /var/www/imagenes_jhk existe y tiene permisos correctos")

# Configurar templates con función `now` global
templates = Jinja2Templates(directory="templates")
templates.env.globals['now'] = datetime.now
app.state.templates = templates

# Incluir routers
app.include_router(ecomerce.router)
app.include_router(ventas.router)
app.include_router(webpay.router)

@app.on_event("startup")
async def startup_event():
    """Verificaciones al iniciar la aplicación"""
    logger.info("🚀 Iniciando JerkHome Ecommerce...")
    
    # Verificar configuración de imágenes
    imagenes_config = {
        "base_path": imagenes_path,
        "productos_path": os.path.join(imagenes_path, "productos"),
        "show_path": os.path.join(imagenes_path, "show")
    }
    
    for name, path in imagenes_config.items():
        if os.path.exists(path):
            # Verificar permisos
            if os.access(path, os.R_OK):
                logger.info(f"✅ {name}: {path} - Accesible")
            else:
                logger.error(f"❌ {name}: {path} - Sin permisos de lectura")
        else:
            logger.error(f"❌ {name}: {path} - No existe")
    
    # Verificar configuración de templates
    templates_path = "templates"
    if os.path.exists(templates_path):
        logger.info(f"✅ Templates disponibles en: {templates_path}")
    else:
        logger.error(f"❌ Templates no encontrados en: {templates_path}")
    
    # Verificar archivos estáticos
    static_path = "static"
    if os.path.exists(static_path):
        logger.info(f"✅ Archivos estáticos disponibles en: {static_path}")
    else:
        logger.error(f"❌ Archivos estáticos no encontrados en: {static_path}")
    
    logger.info("✅ JerkHome Ecommerce iniciado correctamente")

@app.get("/health")
async def health_check():
    """Endpoint para verificar el estado de la aplicación"""
    imagenes_status = {
        "imagenes_path_exists": os.path.exists(imagenes_path),
        "productos_path_exists": os.path.exists(os.path.join(imagenes_path, "productos")),
        "show_path_exists": os.path.exists(os.path.join(imagenes_path, "show"))
    }
    
    if imagenes_status["productos_path_exists"]:
        productos_path = os.path.join(imagenes_path, "productos")
        imagenes_status["total_productos"] = len([f for f in os.listdir(productos_path) if os.path.isfile(os.path.join(productos_path, f))])
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "imagenes": imagenes_status
    }

@app.get("/debug/imagenes")
async def debug_imagenes():
    """Endpoint de debug para verificar configuración de imágenes"""
    try:
        debug_info = {
            "imagenes_path": imagenes_path,
            "imagenes_exists": os.path.exists(imagenes_path),
            "productos_path": os.path.join(imagenes_path, "productos"),
            "productos_exists": os.path.exists(os.path.join(imagenes_path, "productos")),
            "show_path": os.path.join(imagenes_path, "show"),
            "show_exists": os.path.exists(os.path.join(imagenes_path, "show"))
        }
        
        # Listar algunos archivos de ejemplo
        productos_path = os.path.join(imagenes_path, "productos")
        if os.path.exists(productos_path):
            archivos = [f for f in os.listdir(productos_path) if os.path.isfile(os.path.join(productos_path, f))]
            debug_info["total_archivos_productos"] = len(archivos)
            debug_info["ejemplos_productos"] = archivos[:5]  # Primeros 5 archivos
        
        return debug_info
        
    except Exception as e:
        return {"error": str(e)}

# Middleware para logging de requests de imágenes (opcional)
@app.middleware("http")
async def log_image_requests(request, call_next):
    """Middleware para loggear requests de imágenes para debug"""
    if request.url.path.startswith("/imagenes/"):
        logger.debug(f"🖼️ Request de imagen: {request.url.path}")
    
    response = await call_next(request)
    
    # Log de errores 404 en imágenes
    if request.url.path.startswith("/imagenes/") and response.status_code == 404:
        logger.warning(f"❌ Imagen no encontrada: {request.url.path}")
    
    return response