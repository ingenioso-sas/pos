# Escenario 6: Reversión de Comisión en Devoluciones
**Objetivo:** Ver qué pasa cuando se anula una venta y la pasarela devuelve la comisión.

## 1. Configuración
1. En método "Pasarela Internacional", activa **"Reversar Comisión en Devoluciones"**.

## 2. Ejecución
1. Reembolsa una orden de -$100.000, cierra la sesión.

## 3. Verificación
1. El asiento contable será inverso: Crédito a Gastos por $5.000, Débito a cuenta puente.
