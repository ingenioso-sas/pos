# Escenario 3: Retenciones sobre el Total (ReteRenta)
**Objetivo:** Mostrar cómo se aplican retenciones en la fuente sobre el total de la venta (Anticipos).

## 1. Preparación
* Cuenta puente: `112003 - Pendiente Bold`.
* Impuesto: `Retención ReteRenta 1.5%` (Monto: `-1.5%`, Cuenta: `135515 - Anticipo ReteRenta`).

## 2. Configuración
1. Crea método "Datáfono Bold", cuenta `112003`.
2. Activa comisiones (ej. Rate `2.99`), y agrega IVA 19% en la comisión.
3. En **Retenciones sobre el Pago Total**, selecciona `Retención ReteRenta 1.5%`.

## 3. Ejecución
1. Vende $100.000 COP, cobra con Bold. Cierra sesión.

## 4. Verificación
1. Asiento consolidado: Gasto de $2.990, IVA de $568, y una línea adicional *"Retención"* con Débito de $1.500 a la cuenta `135515`.
