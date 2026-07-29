# Documentación del Módulo: pos_payment_method_comission

## Descripción General
El módulo `pos_payment_method_comission` para Odoo 13 permite definir y calcular automáticamente comisiones por el uso de métodos de pago específicos en el Punto de Venta (TPV). Las comisiones pueden configurarse como un porcentaje del monto pagado o como un monto fijo, y el módulo genera automáticamente los asientos contables correspondientes, registrando la comisión como un gasto para la empresa.

## Funcionalidades Principales
1. **Configuración de Comisiones por Método de Pago**: Permite activar la función de comisiones en métodos de pago seleccionados.
2. **Cálculo Flexible**: Soporta tasas porcentuales y montos fijos.
3. **Integración con TPV**: Las comisiones se calculan dinámicamente en la interfaz del Punto de Venta.
4. **Automatización Contable**: Crea asientos contables automáticamente (debitando una cuenta de gastos y acreditando la cuenta por cobrar del método de pago).

## Requisitos
- **Odoo 13.0**
- Dependencias: `point_of_sale`, `account`

## Instalación y Configuración

### 1. Instalación
1. Colocar el directorio `pos_payment_method_comission` en tu carpeta de addons.
2. Reiniciar el servicio de Odoo.
3. Activar el Modo de Desarrollador, actualizar la lista de aplicaciones e instalar el módulo "Point of Sale - Payment Method Commission".

### 2. Configuración del Método de Pago
Para configurar un método de pago con comisión:
1. Navegar a **Punto de Venta > Configuración > Métodos de Pago**.
2. Seleccionar un método de pago o crear uno nuevo.
3. En el formulario, buscar los nuevos campos:
   - **Apply Commission**: Marcar para habilitar.
   - **Commission Rate (%)**: Definir el porcentaje a cobrar (de 0 a 100).
   - **Fixed Commission Amount**: Definir un monto fijo (si aplica).
   - **Commission Journal**: Seleccionar el diario contable (tipo general) donde se registrarán los asientos. **¿Por qué este campo?** Todo asiento contable (`account.move`) en Odoo necesita un Diario. Esto permite agrupar los gastos por comisiones en un diario específico (ej. "Operaciones Varias") en lugar de mezclar el gasto en el mismo diario de ingresos de banco/efectivo.
   - **Commission Expense Account**: Seleccionar una cuenta de tipo gasto para registrar el costo de la comisión. **¿Por qué este campo?** Un método de pago suele tener configurado un diario, y ese diario ya tiene cuentas por defecto (que normalmente son de Activo, es decir, el dinero en bancos). La comisión, sin embargo, es un Gasto operativo. Esta cuenta le dice al sistema que el dinero de la comisión se registre en una cuenta de Gastos y Comisiones Bancarias, logrando así un asiento preciso (Débito al Gasto y Crédito a la cuenta por cobrar del método de pago).

## Uso en Punto de Venta
1. Abrir una sesión del Punto de Venta.
2. Procesar una venta normalmente.
3. En la pantalla de pago, al seleccionar el método de pago configurado, la comisión se calculará y se mostrará bajo la línea de pago. 
4. El cliente paga el total de los productos; la comisión se maneja internamente como un gasto de la empresa.

## Verificación Contable
Al cerrar la sesión del TPV o procesar el pago:
- El sistema crea el asiento original de la venta.
- Adicionalmente, el método `_create_commission_moves` en `pos.order` genera un asiento contable que transfiere el valor de la comisión debitando la cuenta de gasto configurada y acreditando la cuenta puente/cobrar del método de pago.
