=========================================
Point of Sale - Payment Method Commission
=========================================

Este módulo de Odoo 13 permite definir y calcular automáticamente comisiones y sus impuestos asociados por el uso de métodos de pago específicos en el Punto de Venta (TPV). También incluye controles para referencias de aprobación y políticas restrictivas de devolución (como enviar dinero a Cartera).

Características Principales
===========================

1. **Cálculo Flexible de Comisiones**: Soporta tasas porcentuales, montos fijos o ambos simultáneamente.
2. **Impuestos y Retenciones (Estándar Odoo)**: Permite seleccionar múltiples impuestos de compra (IVA, Retefuente, ReteICA) para que apliquen sobre la comisión y ajusten correctamente el saldo por cobrar.
3. **Referencias de Aprobación**: Permite exigir un código de comprobante (ej. Addi, Sistecredito, Voucher) antes de validar el pago.
4. **Comisiones en Devoluciones**: Configurable para reversar (o no) el gasto de la comisión cuando se hace un reembolso al cliente.
5. **Política de Devolución Restringida (Candado de Cartera)**: Evita que el cajero devuelva dinero a través de métodos de crédito/pasarelas, forzándolo a usar métodos permitidos (como Saldo a Favor).

Instalación
===========

1. Copia la carpeta del módulo (`pos_payment_method_comission`) a tu directorio de *addons*.
2. Reinicia el servicio de Odoo (obligatorio al actualizar o instalar si hay cambios en modelos Python).
3. Activa el Modo de Desarrollador, actualiza la lista de aplicaciones e instala el módulo **Point of Sale - Payment Method Commission**.

Configuración de Comisiones
===========================

Ve a **Punto de Venta > Configuración > Métodos de Pago**, selecciona un método y localiza la sección de configuración de comisiones:

* **Apply Commission**: Actívalo para habilitar la función.
* **Commission Rate (%) y Fixed Commission**: Define el costo del servicio. Puedes usar ambos; el sistema los sumará.
* **Commission Journal y Account**:
  * **Commission Journal:** Diario contable (General). Todo asiento contable en Odoo requiere un diario. Esto te permite agrupar las comisiones (gastos) en un diario de "Operaciones Varias" en lugar de ensuciar el diario del banco.
  * **Commission Expense Account:** Cuenta de Gasto. Aunque el diario de un método de pago tiene una cuenta de débito por defecto (tu cuenta bancaria real/activo), la comisión es un gasto operativo. Con esta cuenta evitas que el gasto se confunda con el dinero de tu banco.
* **Impuestos de la Comisión**: Selecciona los impuestos creados en tu Contabilidad (ej. IVA 19% Compras, ReteRenta 1.5%) que se calculan sobre el gasto base.
* **Política de Devolución**:
  * *Devolución Real Permitida:* Comportamiento estándar.
  * *Solo a Cartera / Saldo a Favor:* Bloquea las devoluciones de dinero en el TPV si el cajero selecciona este método.
* **Pedir Referencia de Aprobación**: Si está activo, el cajero deberá digitar el número del voucher/crédito.
* **Reversar Comisión en Devoluciones**: Útil si la pasarela te devuelve el dinero de la comisión original cuando tú reembolsas una venta.

Caso Práctico: Implementación de "Saldo a Favor / Cartera"
==========================================================

El módulo no crea un sistema de "cartera" desde cero, sino que actúa como un **candado** para proteger la caja.

**El Problema:**
Un cliente compra con Addi. Días después pide una devolución. El cajero en el TPV hace un pedido en negativo, y por inercia, selecciona el método "Addi" para cerrar. Odoo aceptaría esto, lo que descuadraría la cartera contable real de Addi.

**La Solución:**
1. Configura el método de pago Addi con la Política de Devolución en **"Solo a Cartera / Saldo a Favor"**.
2. Crea un Diario Contable llamado "Cartera de Clientes" (Tipo Banco/Efectivo) con cuenta de pasivo (ej. 2805 Anticipos).
3. Crea un Método de Pago normal en el TPV llamado **"Saldo a Favor"** apuntando a ese diario.
4. Cuando el cajero intente devolver el dinero usando Addi, el TPV arrojará un error bloqueando la acción. El cajero se verá obligado a seleccionar el método "Saldo a Favor" por el valor a devolver. El sistema creará un pasivo (deuda a favor del cliente) para que en el futuro el cliente pueda comprar usando ese mismo método.

Verificación Contable
=====================

Al cerrar la sesión, Odoo genera el asiento de la venta. Inmediatamente el módulo genera un asiento contable separado para cada pago con comisión:
* **Débito**: A la cuenta de Gasto por el valor base de la comisión.
* **Débitos (Impuestos/Retenciones)**: Se generan líneas para el IVA y retenciones en las cuentas parametrizadas en los Impuestos de la Comisión.
* **Crédito**: A la cuenta por cobrar del Método de Pago por el monto total neto de la comisión y los impuestos. Esto rebaja el monto total que la pasarela te transferirá, permitiendo que la conciliación bancaria encaje a la perfección.