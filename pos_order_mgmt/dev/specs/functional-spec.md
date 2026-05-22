# Especificación Funcional - pos_order_mgmt

## 1. Propósito y Alcance
Este módulo extiende la funcionalidad del frontend del Punto de Venta (PoS) de Odoo para permitir la gestión de pedidos antiguos. Las capacidades principales incluyen la visualización, reimpresión, duplicación y devolución de pedidos históricos directamente desde la interfaz del POS.

## 2. Actores y Roles
- **Cajero del PoS:** Puede buscar pedidos antiguos, reimprimir tickets, duplicar pedidos o realizar devoluciones.
- **Administrador de Ventas:** Configura los permisos y límites de carga de pedidos en la configuración del PoS.

## 3. Capacidades y Casos de Uso

### CU-01: Visualización de Pedidos Históricos (✅✅✅ THREE_WAY)
- El sistema muestra un botón con icono de carrito de compras en la barra superior derecha.
- Al hacer clic, se abre una pantalla con la lista de pedidos.
- Los pedidos se cargan inicialmente según la configuración de "Maximum orders to load".

### CU-02: Búsqueda y Paginación (✅✅ VERIFIED)
- Permite buscar pedidos por referencia (✅✅ VERIFIED).
- **Extensión:** También permite buscar por nombre del pedido, cliente o productos (🔸 CODE_ONLY).
- El sistema soporta paginación si el número de resultados excede el límite configurado (🔸 CODE_ONLY).

### CU-03: Reimpresión de Tickets (✅✅✅ THREE_WAY)
- Permite imprimir un duplicado de un pedido antiguo.
- El ticket impreso incluye una etiqueta de "DUPLICATE" para evitar confusiones (🔸 CODE_ONLY).

### CU-04: Duplicación de Pedidos (✅✅✅ THREE_WAY)
- Permite crear un nuevo pedido en la sesión actual basándose en los productos de un pedido antiguo.

### CU-05: Devolución de Pedidos (✅✅✅ THREE_WAY)
- Permite crear un pedido de reembolso (cantidades negativas) basado en un pedido antiguo.
- Mantiene la trazabilidad del pedido original (✅✅ VERIFIED).

## 4. Reglas de Negocio
- **RN-01 (Conexión):** Se requiere conexión a internet (online) para buscar o cargar detalles de pedidos que no estén en la caché local (✅✅ VERIFIED).
- **RN-02 (Productos Desconocidos):** No se puede cargar un pedido si contiene productos que no están disponibles en la configuración actual del PoS (🔸 CODE_ONLY).
- **RN-03 (Trazabilidad):** Las devoluciones deben quedar vinculadas al pedido original mediante el campo `returned_order_id` (✅✅ VERIFIED).
- **RN-04 (Restricción de Métodos de Pago en Devoluciones):** En una devolución, solo se permiten los métodos de pago utilizados en la venta original (🆕 NEW).
- **RN-05 (Límite de Monto por Método de Pago):** En una devolución, el monto reembolsado por cada método de pago no puede exceder el monto pagado originalmente con ese mismo método (🆕 NEW).
- **RN-06 (Balance Exacto en Devoluciones):** El monto total de los pagos en una devolución debe ser exactamente igual al total de la orden (balance cero). No se permiten reembolsos parciales de dinero si los productos fueron devueltos en su totalidad, ni sobre-pagos (🆕 NEW).
- **RN-07 (Vendedor Predefinido):** En una devolución, el vendedor (cajero) se asigna automáticamente al mismo que realizó la venta original y no puede ser cambiado (🆕 NEW).
- **RN-08 (Facturación Bloqueada):** El tipo de facturación (normal o electrónica) se hereda de la orden original y se bloquea su edición en la pantalla de pago (🆕 NEW).

## 5. Configuración (✅✅✅ THREE_WAY)

Los siguientes campos se encuentran en *Punto de Venta > Configuración > Punto de Venta > [Nombre del POS] > Sección: Order Management*.

- **Habilitar Gestión de Pedidos (`iface_order_mgmt`):** 
    - *Qué es:* Un interruptor (booleano).
    - *Uso:* Activa la funcionalidad completa del módulo. Si está apagado, el icono de carrito no aparecerá.
    - *Origen:* Se configura manualmente por el administrador.
- **Máximo de Pedidos a Cargar (`iface_load_done_order_max_qty`):** 
    - *Qué es:* Un campo numérico (entero).
    - *Uso:* Determina cuántos pedidos se cargan en la caché inicial y el tamaño de los bloques de búsqueda (paginación). Un valor alto puede ralentizar la carga inicial.
    - *Origen:* Valor por defecto es 10.
- **Permisos Específicos:** 
    - *Reimpresión (`iface_reprint_done_order`):* Habilita el icono de impresora para obtener duplicados de tickets.
    - *Devolución (`iface_return_done_order`):* Habilita el icono de retorno para crear reembolsos.
    - *Duplicación (`iface_copy_done_order`):* Habilita el icono de copia para cargar productos en un nuevo pedido.
