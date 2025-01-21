from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    show_client_signature = fields.Boolean(string="Show customer signature")
    # location_only = fields.Boolean(string='Only in POS Location')
    # allow_out_of_stock = fields.Boolean(string='Allow Out-of-Stock')
    # limit_qty = fields.Integer(string='Deny Order when Quantity Available lower than')
    # location_id = fields.Many2one('stock.location')
