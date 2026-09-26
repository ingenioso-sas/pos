# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    is_pos_advance = fields.Boolean(
        string="Anticipo desde TPV",
        default=False,
        help="Marcado cuando el pago se originó como depósito en el TPV.",
    )
    pos_order_id = fields.Many2one(
        'pos.order', string="Pedido TPV origen",
        help="Pedido de depósito del TPV que originó este pago.",
    )

    def _get_advance_residual(self):
        """Residual disponible del pago para usar como saldo a favor.

        Suma -amount_residual de sus líneas a cobrar no conciliadas.
        Si el pago ya está aplicado a facturas, el residual baja solo.
        """
        self.ensure_one()
        if self.state != 'posted' or self.payment_type != 'inbound':
            return 0.0
        MoveLine = self.env['account.move.line']
        domain = [
            ('partner_id', '=', self.partner_id.id),
            ('reconciled', '=', False),
            ('move_id.state', '=', 'posted'),
        ]
        receivable = self.destination_account_id or \
            self.partner_id.property_account_receivable_id
        if 'payment_id' in MoveLine._fields:
            lines = MoveLine.search(domain + [
                ('payment_id', '=', self.id),
                ('account_id', '=', receivable.id),
            ])
            if lines:
                return sum(-l.amount_residual for l in lines
                           if l.amount_residual < 0.0)
        # Fallback Odoo 13: localizar asiento por move_name.
        move = False
        if getattr(self, 'move_name', False):
            move = self.env['account.move'].search(
                [('name', '=', self.move_name)], limit=1)
        if not move:
            return 0.0 if self.invoice_ids else self.amount
        lines = MoveLine.search(domain + [
            ('move_id', '=', move.id),
            ('account_id', '=', receivable.id),
        ])
        return sum(-l.amount_residual for l in lines
                   if l.amount_residual < 0.0)

    @api.model
    def create_pos_advance_payment(self, partner, amount, journal,
                                   communication='', pos_order=None):
        """Crea el account.payment de un depósito TPV sin duplicar caja.

        CONFLICTO DE DOBLE CAJA (resuelto): el efectivo ya lo registra el
        pos.order/pos.payment en el extracto de la sesión. Por eso este pago
        usa un diario de clearing (banco con cuentas por defecto = cuenta de
        anticipos 2805): su asiento es Dr Anticipos / Cr Cuentas por cobrar,
        sin tocar efectivo. El neto global queda Dr Caja (TPV) / Cr CxC,
        y el crédito en CxC sí es aplicable a facturas con el widget estándar.
        """
        if amount <= 0.0:
            raise UserError(_("El monto del anticipo debe ser positivo."))
        if journal.type == 'cash':
            raise UserError(_(
                "El diario de anticipos '%s' no puede ser de efectivo: "
                "duplicaría la caja (el efectivo ya queda en la sesión TPV). "
                "Use un diario banco con cuentas por defecto = %s."
            ) % (journal.name,
                 partner.company_id.pos_advance_account_id.display_name
                 if partner.company_id.pos_advance_account_id else '2805'))
        receivable = partner.property_account_receivable_id
        if not receivable:
            raise UserError(_(
                "El cliente %s no tiene cuenta por cobrar configurada.")
                % partner.display_name)
        method = self.env['account.payment.method'].search([
            ('payment_type', '=', 'inbound'),
            ('code', '=', 'manual'),
        ], limit=1)
        if not method:
            raise UserError(_("No hay método de pago manual de entrada."))
        vals = {
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': partner.id,
            'amount': amount,
            'journal_id': journal.id,
            'payment_method_id': method.id,
            # Sin destination_account_id: en v13 es calculado readonly y el
            # destino cae a la CxC del partner por _compute_destination.
            'communication': communication,
            'is_pos_advance': True,
        }
        if pos_order:
            vals['pos_order_id'] = pos_order.id
        payment = self.create(vals)
        payment.post()
        return payment
