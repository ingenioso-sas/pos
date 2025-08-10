# -*- coding: utf-8 -*-
# Copyright (C) 2025-Today: Ing.Factura S.L
# @author: Ing.Factura S.L
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, models, _

class PosOrder(models.Model):
    _inherit = "pos.order"

    def _payment_fields(self, order, ui_paymentline):
        fields = super(PosOrder, self)._payment_fields(order, ui_paymentline)
        fields['commission'] = ui_paymentline.get('commission', 0.0)
        return fields

    @api.model
    def _process_order(self, order, draft, existing_order):
        order_id = super(PosOrder, self)._process_order(order, draft, existing_order)
        order_rec = self.browse(order_id)
        self._create_commission_moves(order_rec)
        return order_id

    def _create_commission_moves(self, order):
        for payment in order.payment_ids:
            if payment.payment_method_id.has_commission and payment.commission > 0:
                commission_move = self._prepare_commission_move(payment)
                commission_move.post()

    def _prepare_commission_move(self, payment):
        payment_method = payment.payment_method_id
        commission_account = payment_method.commission_account_id
        commission = payment.commission

        # The move should be created in the company's currency
        amount_in_company_currency = payment.pos_order_id.pricelist_id.currency_id._convert(
            commission,
            payment.pos_order_id.company_id.currency_id,
            payment.pos_order_id.company_id,
            payment.pos_order_id.date_order,
        )

        return self.env['account.move'].create({
            'journal_id': payment_method.commission_journal_id.id,
            'date': payment.pos_order_id.date_order,
            'ref': _('Commission: %s') % payment.pos_order_id.name,
            'line_ids': [
                # Credit the payment method's outstanding account
                (0, 0, {
                    'name': _('Commission for %s') % payment.pos_order_id.name,
                    'account_id': payment.payment_method_id.receivable_account_id.id,
                    'credit': amount_in_company_currency,
                    'debit': 0,
                }),
                # Debit the commission expense account
                (0, 0, {
                    'name': _('Commission for %s') % payment.pos_order_id.name,
                    'account_id': commission_account.id,
                    'debit': amount_in_company_currency,
                    'credit': 0,
                }),
            ],
        })
