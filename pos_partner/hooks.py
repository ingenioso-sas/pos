from odoo import SUPERUSER_ID, api


def post_init_hook(cr, registry):
    # One-time backfill: vat <- identificacion where vat is empty.
    # Only fills empties, never overwrites an existing vat.
    cr.execute(
        """
        UPDATE res_partner
        SET vat = identificacion
        WHERE (vat IS NULL OR vat = '')
          AND identificacion IS NOT NULL
          AND identificacion != ''
        """
    )
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["res.partner"].invalidate_cache()
