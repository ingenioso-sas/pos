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

    pos_advance_suggest = fields.Boolean(
        string="Sugerir Saldo a Favor en Pago",
        default=False,
        help="Si está marcado, al abrir la pantalla de pago con un "
             "cliente que tiene saldo disponible se muestra una alerta "
             "única por pedido para ofrecer pagar con saldo a favor.",
    )

    pos_advance_suggest_mode = fields.Selection(
        [('balance', 'Solo saldo real'),
         ('available', 'Saldo + cupo')],
        string="Monto Sugerido",
        default='balance',
        help="Saldo real usa solo el favor contabilizado; Saldo + cupo "
             "incluye el crédito autorizado y puede generar descubierto.",
    )
