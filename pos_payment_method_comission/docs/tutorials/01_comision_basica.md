# Escenario 1: Datáfono Estándar (Comisión Fija + Porcentual)
**Objetivo del Video:** Mostrar lo rápido que es configurar el módulo y el asiento contable automático.

## 1. Preparación
* Moneda: COP (Pesos Colombianos).
* Cuenta de Activo: `112001 - Pendiente Datáfono Redeban` (Tipo: Por Cobrar, Reconcile: True).
* Cuenta de Gasto: `530515 - Gastos Bancarios Comisiones`.

## 2. Configuración
1. En TPV > Métodos de Pago, crea "Datáfono Redeban".
2. **Cuenta Intermediaria:** `112001`.
3. Activa **"Apply Commission"**.
4. **Commission Rate (%):** `2.00`.
5. **Fixed Commission Amount:** `100.00`.
6. **Expense Account:** `530515`.

## 3. Ejecución
1. En TPV, vende $100.000 COP y cobra con Datáfono Redeban.
2. Cierra sesión.

## 4. Verificación
1. Ve al asiento contable. 
2. Hay Débito a `530515` por **$2.100**. Crédito a `112001` por **$2.100**.
