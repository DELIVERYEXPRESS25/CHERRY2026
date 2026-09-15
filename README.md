# Cherry Inventario

Sistema de Inventario y Facturación en Córdobas Nicaragüenses (C$)

## Requisitos

- Python 3.8+
- PostgreSQL
- pip

## Instalación

1. Clonar o descargar el proyecto

2. Crear entorno virtual:
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

4. Crear base de datos en PostgreSQL:
```sql
CREATE DATABASE cherry_inventory;
```

5. Configurar variables de entorno (opcional):
```bash
export DATABASE_URL=postgresql://usuario:password@localhost:5432/cherry_inventory
export SECRET_KEY=tu-clave-secreta
```

6. Ejecutar la aplicación:
```bash
python app.py
```

7. Abrir en el navegador:
```
http://localhost:5000
```

## Usuario por Defecto

- **Usuario:** admin
- **Contraseña:** admin123

## Funcionalidades

### Gestión de Productos
- Agregar, editar y eliminar productos
- Control de stock con alertas de stock bajo
- Búsqueda por nombre o código
- Categorización de productos

### Gestión de Clientes
- Registro de clientes con RUC
- Información de contacto
- Búsqueda de clientes

### Sistema de Facturación
- Creación de facturas con númerosecuencial
- Cálculo automático de ISV (15%)
- Métodos de pago (Efectivo, Tarjeta, Transferencia, Crédito)
- Impresión de facturas
- Cancelación de facturas con restauración de stock

### Reportes
- Ventas diarias, mensuales y anuales
- Productos más vendidos
- Resumen de facturación
- Gráficos de ventas

### Panel de Control
- Estadísticas generales
- Alertas de stock bajo
- Facturas recientes
- Gráfico de ventas últimos 30 días

## Moneda

El sistema utiliza el Córdoba Nicaragüense (C$) como moneda local.

## Estructura del Proyecto

```
cherry-inventario/
├── app.py                 # Aplicación principal
├── requirements.txt       # Dependencias
├── static/
│   ├── css/
│   │   └── style.css     # Estilos CSS
│   └── js/
│       └── main.js       # JavaScript
└── templates/
    ├── base.html         # Plantilla base
    ├── login.html        # Inicio de sesión
    ├── dashboard.html    # Panel de control
    ├── products.html     # Lista de productos
    ├── product_form.html # Formulario de productos
    ├── customers.html    # Lista de clientes
    ├── customer_form.html# Formulario de clientes
    ├── invoices.html     # Lista de facturas
    ├── invoice_form.html # Nueva factura
    ├── invoice_view.html # Ver factura
    └── reports.html      # Reportes
```

## Notas

- El sistema incluye ISV del 15% automáticamente
- Las facturas se numeran secuencialmente (INV-000001)
- El stock se actualiza automáticamente al crear/cancelar facturas
- Se recomienda cambiar la contraseña del admin después del primer inicio
