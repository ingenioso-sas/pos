# -*- coding: utf-8 -*-
# Copyright (C) 2025-Today: Ing.Factura S.L
# @author: Ing.Factura S.L
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    has_commission = fields.Boolean(
        string="Apply Commission",
        help="Check this box to apply a commission to payments made with this method."
    )
    commission_type = fields.Selection(
        [('fixed', 'Fixed'), ('percentage', 'Percentage')],
        string="Commission Type",
        default='percentage'
    )
    commission_rate = fields.Float(
        string="Commission Rate (%)",
        digits='Discount',
        help="The commission percentage to be applied to the payment amount."
    )
    commission_fixed_amount = fields.Monetary(
        string="Fixed Commission Amount",
        help="The fixed commission amount to be applied.",
        currency_field='company_currency_id',
    )
    company_currency_id = fields.Many2one(
        'res.currency',
        string="Company Currency",
        related='company_id.currency_id',
        readonly=True,
    )
    commission_account_id = fields.Many2one(
        'account.account',
        string="Commission Expense Account",
        domain=[('user_type_id.type', '=', 'other'), ('deprecated', '=', False)],
        help="The account where the commission expense will be recorded."
    )

    @api.constrains('commission_rate')
    def _check_commission_rate(self):
        for record in self:
            if record.commission_type == 'percentage' and (record.commission_rate < 0 or record.commission_rate > 100):
                raise ValidationError(_("Commission rate must be between 0 and 100."))