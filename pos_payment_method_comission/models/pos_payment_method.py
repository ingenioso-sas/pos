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
    commission_journal_id = fields.Many2one(
        'account.journal',
        string="Commission Journal",
        domain=[('type', '=', 'general')],
        help="El diario donde se registrarán los asientos contables de la comisión. "
             "Aunque el método de pago tenga un diario por defecto para cobrar el dinero (activo), "
             "este campo permite agrupar los gastos por comisiones en un diario específico (ej. Operaciones Varias) "
             "para no mezclar el registro del dinero recibido con el gasto bancario."
    )
    commission_account_id = fields.Many2one(
        'account.account',
        string="Commission Expense Account",
        domain=[('user_type_id.internal_group', '=', 'expense'), ('deprecated', '=', False)],
        help="La cuenta contable de GASTOS (ej. Gastos Bancarios) donde se debitará el valor de la comisión. "
             "Se requiere una cuenta separada porque la comisión es un gasto operativo para la empresa, "
             "y no debe debitarse de la cuenta de banco/caja que recibe el pago total."
    )
    commission_tax_ids = fields.Many2many(
        'account.tax',
        'pos_payment_method_commission_tax_rel',
        'payment_method_id', 'tax_id',
        string="Impuestos de la Comisión",
        domain=[('type_tax_use', '=', 'purchase')],
        help="Impuestos (IVA, Retenciones) a aplicar sobre la comisión base."
    )
    payment_withholding_tax_ids = fields.Many2many(
        'account.tax',
        'pos_payment_method_withholding_tax_rel',
        'payment_method_id', 'tax_id',
        string="Retenciones sobre el Pago Total",
        domain=[('type_tax_use', '=', 'purchase')],
        help="Impuestos (ej. ReteRenta, ReteICA) que la pasarela retiene sobre el valor total de la venta (el pago)."
    )
    require_approval_reference = fields.Boolean(
        string="Pedir Referencia de Aprobación",
        help="Exige ingresar un número de aprobación (ej. voucher, crédito Addi) en el TPV."
    )
    reverse_commission_on_refund = fields.Boolean(
        string="Reversar Comisión en Devoluciones",
        help="Si está activo, la comisión se restará en devoluciones."
    )
    refund_policy = fields.Selection(
        [('real', 'Devolución Real Permitida'), ('wallet', 'Solo a Cartera / Saldo a Favor')],
        string="Política de Devolución",
        default='real',
        help="Define si este método permite devolver dinero en efectivo/pasarela o si obliga a devolver el saldo a la cartera del cliente."
    )

    @api.constrains('commission_rate')
    def _check_commission_rate(self):
        for record in self:
            if record.commission_rate < 0 or record.commission_rate > 100:
                raise ValidationError(_("Commission rate must be between 0 and 100."))

    @api.constrains('commission_fixed_amount')
    def _check_commission_fixed_amount(self):
        for record in self:
            if record.commission_fixed_amount < 0:
                raise ValidationError(
                    _("Fixed commission amount must be a positive value.")
                )