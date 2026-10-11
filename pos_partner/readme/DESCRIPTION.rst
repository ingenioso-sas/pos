Este módulo extiende los datos del cliente en el formulario convencional y en el punto de venta (TPV):

* Fecha de nacimiento (``fecha_nac``), mes de nacimiento calculado (``mes_nac``) y edad (``edad``).
* Identificación del cliente sobre el campo nativo ``vat`` (ID impuestos / Tax ID).
  El campo anterior ``identificacion`` quedó deprecated y solo existe para migrar su valor a ``vat``.
* Tipo de documento colombiano (``l10n_co_document_type`` de ``l10n_co``) en el formulario de cliente del TPV,
  únicamente cuando el addon de Jorels (``l10n_co_edi_jorels_pos``) no está instalado.
* Aviso de cumpleaños en el TPV (mes y día) con confeti al seleccionar al cliente.
