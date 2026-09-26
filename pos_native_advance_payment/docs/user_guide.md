# Guía de Usuario — POS Native Advance Payment (Cartera)

## Índice

1. [¿Qué hace este módulo?](#qué-hace-este-módulo)
2. [Configuración Inicial](#configuración-inicial)
   - [1. Definir la cuenta de anticipos](#1-definir-la-cuenta-de-anticipos)
   - [2. Configurar el método de pago](#2-configurar-el-método-de-pago)
   - [3. Configurar cliente](#3-configurar-cliente)
3. [Uso en el TPV](#uso-en-el-tpv)
    - [Visualizar saldo a favor](#visualizar-saldo-a-favor)
    - [Depósito a Saldo a Favor](#depósito-a-saldo-a-favor)
    - [Cobrar con saldo a favor](#cobrar-con-saldo-a-favor)
    - [Reembolsar a saldo a favor](#reembolsar-a-saldo-a-favor)
    - [Historial de movimientos](#historial-de-movimientos)
4. [Reporte de Cartera](#reporte-de-cartera)
5. [Pago de Facturas desde Saldo a Favor](#pago-de-facturas-desde-saldo-a-favor)
6. [Preguntas Frecuentes](#preguntas-frecuentes)

---

## ¿Qué hace este módulo?

Este módulo permite que los clientes usen sus **saldos a favor** (anticipos registrados en contabilidad) como método de pago en el TPV (Punto de Venta).

A diferencia de otros módulos que crean tablas paralelas de "billeteras virtuales", este módulo **lee directamente de `account.move.line`** — la misma tabla donde la contabilidad registra los pagos anticipados. Esto garantiza:

- **Exactitud financiera al 100%** — no hay desfase entre el saldo visible en TPV y la contabilidad real.
- **Sin doble contabilidad** — los anticipos se registran una sola vez, de forma nativa.
- **Conciliación automática** — al cobrar con saldo a favor, el asiento se concilia contra el anticipo original.

---

## Configuración Inicial

### 1. Definir la cuenta de anticipos

Ruta: **Ajustes → Punto de Venta → Anticipos y Saldos a Favor**

<pre>
┌──────────────────────────────────────────────────────┐
│  Anticipos y Saldos a Favor                           │
│                                                       │
│  ☐ Cuenta de Anticipos (Saldos a Favor)              │
│    Cuenta contable para rastrear los saldos a favor   │
│    de los clientes.                                   │
│    [Cuenta de Anticipos para TPV ______________ ▼]    │
│                                                       │
│  ☐ Límite de Sobregiro por Defecto                   │
│    Límite de sobregiro predeterminado para todos los  │
│    clientes. Se puede ajustar por cliente.             │
│    [0.00]                                              │
└──────────────────────────────────────────────────────┘
</pre>

Selecciona la cuenta contable que usarás para rastrear los anticipos de clientes (ej. "2805 — Anticipos de Clientes").

> 💡 **¿Qué tipo de cuenta usar?**
>
> Los saldos a favor (anticipos recibidos de clientes) deben registrarse en una cuenta de **PASIVO**, porque son dinero que la empresa le debe al cliente (en bienes, servicios o devolución) — no es un activo.
>
> En el PUC colombiano la cuenta correcta es **2805 - Anticipos de Clientes** (subcuenta `280505` si tu plan la desglosa).
>
> Para que la cuenta aparezca en este selector, debe cumplir **ambos** requisitos:
> 1. **Tipo interno**: `Pagado / Cuenta por pagar` (payable)
> 2. **Conciliar**: activado ✅
>
> Si la cuenta no aparece, configúrala en *Contabilidad → Configuración → Plan de Cuentas*:
> - Abre la cuenta (ej. 280505) y en el campo **Tipo interno** selecciona *Pagado / Cuenta por pagar*.
> - Marca la casilla **Permite conciliación**.
>
> **¿Por qué debe ser conciliable?** El módulo concilia los depósitos (créditos en la cuenta) contra el consumo posterior en ventas (débitos) en orden FIFO. Solo las cuentas reconciliables permiten crear conciliaciones parciales y mantienen el campo `amount_residual` que el módulo usa para calcular el saldo disponible real por cliente. Sin conciliación, el saldo disponible sería incorrecto.

Opcionalmente, define un **límite de sobregiro por defecto** (monto máximo que un cliente puede exceder su saldo a favor).

### 2. Configurar el método de pago

Ruta: **Punto de Venta → Configuración → Métodos de Pago**

1. Crea o edita un método de pago (ej. "Saldo a Favor" o "Cartera").
2. Marca la casilla **"Es Método de Saldo a Favor"**.
3. Automáticamente, la **Cuenta por Cobrar** del método cambiará a la cuenta de anticipos configurada en el paso anterior.
4. Guarda el método de pago.

> ⚠️ **Nota:** Un método de pago no puede ser "Saldo a Favor" y "Efectivo" al mismo tiempo.

### 3. Configurar cliente

Ruta: **Contactos → [Seleccionar Cliente]**

En la pestaña **Saldo a Favor (TPV)** del formulario del cliente:

<pre>
┌─────────────────────────────────────────────┐
│  Saldo a Favor (TPV)                        │
│                                             │
│  ☑ Permite Saldo a Favor en TPV            │
│  Límite de Sobregiro: [0.00]                │
│  Saldo a Favor (TPV): [___]                 │
│  [🔍 Ver movimientos]                       │
└─────────────────────────────────────────────┘
</pre>

- **Permite Saldo a Favor en TPV:** Desmarca esta casilla para clientes que no deben usar saldo a favor (ej. morosos).
- **Límite de Sobregiro:** Define un límite individual (si es 0, usa el límite por defecto de la compañía; si la compañía tiene 0, no hay sobregiro permitido).
- **Saldo a Favor (TPV):** Muestra el saldo disponible calculado de la cuenta de anticipos.
- **Ver movimientos:** Abre el historial de apuntes contables en la cuenta de anticipos.

---

## Uso en el TPV

### Visualizar saldo a favor

- **En la lista de clientes:** Se muestra una columna "Saldo a Favor" con el valor disponible. Si es positivo, aparece en **verde**.
- **En los detalles del cliente:** Al seleccionar un cliente, se muestra el saldo a favor.
- **En la pantalla de pago:** Cuando tienes un cliente seleccionado, ves una barra con el saldo a favor disponible justo encima del resumen de pago.

### Depósito a Saldo a Favor

Puedes recibir dinero de un cliente y acreditarlo directamente a su saldo a favor sin necesidad de crear facturas ni ir al backend de contabilidad.

1. En la pantalla de productos del TPV, selecciona un **cliente**.
2. La orden debe estar **vacía** (sin productos agregados).
3. Haz clic en el botón **"Abonar a Saldo a Favor"** (botón celeste debajo de la lista de productos).

   <pre>
   ┌──────────────────────────────────────┐
   │  Orden Vacía                          │
   │  Cliente: Juan Pérez                  │
   │                                       │
   │  ┌──────────────────────────────────┐ │
   │  │  Abonar a Saldo a Favor          │ │
   │  └──────────────────────────────────┘ │
   └──────────────────────────────────────┘
   </pre>

4. En la ventana emergente, ingresa el **monto a depositar** y haz clic en "Depositar".
5. El sistema:
   - Crea una orden de TPV sin productos.
   - Genera el asiento contable: **Débito → Caja / Crédito → Cuenta de Anticipos**.
   - Acredita el monto al saldo a favor del cliente.
6. Verás un mensaje de confirmación. El saldo a favor del cliente se actualiza automáticamente.

> ⚠️ El método de pago se selecciona automáticamente (el primero disponible que no sea "Saldo a Favor"). Para usar un método específico, registra el anticipo desde **Contabilidad → Pagos**.

**Ejemplo de asiento para un depósito de $200:**

| Cuenta | Débito | Crédito |
|--------|--------|---------|
| Caja   | $200   |         |
| Anticipos de Clientes | | $200 |

Este crédito de $200 queda disponible inmediatamente para futuras compras del cliente en el TPV.

### Cobrar con saldo a favor

1. Abre el TPV y agrega productos a la orden.
2. Selecciona un cliente (obligatorio para usar saldo a favor).
3. Ve a la pantalla de pago.
4. Selecciona el método de pago "Saldo a Favor" (aparece resaltado en **verde**).
5. Ingresa el monto a cobrar.
6. Completa el pago — el sistema:
   - Verifica que el cliente tenga saldo suficiente (`saldo + sobregiro ≥ monto a cobrar`).
   - Registra el asiento contable: **Débito → Cuenta de Anticipos**.
   - Concilia automáticamente el débito contra los créditos más antiguos (FIFO).

> ⚠️ Si el cliente no tiene saldo suficiente, verás una advertencia y no podrás finalizar la orden.

### Reembolsar a saldo a favor

1. En el TPV, haz clic en el botón **Reembolso**.
2. Selecciona la orden original a reembolsar.
3. Confirma los productos a devolver.
4. En la pantalla de pago, selecciona el método **"Saldo a Favor"** como forma de reembolso.
5. El monto se **acreditará** al saldo a favor del cliente, quedando disponible para futuras compras.
6. El asiento contable generado es: **Crédito → Cuenta de Anticipos** (aumenta el saldo del cliente).

### Historial de movimientos

En los detalles del cliente, haz clic en el botón **"Ver movimientos"**. Se abrirá una nueva pestaña en tu navegador con el listado de los últimos 50 apuntes contables de la cuenta de anticipos para ese cliente.

---

## Reporte de Cartera

Ruta: **Contabilidad → Clientes → Cartera - Saldos a Favor**

<pre>
┌──────────────────────────────────────────────────────┐
│  Reporte de Cartera - Saldos a Favor                  │
│                                                       │
│  Compañía:  [Mi Compañía ____________ ▼]              │
│  Cuenta de Anticipos: [2805 - Anticipos Clientes]     │
│  Clientes:  [___________________________]             │
│  ☐ Incluir saldos en cero                            │
│                                                       │
│  ┌──────────────────────────────────────────────┐    │
│  │ Cliente      │ Saldo    │ Días │ Antigüedad  │    │
│  ├──────────────────────────────────────────────┤    │
│  │ Juan Pérez   │ $150.00  │  45  │ 31-60 días  │    │
│  │ María García │ $200.00  │  10  │ ≤ 30 días   │    │
│  │ Total        │ $350.00  │      │             │    │
│  └──────────────────────────────────────────────┘    │
│                                                       │
│  [Generar] [Imprimir PDF] [Cerrar]                    │
└──────────────────────────────────────────────────────┘
</pre>

1. Selecciona los filtros deseados (compañía, clientes específicos, incluir/excluir saldos en cero).
2. Haz clic en **"Generar"** para ver los resultados.
3. Haz clic en **"Imprimir PDF"** para obtener el reporte en formato PDF.

El reporte incluye:
- Nombre del cliente
- Saldo a favor disponible
- Antigüedad del saldo (≤ 30 días, 31–60 días, > 60 días)
- Fecha del movimiento más antiguo y más reciente
- Total general

---

## Pago de Facturas desde Saldo a Favor

Ruta: **Contabilidad → Clientes → Pagar con Saldo a Favor**

<pre>
┌──────────────────────────────────────────────────────┐
│  Pagar Facturas con Saldo a Favor                    │
│                                                       │
│  Cliente:  [Juan Pérez _______________ ▼]            │
│  Saldo a Favor Disponible:  $150.00                  │
│  Total Seleccionado:  $120.00                         │
│                                                       │
│  Facturas Pendientes:                                │
│  ┌──────────────────────────────────────────────┐    │
│  │ Factura │ Fecha      │ Total   │ Estado       │    │
│  ├──────────────────────────────────────────────┤    │
│  │ INV-001 │ 01/07/2026 │ $120.00 │ posted       │    │
│  │ INV-002 │ 15/07/2026 │ $80.00  │ posted       │    │
│  └──────────────────────────────────────────────┘    │
│                                                       │
│  [Pagar con Saldo a Favor]  [Cancelar]               │
└──────────────────────────────────────────────────────┘
</pre>

1. Selecciona el cliente.
2. Se mostrarán las facturas abiertas del cliente.
3. Marca las facturas que deseas pagar (puedes seleccionar varias).
4. El sistema verificará que el total seleccionado no exceda el saldo disponible.
5. Haz clic en **"Pagar con Saldo a Favor"**.
6. El sistema creará las conciliaciones parciales necesarias entre los créditos de la cuenta de anticipos y los débitos de las facturas seleccionadas.

> ⚠️ Este proceso **no crea nuevos pagos** — concilia directamente las líneas contables existentes. Equivale a una conciliación manual en Contabilidad, pero automatizada.

---

## Preguntas Frecuentes

### ¿Por qué el saldo a favor del cliente no se actualiza en el TPV?

El saldo se refresca cada vez que abres la pantalla de pago (vía RPC al servidor). Si ves un saldo desactualizado, cierra y vuelve a abrir la pantalla de pago. El saldo en la lista de clientes se actualiza al iniciar el TPV o al abrir el detalle del cliente.

### ¿Qué pasa si dos cajeros cobran al mismo cliente simultáneamente?

El módulo utiliza bloqueo pesimista (`SELECT FOR UPDATE NOWAIT`) en la base de datos. Si dos transacciones intentan usar el mismo saldo al mismo tiempo, una de ellas fallará con un error. La transacción que falla se revierte y el cajero debe reintentar.

### ¿Cómo registro un anticipo (saldo a favor) de un cliente?

Hay dos formas:

**Desde el TPV (recomendado para cajeros):**
1. En la pantalla de productos del TPV, selecciona el cliente.
2. Haz clic en **"Abonar a Saldo a Favor"**.
3. Ingresa el monto. El sistema crea el asiento automáticamente (Dr. Caja / Cr. Anticipos).

**Desde Contabilidad:** Crea un pago del cliente (tipo "Entrante") usando la cuenta de anticipos configurada en este módulo. El pago generará un crédito en la cuenta de anticipos que automáticamente estará disponible en el TPV.

Ejemplo de asiento al registrar un anticipo de $100 desde Contabilidad:

| Cuenta | Débito | Crédito |
|--------|--------|---------|
| Banco  | $100   |         |
| Anticipos de Clientes | | $100 |

### ¿Cómo se contabiliza una venta pagada con saldo a favor?

Al pagar en el TPV con el método "Saldo a Favor":

| Cuenta | Débito | Crédito |
|--------|--------|---------|
| Anticipos de Clientes | $50 | |
| Ingresos por Ventas | | $50 |

Luego, el módulo concilia automáticamente ese débito de $50 contra créditos anteriores en la misma cuenta de anticipos.

### ¿Puedo deshabilitar el saldo a favor para un cliente específico?

Sí. En el formulario del cliente, desmarca la casilla **"Permite Saldo a Favor en TPV"**. El método de pago dejará de estar disponible para ese cliente en el TPV.

### ¿Qué significa "Límite de Sobregiro"?

Es un monto adicional que el cliente puede usar por encima de su saldo a favor. Por ejemplo, si un cliente tiene $50 de saldo y un límite de sobregiro de $20, puede pagar hasta $70 usando el método de Saldo a Favor. Esto es útil para clientes frecuentes con relación de confianza.
