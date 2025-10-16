from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_require_customer_id = fields.Boolean(
        related='company_id.pos_require_customer_id',
        readonly=False
    )
