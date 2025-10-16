from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    pos_require_customer_id = fields.Boolean(
        string="Requerir identificación del cliente para ventas en POS",
        help=(
            "Si se activa, el POS exigirá que el cliente tenga una"
            "identificación registrada antes de validar la venta."
        )
    )
