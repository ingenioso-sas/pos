Formulario convencional (Contactos)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#. Ir a Contactos y abrir un cliente.
#. El campo ``vat`` se muestra con la etiqueta *Identification* (*Identificación* en español).
#. Informar la fecha de nacimiento en ``fecha_nac``; ``mes_nac`` se calcula y almacena solo,
   y ``edad`` se calcula al vuelo.
#. En la vista de lista existe la columna ``mes_nac`` y en el buscador se puede
   filtrar y agrupar por *Mes Nacimiento*.

Punto de venta (TPV)
~~~~~~~~~~~~~~~~~~~~

#. Abrir la sesión del POS y entrar a Clientes.
#. La lista muestra la columna *Identification* con el valor de ``vat`` y permite
   buscar por número de identificación.
#. Al seleccionar un cliente con fecha de nacimiento en el mes actual se muestra
   *MONTH OF BIRTHDAY*, y si es el día exacto, *BIRTHDAY* con confeti.
#. Con el botón de editar se puede modificar la fecha de nacimiento y la identificación.
#. El campo *Tipo doc.* (tipo de documento) aparece solo si está instalado ``l10n_co``
   y **no** está instalado ``l10n_co_edi_jorels_pos``. Si Jorels está instalado,
   manda su propio selector con sus validaciones de facturación electrónica.

Reglas para el funcionamiento correcto
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#. **Dependencias.** Solo ``account`` y ``point_of_sale``. ``l10n_co`` es opcional:
   sin él no hay selector de tipo de documento pero el resto funciona normal.
   No se debe agregar ``l10n_co_pos`` como dependencia (aporta recibo DIAN y
   ajustes de ``pos.config`` que este módulo no necesita).
#. **Migración a ``vat``.** Al instalar, ``post_init_hook`` copia ``identificacion``
   a ``vat`` solo en partners con ``vat`` vacío; nunca sobrescribe un ``vat`` existente.
   Al actualizar a 13.0.1.7.0 o superior corre la migración
   ``migrations/13.0.1.7.0/post-migration.py`` con la misma regla. ``create``/``write``
   mantienen la misma regla hacia adelante.
#. **Coexistencia con Jorels.** Si ``l10n_co_edi_jorels_pos`` está instalado, su
   funcionalidad prevalece: este módulo detecta su selector en el formulario y no
   modifica etiquetas, validaciones ni guardado. No renombrar el *Tax ID* nativo
   en QWeb para no romper su reemplazo a *NIT*. Ver ``DEUDA_TECNICA.md`` en el addon
   de Jorels para los bugs conocidos de ese módulo.
#. **No usar junto a ``partner_pos``.** Este módulo lo reemplaza; mantener ambos
   duplica la columna ``mes_nac`` en la lista y el filtro de búsqueda.
#. **Actualización.** Tras cada cambio aplicar ``-u pos_partner`` y recargar el TPV
   (Ctrl+F5) para refrescar assets y QWeb. Las traducciones al español están en
   ``i18n/es_CO.po`` (idioma ``es_CO``).
