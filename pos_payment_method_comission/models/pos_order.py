# -*- coding: utf-8 -*-
# Copyright (C) 2025-Today: Ing.Factura S.L
# @author: Ing.Factura S.L
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import logging

from odoo import api, models, _

_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    _inherit = "pos.order"

    def _payment_fields(self, order, ui_paymentline):
        fields = super(PosOrder, self)._payment_fields(order, ui_paymentline)
        fields['commission'] = ui_paymentline.get('commission', 0.0)
        fields['approval_reference'] = ui_paymentline.get('approval_reference', '')
        return fields

    @api.model
    def _process_order(self, order, draft, existing_order):
        order_id = super(PosOrder, self)._process_order(order, draft, existing_order)
        order_rec = self.browse(order_id)
        self._create_commission_moves(order_rec)
        return order_id

    def _create_commission_moves(self, order):
        for payment in order.payment_ids:
            if payment.payment_method_id.has_commission and payment.commission != 0:
                try:
                    commission_move = self._prepare_commission_move(payment)
                    commission_move.post()
                except Exception:
                    _logger.error(
                        "Failed to create commission move for payment %s (order: %s)",
                        payment.id, order.name
                    )
                    raise

    def _prepare_commission_move(self, payment):
        payment_method = payment.payment_method_id
        commission_account = payment_method.commission_account_id
        commission = payment.commission

        # The move should be created in the company's currency
        src_currency = payment.pos_order_id.pricelist_id.currency_id or payment.pos_order_id.company_id.currency_id
        amount_in_company_currency = src_currency._convert(
            commission,
            payment.pos_order_id.company_id.currency_id,
            payment.pos_order_id.company_id,
            payment.pos_order_id.date_order,
        )

        ref_str = _('Commission: %s') % payment.pos_order_id.name
        if payment.approval_reference:
            ref_str += _(' (Ref: %s)') % payment.approval_reference

        move_lines = []

        if payment_method.commission_tax_ids:
            taxes = payment_method.commission_tax_ids.compute_all(
                amount_in_company_currency,
                payment.pos_order_id.company_id.currency_id,
                1.0,
                product=None,
                partner=payment.pos_order_id.partner_id
            )
            total_expense = taxes['total_excluded']
            total_receivable = taxes['total_included']

            # Base expense line
            move_lines.append((0, 0, {
                'name': ref_str,
                'account_id': commission_account.id,
                'debit': total_expense if total_expense > 0 else 0,
                'credit': -total_expense if total_expense < 0 else 0,
            }))

            # Tax lines
            for tax_res in taxes['taxes']:
                tax_amount = tax_res['amount']
                tax_account_id = tax_res.get('account_id') or commission_account.id
                move_lines.append((0, 0, {
                    'name': tax_res['name'],
                    'account_id': tax_account_id,
                    'debit': tax_amount if tax_amount > 0 else 0,
                    'credit': -tax_amount if tax_amount < 0 else 0,
                }))
        else:
            total_receivable = amount_in_company_currency
            move_lines.append((0, 0, {
                'name': ref_str,
                'account_id': commission_account.id,
                'debit': amount_in_company_currency if amount_in_company_currency > 0 else 0,
                'credit': -amount_in_company_currency if amount_in_company_currency < 0 else 0,
            }))

        # Credit the payment method's outstanding account
        move_lines.append((0, 0, {
            'name': ref_str,
            'account_id': payment.payment_method_id.receivable_account_id.id,
            'credit': total_receivable if total_receivable > 0 else 0,
            'debit': -total_receivable if total_receivable < 0 else 0,
        }))

        return self.env['account.move'].create({
            'journal_id': payment_method.commission_journal_id.id,
            'date': payment.pos_order_id.date_order,
            'ref': ref_str,
            'line_ids': move_lines,
        })
