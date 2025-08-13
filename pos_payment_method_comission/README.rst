✦ He completado la implementación del addon. El siguiente paso lógico es explicar cómo instalarlo, configurarlo y usarlo en Odoo.

  Pasos para la Instalación y Uso

   1. Asegurar la Estructura de Archivos: El addon pos_payment_method_comission debe estar en tu carpeta de addons de Odoo.

   2. Reiniciar el Servidor de Odoo: Después de colocar el addon, reinicia el servicio de Odoo para que reconozca el nuevo módulo.

   3. Actualizar la Lista de Aplicaciones:
       * Ve a Aplicaciones en el backend de Odoo.
       * Activa el Modo de Desarrollador (Ajustes -> Activar el modo de desarrollador).
       * Vuelve a Aplicaciones y haz clic en Actualizar la lista de aplicaciones.

   4. Instalar el Addon:
       * Busca Point of Sale - Payment Method Commission en la barra de búsqueda de Aplicaciones.
       * Haz clic en el botón Instalar.

  Cómo Configurar las Comisiones

   1. Ir a los Métodos de Pago del TPV:
       * Ve a Punto de Venta -> Configuración -> Métodos de Pago.
       * Selecciona un método de pago existente (ej. Tarjeta de Crédito) o crea uno nuevo.

   2. Activar y Definir la Comisión:
       * En el formulario del método de pago, verás una nueva sección llamada "Commission Settings".
       * Marca la casilla "Apply Commission".
       * Tipo de Comisión: Elige entre Percentage (un % del monto del pago) o Fixed (un monto fijo por transacción).
       * Tasa/Monto: Rellena el campo Commission Rate (%) o Fixed Commission Amount según tu elección.
       * Cuenta de Gastos: Selecciona la Commission Expense Account. Este es un paso crucial. Debe ser una cuenta de tipo "Gasto" donde se registrarán todas las
         comisiones.
       * Guarda los cambios.

  Cómo Funciona en el Punto de Venta

   1. Abrir una Sesión de TPV: Inicia una nueva sesión en tu Punto de Venta.

   2. Procesar un Pedido:
       * Añade productos al carrito como de costumbre.
       * Procede a la pantalla de Pago.
       * Selecciona el método de pago que has configurado con una comisión.

   3. Ver la Comisión:
       * Al introducir el monto del pago, la comisión se calculará y se mostrará automáticamente debajo de la línea de pago.
       * El total a pagar por el cliente no cambia, la comisión es un gasto interno.

   4. Validar y Recibo:
       * Valida el pago.
       * En el recibo impreso, aparecerá una nueva línea detallando el Total de la Comisión del pedido.

  Verificación Contable

   1. Cerrar la Sesión del TPV: Cierra la sesión y contabiliza los asientos.
   2. Revisar los Asientos Contables:
       * Ve al módulo de Contabilidad.
       * Busca los asientos contables relacionados con tu sesión de TPV.
       * Por cada pago con comisión, se habrá creado un asiento contable adicional moviendo el saldo desde la cuenta del método de pago a la cuenta de gastos por
         comisión que configuraste.