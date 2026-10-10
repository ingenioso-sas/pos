import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Backfill vat <- identificacion on module update.
    # Only fills empties, never overwrites an existing vat.
    # Mirrors hooks.post_init_hook (which only runs on install).
    cr.execute(
        """
        UPDATE res_partner
        SET vat = identificacion
        WHERE (vat IS NULL OR vat = '')
          AND identificacion IS NOT NULL
          AND identificacion != ''
        """
    )
    _logger.info("pos_partner migration: %s partners backfilled vat <- identificacion", cr.rowcount)
