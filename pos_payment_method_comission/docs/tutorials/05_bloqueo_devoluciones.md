# Escenario 5: Bloqueo de Devoluciones a Pasarela
**Objetivo:** Mostrar cómo prevenir devoluciones de dinero en métodos que no lo permiten.

## 1. Configuración
1. En método "Tarjeta de Crédito", cambia "Política de Devolución" a **"Solo a Cartera / Saldo a Favor"**.

## 2. Ejecución
1. Reembolsa una orden pagada con Tarjeta (monto negativo).
2. Intenta pagar la devolución con "Tarjeta de Crédito". 
3. El sistema arrojará error indicando usar "Saldo a Favor".
