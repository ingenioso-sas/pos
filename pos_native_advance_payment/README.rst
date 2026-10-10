====================================
POS Native Advance Payment (Cartera)
====================================

Este módulo integra los **Saldos a Favor** (Anticipos Nativos) de los clientes directamente en el Punto de Venta (TPV) de Odoo 13, permitiendo utilizarlos como métodos de pago de forma controlada y automatizada.

A diferencia de módulos de terceros que crean sus propias tablas de "billeteras virtuales" desconectadas de la contabilidad real, este módulo **lee directamente de los apuntes contables (account.move.line)**, garantizando una exactitud financiera al 100%.

Funcionalidades Principales
===========================

1. **Lectura de Saldos Nativos:** Calcula el saldo a favor disponible de un cliente sumando los apuntes no conciliados en la cuenta de anticipos.
2. **Validación Restrictiva en TPV:** Impide que los cajeros cobren un monto superior al saldo disponible + límite de sobregiro del cliente.
3. **Visibilidad Inmediata:** Muestra el "Saldo a Favor" disponible en la lista de clientes del TPV (en verde) y en la misma pantalla de pago.
4. **Conciliación Automática FIFO:** Al pagar con Saldo a Favor, el módulo cruza (concilia) automáticamente —mediante matching parcial FIFO— el nuevo débito contra los créditos abiertos del anticipo original, sin exigir montos exactos.
5. **Devolución a Saldo a Favor:** Al hacer un reembolso con el método de Saldo a Favor, se acredita el monto como nuevo saldo disponible para el cliente.
6. **Bloqueo Pesimista:** Evita race conditions en entornos multisesión bloqueando las líneas contables durante la conciliación.
7. **Saldo en Tiempo Real:** Consulta el saldo disponible del cliente desde el servidor cada vez que se abre la pantalla de pago, reduciendo el riesgo de datos obsoletos.
8. **Configuración por Cliente:** Permite habilitar/deshabilitar el uso de Saldo a Favor por cliente y definir límites de sobregiro individuales.
9. **Historial de Movimientos:** Botón "Ver movimientos" en el TPV que abre el listado de apuntes contables de la cuenta de anticipos.
10. **Reporte de Cartera (PDF):** Reporte imprimible con saldos por cliente, antigüedad y totales.
11. **Pago de Facturas desde Saldo:** Wizard en Contabilidad para pagar facturas abiertas usando el saldo a favor disponible.

Configuración (Para el Contador/Administrador)
==============================================

1. **Definir la Cuenta de Anticipos:**
   * Ir a **Ajustes -> Punto de Venta**.
   * En la nueva sección *Anticipos y Saldos a Favor*, seleccionar la **Cuenta de Anticipos para TPV** (Ej. la cuenta `2805` - Anticipos de Clientes).
   * Guardar.

2. **Configurar el Método de Pago:**
   * Ir a **Punto de Venta -> Configuración -> Métodos de Pago**.
   * Crear o editar el método llamado "Saldo a Favor" o "Cartera".
   * Marcar la casilla **"Es Método de Saldo a Favor"**. 
   * Automáticamente, la cuenta por cobrar de este método cambiará a la configurada en el paso anterior.

Uso (Para el Cajero)
====================

1. En el TPV, al hacer clic en el botón "Cliente", verás una nueva columna llamada **Saldo a Favor**.
2. Los clientes que tengan anticipos registrados mostrarán su saldo disponible en color **Verde**.
3. Selecciona el cliente y procede al pago.
4. Si intentas pagar usando el método "Saldo a Favor", el sistema validará que el cliente seleccionado tenga saldo suficiente. Si no es así, el TPV te bloqueará con una advertencia en pantalla.

Casos Prácticos
===============

* **El cliente dejó un anticipo ayer en el banco:** El contador lo registró en *Contabilidad -> Pagos* usando la cuenta de anticipos. Hoy el cliente llega a la tienda y su saldo a favor ya es visible en el TPV.
* **El cajero devuelve un producto y entrega Saldo a Favor:** Si el TPV hace una devolución y se envía a la cuenta de anticipos, el cliente acumula saldo a favor de inmediato para su próxima compra.

Soporte y Autor
===============

Desarrollado a la medida para garantizar el control estricto de la cartera y anticipos en el ecosistema contable de Odoo Colombia.
* Autor: Ing.Factura S.L. / Asistente IA
