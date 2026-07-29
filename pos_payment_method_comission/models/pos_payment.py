# -*- coding: utf-8 -*-
# Copyright (C) 2025-Today: Ing.Factura S.L
# @author: Ing.Factura S.L
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class PosPayment(models.Model):
    _inherit = "pos.payment"

    commission = fields.Float(string="Commission", digits='Account', readonly=True)
    approval_reference = fields.Char(string="Referencia de Aprobación")
