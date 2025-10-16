from odoo import fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    pos_require_customer_id = fields.Boolean(
        related='company_id.pos_require_customer_id',
        readonly=True
    )

    def _get_pos_ui_pos_config(self, params):
        result = super()._get_pos_ui_pos_config(params)
        result['pos_require_customer_id'] = self.pos_require_customer_id
        return result
