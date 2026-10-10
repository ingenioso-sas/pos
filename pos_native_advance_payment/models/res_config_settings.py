# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_advance_account_id = fields.Many2one(
        related='company_id.pos_advance_account_id',
        readonly=False,
        string="Cuenta de Anticipos para TPV"
    )

    advance_overdraft_limit = fields.Float(
        related='company_id.advance_overdraft_limit',
        readonly=False,
        string="Límite de Sobregiro por Defecto"
    )

    pos_deposit_product_id = fields.Many2one(
        related='company_id.pos_deposit_product_id',
        readonly=False,
        string="Producto Auxiliar de Depósito (TPV)",
    )

    pos_advance_journal_id = fields.Many2one(
        related='company_id.pos_advance_journal_id',
        readonly=False,
        string="Diario Clearing de Anticipos",
    )

    def set_values(self):
        super().set_values()
        for rec in self:
            if rec.company_id:
                rec.company_id._sync_deposit_product_income()
