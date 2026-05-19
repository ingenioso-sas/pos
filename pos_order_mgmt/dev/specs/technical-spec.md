# Especificación Técnica - pos_order_mgmt

## 1. Arquitectura del Sistema
El módulo sigue la arquitectura estándar de Odoo 13 (MVC). Extiende modelos existentes en el backend (Python) y widgets en el frontend (JS) utilizando herencia.

## 2. Modelo de Datos (PostgreSQL)

### 2.1. `pos.config` (Extensión)
| Campo | Tipo | Descripción | Confianza |
|-------|------|-------------|-----------|
| `iface_order_mgmt` | Boolean | Habilita el botón de gestión en el POS | ✅✅✅ |
| `iface_reprint_done_order` | Boolean | Permite reimprimir pedidos finalizados | ✅✅✅ |
| `iface_return_done_order` | Boolean | Permite devolver pedidos finalizados | ✅✅✅ |
| `iface_copy_done_order` | Boolean | Permite duplicar pedidos finalizados | ✅✅✅ |
| `iface_load_done_order_max_qty` | Integer | Cantidad máx. a cargar/tamaño de página | ✅✅✅ |

### 2.2. `pos.order` (Extensión)
| Campo | Tipo | Descripción | Confianza |
|-------|------|-------------|-----------|
| `returned_order_id` | Many2one | Vínculo al pedido original en devoluciones | ✅✅ |
| `returned_order_reference` | Char | Referencia del pedido original (relacionado) | ✅✅ |
| `refund_order_ids` | One2many | Pedidos de reembolso generados desde este | 🔸 |
| `refund_order_qty` | Integer | Cantidad de reembolsos (computado) | 🔸 |

## 3. APIs y Endpoints (Odoo RPC)

### 3.1. `search_done_orders_for_pos(query, pos_session_id, page)`
- **Modelo:** `pos.order`
- **Descripción:** Busca pedidos que cumplan los criterios de filtro y paginación.
- **Filtros aplicados:**
    - `state`: 'paid', 'done', 'invoiced'.
    - Si no hay query: filtra por `config_id` de la sesión actual.
    - Si hay query: busca en `name`, `pos_reference`, `partner_id.display_name`, `lines.product_id.name`.
- **Retorno:** Objeto con `items` y metadatos de paginación.

### 3.2. `load_done_order_for_pos(order_id)`
- **Modelo:** `pos.order`
- **Descripción:** Prepara y retorna los datos detallados de un pedido y sus líneas para cargarlo en el frontend.
- **Campos retornados:** `id`, `date_order`, `pos_reference`, `name`, `partner_id`, `fiscal_position`, `line_ids` (con `product_id`, `qty`, `price_unit`, `discount`, `pack_lot_names`), `statement_ids`.

## 4. Frontend (Point of Sale JS)

### 4.1. Extensiones de Modelos
- `models.Order`: Sobrescribe `init_from_JSON`, `export_as_JSON` y `export_for_printing` para incluir datos de trazabilidad (`returned_order_id`).

### 4.2. Componentes UI (Widgets)
- `ListOrderButtonWidget`: Botón en el header para abrir la lista de pedidos.
- `OrderListScreenWidget`: Pantalla principal de gestión. Maneja búsqueda reactiva (timeout 70ms), paginación y acciones.
    - Se extiende `_prepare_order_from_order_data` para guardar `original_payments` en el objeto `order` durante una devolución.
- `PaymentScreenWidget`: Extendido para implementar validaciones en devoluciones.
    - `click_paymentmethods(id)`: Bloquea métodos de pago no presentes en la orden original.
    - `order_is_valid()`: 
        - Valida que el monto reembolsado por cada método no exceda el original.
        - Valida que el balance pendiente (`get_due()`) sea exactamente cero para devoluciones.
- `ReceiptScreenWidget`: Extendido para manejar la impresión de pedidos "recargados" y añadir la etiqueta de duplicado.

## 5. Plantillas QWeb (XML)
- `ListOrderButtonWidget`: Icono de carrito.
- `OrderListScreenWidget`: Estructura de la tabla y buscador.
- `OrderLine`: Fila de pedido con botones condicionales según permisos en `pos.config`.
- `OrderDetails`: Detalles de productos cargados bajo demanda.
- `PosTicket`/`XmlReceipt`: Extensiones para mostrar información de rectificación y etiqueta "DUPLICATE".

## 6. Seguridad y Permisos
- El acceso está controlado por los flags en `pos.config`.
- Los métodos RPC requieren una sesión activa de POS (`pos_session_id`).
