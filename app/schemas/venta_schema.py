from pydantic import BaseModel
from typing import Optional
from datetime import date

class VentaBase(BaseModel):
    cliente_id: int
    numero_orden: Optional[str] = None
    cliente_final: Optional[str] = None
    rut_documento: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    fecha_entrega: Optional[date] = None
    fecha_cliente: Optional[date] = None
    fecha_compra: Optional[date] = None  # ✅ este campo era necesario
    producto: Optional[str] = None
    precio: Optional[float] = None
    precio_cliente: Optional[float] = None
    costo_despacho: Optional[float] = None
    comuna: Optional[str] = None
    direccion: Optional[str] = None
    region: Optional[str] = None
    sku: Optional[str] = None
    estado: Optional[str] = None
    documento: Optional[str] = None
    razon_social: Optional[str] = None
    rut: Optional[str] = None
    giro: Optional[str] = None
    direccion_factura: Optional[str] = None
    courier: Optional[str] = None
    unidades: Optional[int] = None
    users_id: Optional[int] = None

class VentaCreate(VentaBase):
    pass

class VentaOut(BaseModel):
    id: int
    numero_orden: str
    fecha_entrega: str
    producto: str
    estado: str
    sku: Optional[str] = None
