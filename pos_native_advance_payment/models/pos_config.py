# -*- coding: utf-8 -*-
from odoo import fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    pos_deposit_product_id = fields.Many2one(
        'product.template',
        related='company_id.pos_deposit_product_id',
        string="Producto Auxiliar de Depósito (TPV)",
        readonly=True,
    )
