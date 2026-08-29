# Escenario 2: Comisiones con Impuestos (IVA)
**Objetivo:** Demostrar cómo el módulo separa el IVA descontable del gasto neto de la comisión.

## 1. Preparación
* Cuenta puente: `112002 - Pendiente Wompi`.
* Cuenta de Gasto: `530515`.
* Impuesto: `IVA 19% Compras`.

## 2. Configuración
1. Crea método "Pago Wompi" con cuenta `112002`.
2. Activa comisiones, Rate: `3.00`.
3. **Impuestos de la Comisión:** selecciona `IVA 19% Compras`.

## 3. Ejecución
1. Vende $100.000 COP, paga con Wompi, cierra sesión.

## 4. Verificación
1. Revisa el asiento: Comisión base es $3.000. El IVA es $570.
2. Débito a Gasto: $3.000. Débito a IVA: $570. Crédito a `112002`: $3.570.
