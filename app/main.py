from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routers import ecomerce
from datetime import datetime
from app.routers import ventas
from app.routers import webpay

app = FastAPI()

# Archivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

app.mount("/images", StaticFiles(directory="/var/www/v4_python_jerk/static/images"), name="images")

# Configurar templates con función `now` global
templates = Jinja2Templates(directory="templates")
templates.env.globals['now'] = datetime.now  # 👈 ESTA LÍNEA ES CLAVE
app.state.templates = templates

# Incluir routers
app.include_router(ecomerce.router)
app.include_router(ventas.router)
app.include_router(webpay.router)