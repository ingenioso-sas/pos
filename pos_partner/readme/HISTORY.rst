13.0.1.12.0 (2026-10-11)
~~~~~~~~~~~~~~~~~~~~~~~

* [CHG] Marcador en consola al cargar ``document_type.js`` para diagnosticar
  despliegues (si falta la línea, el POS sirve assets viejos).

13.0.1.11.0 (2026-10-11)
~~~~~~~~~~~~~~~~~~~~~~~

* [ADD] Búsqueda local de clientes sin regex (``indexOf`` sobre texto normalizado:
  minúsculas, sin tildes, sin espacios/guiones) en ``db.js``; mismo resultado al
  escribir y al borrar. ``identificacion`` vuelve a cargarse solo como fallback
  transicional de búsqueda (I1), sin mostrarse.
* [CHG] ``screens.js``: el buscador escucha ``input`` (+ Enter) en lugar del
  ``keypress`` del core, con debounce 70ms y handlers con namespace.

13.0.1.10.0 (2026-10-11)
~~~~~~~~~~~~~~~~~~~~~~~

* [CHG] ``identificacion`` fuera de la interfaz del TPV (``models.js``/``db.js``):
  ya no se carga ni se busca en el POS. La columna y el sync en Python se mantienen
  como red de seguridad de la migración hacia ``vat``.
* [CHG] Rename *Tax ID* a *Identificación* en el TPV siempre que Jorels esté
  ausente, independiente de que ``l10n_co`` esté instalado. Sin cambios en otros
  addons.

13.0.1.9.0 (2026-10-11)
~~~~~~~~~~~~~~~~~~~~

* [ADD] Selector de tipo de documento (``l10n_co_document_type``) en el TPV vía
  ``static/src/js/document_type.js`` defensivo: solo actúa sin Jorels y sin ``l10n_co``
  no rompe la carga del POS. Sin dependencias nuevas.
* [CHG] El label *Tax ID* del TPV ya no se toca en QWeb para ceder a Jorels;
  el rename a *Identification* vive en el backend y en JS condicional.

13.0.1.8.0 (2026-10-11)
~~~~~~~~~~~~~~~~~~~~~~~

* [ADD] Vistas de ``mes_nac`` como ``partner_pos``: campo invisible en formulario,
  columna en lista y filtro/agrupamiento.

13.0.1.7.0 (2026-10-11)
~~~~~~~~~~~~~~~~~~~~~~~

* [ADD] Migración ``post-migration.py``: backfill ``vat`` desde ``identificacion``
  (solo vacíos) al actualizar.

1.0.0.0.0 (2021-01-01)
~~~~~~~~~~~~~~~~~~~~~~~

* [INIT] Creación del modulo.
