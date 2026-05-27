# Especificación Técnica - pos_order_mgmt

## 1. Arquitectura del Sistema
El módulo sigue la arquitectura estándar de Odoo 13 (MVC). Extiende modelos existentes en el backend (Python) y widgets en el frontend (JS) utilizando herencia.

## 2. Modelo de Datos (PostgreSQL)

### 2.1. `pos.config` (Extensión)
| Campo | Tipo | Descripción | Ayuda / Origen | Confianza |
|-------|------|-------------|----------------|-----------|
| `iface_order_mgmt` | Boolean | Habilita el botón de gestión en el POS | Activa el icono de carrito en el POS. Config: *Punto de Venta > Configuración > [POS] > Order Management*. | ✅✅✅ |
| `iface_reprint_done_order` | Boolean | Permite reimprimir pedidos finalizados | Habilita botón de impresora en la lista. Config: *[POS] > Reprint Orders*. | ✅✅✅ |
| `iface_return_done_order` | Boolean | Permite devolver pedidos finalizados | Habilita botón de flecha curva en la lista. Config: *[POS] > Return Orders*. | ✅✅✅ |
| `iface_copy_done_order` | Boolean | Permite duplicar pedidos finalizados | Habilita botón de duplicado en la lista. Config: *[POS] > Duplicate Orders*. | ✅✅✅ |
| `iface_load_done_order_max_qty` | Integer | Cantidad máx. a cargar/tamaño de página | Define cuántos pedidos se traen al iniciar y el tamaño de página. Config: *[POS] > Maximum Orders to load*. | ✅✅✅ |

### 2.2. `pos.order` (Extensión)
| Campo | Tipo | Descripción | Ayuda / Origen | Confianza |
|-------|------|-------------|----------------|-----------|
| `returned_order_id` | Many2one | Vínculo al pedido original en devoluciones | Se asigna automáticamente al crear una devolución desde el frontend. | ✅✅ |
| `returned_order_reference` | Char | Referencia del pedido original (relacionado) | Se muestra en el ticket de devolución. Viene de `returned_order_id.pos_reference`. | ✅✅ |
| `refund_order_ids` | One2many | Pedidos de reembolso generados desde este | Lista de todos los reembolsos vinculados a la venta original. | 🔸 |
| `refund_order_qty` | Integer | Cantidad de reembolsos (computado) | Conteo de registros en `refund_order_ids`. | 🔸 |

## 3. APIs y Endpoints (Odoo RPC)

### 3.1. `search_done_orders_for_pos(query, pos_session_id, page)`
- **Modelo:** `pos.order`
- **Descripción:** Busca pedidos que cumplan los criterios de filtro y paginación.
- **Parámetros:**
    - `query` (String): Término de búsqueda (Nombre, Ref, Cliente, Producto).
    - `pos_session_id` (Integer): ID de la sesión actual del POS (para obtener la configuración).
    - `page` (Integer): Número de página solicitado (empieza en 0).
- **Filtros aplicados:**
    - `state`: 'paid', 'done', 'invoiced'.
    - Si no hay query: filtra por `config_id` de la sesión actual.
    - Si hay query: busca en `name`, `pos_reference`, `partner_id.display_name`, `lines.product_id.name`.
- **Retorno:** Objeto con `items` (lista de pedidos) y metadatos de paginación (`current_page`, `next_page`, `total_items`, `total_pages`, `page_size`).

### 3.2. `load_done_order_for_pos(order_id)`
- **Modelo:** `pos.order`
- **Descripción:** Prepara y retorna los datos detallados de un pedido y sus líneas para cargarlo en el frontend.
- **Parámetros:**
    - `order_id` (Integer): ID del pedido a cargar.
- **Campos retornados:** 
    - `id`, `date_order`, `pos_reference`, `name`, `partner_id`, `fiscal_position`.
    - `line_ids`: Lista de líneas con `product_id`, `qty`, `price_unit`, `discount`, `pack_lot_names`.
    - `statement_ids`: Lista de pagos con `journal_id`, `amount`, `payment_method_id`.

## 4. Frontend (Point of Sale JS)

### 4.1. Extensiones de Modelos
- `models.Order`: Sobrescribe `init_from_JSON`, `export_as_JSON` y `export_for_printing` para incluir datos de trazabilidad (`returned_order_id`).
    - **Edición (Confirmación de Modificación de Pendientes):** Sobrescribe `initialize` para definir `allowed_to_modify = false`.

### 4.2. Componentes UI (Widgets)
- `ListOrderButtonWidget`: Botón en el header para abrir la lista de pedidos.
- `OrderListScreenWidget`: Pantalla principal de gestión. Maneja búsqueda reactiva (timeout 70ms), paginación y acciones.
    - Se extiende `_prepare_order_from_order_data` para guardar `original_payments` en el objeto `order` durante una devolución.
- `ProductScreenWidget` y `PaymentScreenWidget`:
    - **Adición (Intercepción en Captura y Popups):** Extienden `renderElement` para añadir un escuchador nativo de clics en la fase de captura (`useCapture = true`). Si el cajero hace clic en un elemento que pudiera modificar la orden (`.numpad, .product-list, .set-customer, .pay, .orderline, .paymentmethods, .payment-numpad, .js_customer, .js_invoice, .js_electronic_invoice`) y la orden está pendiente de sincronización, detiene la propagación del evento (`event.stopPropagation()`) y presenta el popup personalizado `OrderConfirmModifyPopupWidget` (`order_confirm_modify`) solicitando la frase `"modificar orden"`. Si confirma, establece `allowed_to_modify = true` para desbloquear la interfaz; si no, levanta un popup amigable del POS sin lanzar excepciones de JS.
- `PaymentScreenWidget`: Extendido para implementar validaciones en devoluciones.
    - `click_paymentmethods(id)`: Bloquea métodos de pago no presentes en la orden original.
    - `order_is_valid()`: 
        - Valida que el monto reembolsado por cada método no exceda el original.
        - Valida que el balance pendiente (`get_due()`) sea exactamente cero para devoluciones.
        - **Edición (Validación de Cantidad Cero):** Verifica que ninguna línea de la orden tenga una cantidad de `0`. Si existe, muestra una alerta al usuario identificando el producto específico y detiene la validación.
    - `renderElement()`: Deshabilita los botones de factura, factura electrónica y cambio de vendedor si es una devolución.
- `ReceiptScreenWidget`: Extendido para manejar la impresión de pedidos "recargados" y añadir la etiqueta de duplicado.

## 5. Plantillas QWeb (XML)
- `ListOrderButtonWidget`: Icono de carrito.
- `OrderListScreenWidget`: Estructura de la tabla y buscador.
- `OrderLine`: Fila de pedido con botones condicionales según permisos en `pos.config`.
- `OrderDetails`: Detalles de productos cargados bajo demanda.
- `PosTicket`/`XmlReceipt`: Extensiones para mostrar información de rectificación y etiqueta "DUPLICATE".
- `OrderConfirmModifyPopupWidget`: Template para el popup personalizado de advertencia y confirmación de edición.


## 6. Seguridad y Permisos
- El acceso está controlado por los flags en `pos.config`.
- Los métodos RPC requieren una sesión activa de POS (`pos_session_id`).
