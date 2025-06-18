# 🏠 Jerk Home - Sistema de Ventas y E-commerce

Sistema integral de gestión de ventas y e-commerce para Jerk Home, especializado en muebles premium y sofás seccionales.

## 🚀 Características Principales

### 💼 Gestión de Ventas
- ✅ CRUD completo de ventas retail
- ✅ Gestión de clientes y productos
- ✅ Reportes y maestra de ventas
- ✅ Filtros avanzados y exportación a Excel/PDF
- ✅ Dashboard con estadísticas en tiempo real

### 🛒 E-commerce
- ✅ Catálogo de productos con filtros
- ✅ Carrito de compras persistente
- ✅ Checkout multi-paso
- ✅ Páginas de producto con galería de imágenes
- ✅ Búsqueda y categorización
- ✅ Diseño responsive y moderno

### 💳 Pagos con WebPay Plus
- ✅ Integración completa con Transbank WebPay Plus
- ✅ Manejo de estados de transacción
- ✅ Páginas de éxito, error y confirmación
- ✅ Logging y auditoría de pagos
- ✅ Configuración para testing y producción

### 🎨 Diseño y UX
- ✅ Interfaz moderna con Tailwind CSS
- ✅ Tema dark premium
- ✅ Animaciones y transiciones suaves
- ✅ Componentes glassmorphism
- ✅ Mobile-first responsive design

## 🛠️ Tecnologías Utilizadas

- **Backend**: FastAPI (Python)
- **Frontend**: Jinja2 Templates + Tailwind CSS
- **Base de Datos**: MySQL
- **Pagos**: Transbank WebPay Plus SDK
- **Estilos**: Tailwind CSS + Font Awesome
- **Deploy**: Compatible con Docker, VPS, PaaS

## 📋 Requisitos Previos

- Python 3.8+
- MySQL 5.7+
- pip (gestor de paquetes de Python)

## ⚡ Instalación Rápida

### 1. Clonar el repositorio
```bash
git clone https://github.com/felipeJS1295/api_ventas_jerk.git
cd api_ventas_jerk
```

### 2. Crear entorno virtual
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate     # Windows
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar base de datos
```sql
-- Crear base de datos
CREATE DATABASE integracion;

-- Ejecutar migraciones (archivo incluido)
mysql -u root -p integracion < database/migrations.sql
```

### 5. Configurar conexión a BD
Editar `app/db.py` con tus credenciales:
```python
connection = mysql.connector.connect(
    host="localhost",
    user="tu_usuario",
    password="tu_password",
    database="integracion"
)
```

### 6. Ejecutar la aplicación
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 7. Acceder a la aplicación
- **E-commerce**: http://localhost:8000
- **Gestión de ventas**: http://localhost:8000/ventas/vista

## 🧪 Testing WebPay Plus

La aplicación incluye configuración de testing para WebPay Plus:

### Tarjetas de Prueba
- **VISA**: 4051 8856 0000 0005
- **RUT**: 11.111.111-1
- **Clave**: 123

### URLs de Testing
- **Iniciar pago**: `/webpay/iniciar`
- **Confirmar pago**: `/webpay/confirmar`
- **Estado**: `/webpay/estado/{numero_orden}`

## 🔧 Configuración para Producción

### Variables de Entorno
Crear archivo `.env`:
```bash
ENVIRONMENT=production
WEBPAY_COMMERCE_CODE=tu_codigo_comercio
WEBPAY_API_KEY=tu_api_key
BASE_URL=https://tu-dominio.com
```

### HTTPS Obligatorio
WebPay Plus requiere HTTPS en producción:
- Configurar certificado SSL
- Actualizar return_url en la configuración

## 📁 Estructura del Proyecto

```
api_ventas_jerk/
├── app/
│   ├── routers/           # Rutas de la API
│   │   ├── ecomerce.py    # E-commerce público
│   │   ├── ventas.py      # Gestión de ventas
│   │   └── webpay.py      # Integración WebPay
│   ├── schemas/           # Modelos Pydantic
│   └── db.py             # Conexión base de datos
├── templates/             # Templates Jinja2
│   ├── webpay/           # Templates de pago
│   ├── ventas/           # Templates de gestión
│   └── *.html            # Templates del e-commerce
├── static/               # Archivos estáticos
│   ├── css/
│   ├── js/
│   └── images/
├── main.py              # Aplicación FastAPI principal
├── requirements.txt     # Dependencias Python
└── README.md           # Este archivo
```

## 🗃️ Base de Datos

### Tablas Principales
- `ventas_retail`: Gestión de ventas
- `productos`: Catálogo de productos
- `clientes`: Base de clientes
- `transacciones_webpay`: Seguimiento de pagos
- `logs_webpay`: Auditoría de transacciones

### Migraciones
Las migraciones están en `database/migrations.sql`

## 🔍 API Endpoints

### E-commerce
- `GET /` - Página principal
- `GET /productos` - Catálogo de productos
- `GET /producto/{id}` - Detalle de producto
- `GET /carrito` - Carrito de compras
- `GET /checkout` - Proceso de compra

### Gestión de Ventas
- `GET /ventas/vista` - Dashboard de ventas
- `GET /ventas/` - API de ventas
- `POST /ventas/` - Crear nueva venta
- `GET /ventas/maestra` - Reporte maestra

### WebPay Plus
- `POST /webpay/iniciar` - Iniciar transacción
- `POST /webpay/confirmar` - Confirmar pago
- `GET /webpay/estado/{orden}` - Consultar estado

## 🚀 Despliegue

### Opción 1: VPS con Nginx
```bash
# Instalar en servidor
sudo apt update
sudo apt install python3-pip nginx mysql-server
pip3 install -r requirements.txt

# Configurar Nginx como proxy reverso
# Configurar supervisor para auto-restart
```

### Opción 2: Docker
```dockerfile
# Dockerfile incluido en el proyecto
docker build -t jerk-home .
docker run -p 8000:8000 jerk-home
```

### Opción 3: PaaS (Railway, Heroku, etc.)
- Configurar variables de entorno
- Conectar base de datos externa
- Deploy automático desde GitHub

## 🐛 Debugging y Logs

### Logs de WebPay
```sql
SELECT * FROM logs_webpay ORDER BY created_at DESC LIMIT 10;
```

### Estado de Transacciones
```sql
SELECT numero_orden, estado, monto, authorization_code 
FROM transacciones_webpay 
ORDER BY created_at DESC;
```

### Testing Script
```bash
python test_webpay.py
```

## 🤝 Contribuir

1. Fork el proyecto
2. Crear feature branch (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Agregar nueva funcionalidad'`)
4. Push al branch (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## 📄 Licencia

Este proyecto es privado y pertenece a Jerk Home SpA.

## 👥 Contacto

- **Empresa**: Jerk Home SpA
- **Desarrollo**: Felipe Jiménez
- **Email**: contacto@jerkhome.cl
- **WhatsApp**: +56 9 3253 8029

---

## 🏆 Features Destacadas

### 💡 Innovaciones Técnicas
- Carrito persistente con localStorage
- Templates dinámicos con Jinja2
- Integración nativa con Transbank
- Diseño glassmorphism moderno
- Sistema de notificaciones en tiempo real

### 📈 Métricas y Analytics
- Tracking de visitas de productos
- Reportes de ventas por período
- Análisis de productos más vendidos
- Estados de transacciones en tiempo real

### 🔒 Seguridad
- Validación de RUT chileno
- Sanitización de inputs
- Logging de auditoría
- Manejo seguro de tokens WebPay

---

**¡Jerk Home - Redefiniendo espacios con tecnología premium!** 🏠✨