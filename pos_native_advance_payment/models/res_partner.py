# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    pos_advance_balance = fields.Float(
        string="Saldo a Favor",
        compute="_compute_advance_amounts",
        help="Pagos de cliente sin conciliar + remanentes de notas crédito, "
             "publicados. Incluye TPV y Facturación."
    )

    advance_credit_used = fields.Float(
        string="Crédito en Uso",
        compute="_compute_advance_amounts",
        help="Residual abierto de facturas nacidas de ventas TPV con Saldo a "
             "Favor. Reduce el disponible."
    )

    advance_available = fields.Float(
        string="Disponible (Saldo + Cupo − Uso)",
        compute="_compute_advance_amounts",
        help="Monto accionable en TPV: saldo + cupo − crédito en uso."
    )

    advance_credit_remaining = fields.Float(
        string="Crédito Disponible (Cupo − Uso)",
        compute="_compute_advance_amounts",
        help="Cupo libre del cliente, sin contar el saldo a favor."
    )

    advance_payment_allowed = fields.Boolean(
        string="Permite Saldo a Favor en TPV",
        default=True,
        help="Si está marcado, el cliente puede usar su saldo a favor como método de pago en el TPV."
    )

    advance_overdraft_limit = fields.Float(
        string="Límite de Sobregiro / Cupo Crédito (Saldo a Favor)",
        default=0.0,
        help="Cupo de crédito para vender con Saldo a Favor sin saldo. "
             "0 = usa el valor por defecto de la compañía; 0 en ambos = "
             "contado estricto (sin crédito). Lo usado se descuenta de "
             "facturas de saldo aún abiertas."
    )

    def _get_unreconciled_advance_payments(self):
        """Devuelve los account.payment de cliente (inbound, posted) con residual > 0.

        Fuente del saldo a favor: incluye pagos creados desde TPV
        (depósitos) y desde Facturación. Un pago parcialmente aplicado aporta
        solo su residual, no el total original.
        """
        self.ensure_one()
        Payment = self.env['account.payment']
        payments = Payment.search([
            ('partner_id', '=', self.id),
            ('payment_type', '=', 'inbound'),
            ('partner_type', '=', 'customer'),
            ('state', '=', 'posted'),
        ])
        result = []
        for payment in payments:
            try:
                residual = payment._get_advance_residual()
            except Exception:
                try:
                    residual = self._get_payment_residual_fallback(payment)
                except Exception as e:
                    _logger.warning(
                        'No se pudo calcular residual del pago %s: %s',
                        payment.id, e,
                    )
                    residual = 0.0
            if residual > 0.001:
                result.append((payment, residual))
        return result

    def _get_unreconciled_credit_notes(self):
        """Créditos de notas (out_refund publicadas, residual abierto).

        Una devolución cuyo remanente no cerró factura queda aquí como
        crédito nuevo y gastable, igual que un pago.
        """
        self.ensure_one()
        moves = self.env['account.move'].search([
            ('partner_id', '=', self.id),
            ('type', '=', 'out_refund'),
            ('state', '=', 'posted'),
            ('amount_residual', '>', 0.001),
        ])
        return moves

    def _get_advance_outstanding_lines(self):
        """Líneas CxC sin conciliar aplicables como saldo a favor.

        Fuente única para TPV, wizard y reportes: incluye tanto líneas
        de pagos (account.payment) como de notas crédito (out_refund).
        Ambas son créditos en la misma CxC y se aplican con el mecanismo
        estándar (js_assign_outstanding_line / partial.reconcile).
        """
        self.ensure_one()
        receivable = self.property_account_receivable_id
        if not receivable:
            return self.env['account.move.line'].browse()
        return self.env['account.move.line'].search([
            ('partner_id', '=', self.id),
            ('account_id', '=', receivable.id),
            ('reconciled', '=', False),
            ('move_id.state', '=', 'posted'),
            ('credit', '>', 0.0),
        ])

    def _get_payment_residual_fallback(self, payment):
        """Residual del pago vía líneas a cobrar no conciliadas de su asiento."""
        receivable = self.property_account_receivable_id
        MoveLine = self.env['account.move.line']
        domain = [
            ('partner_id', '=', self.id),
            ('reconciled', '=', False),
            ('move_id.state', '=', 'posted'),
        ]
        if 'payment_id' in MoveLine._fields:
            lines = MoveLine.search(domain + [
                ('payment_id', '=', payment.id),
                ('account_id', '=', receivable.id),
            ])
        else:  # Odoo 13 sin payment_id en línea: localizar por asiento del pago
            move = False
            if getattr(payment, 'move_name', False):
                move = self.env['account.move'].search(
                    [('name', '=', payment.move_name)], limit=1)
            if not move:
                # Sin rastro contable: pago sin aplicar = disponible total
                if not payment.invoice_ids:
                    return payment.amount
                return 0.0
            lines = MoveLine.search(domain + [
                ('move_id', '=', move.id),
                ('account_id', '=', receivable.id),
            ])
        # Líneas de crédito (pagos) tienen residual negativo en Odoo.
        return sum(-line.amount_residual for line in lines
                   if line.amount_residual < 0.0)

    def _get_effective_overdraft(self):
        """Cupo de crédito: individual o, si es 0, el de la compañía."""
        self.ensure_one()
        company = self.company_id or self.env.company
        return (self.advance_overdraft_limit or 0.0) or \
            (company.advance_overdraft_limit or 0.0)

    def _compute_advance_amounts(self):
        for partner in self:
            total = 0.0
            try:
                for _payment, residual in partner._get_unreconciled_advance_payments():
                    total += residual
                for note in partner._get_unreconciled_credit_notes():
                    total += note.amount_residual
            except Exception as e:
                _logger.warning(
                    'Error calculando saldo a favor de %s: %s',
                    partner.display_name, e,
                )
                total = 0.0
            partner.pos_advance_balance = total
            try:
                used = self.env['pos.order']._get_advance_credit_used(partner)
            except Exception as e:
                _logger.warning(
                    'Error calculando crédito en uso de %s: %s',
                    partner.display_name, e,
                )
                used = 0.0
            partner.advance_credit_used = used
            try:
                overdraft = partner._get_effective_overdraft()
            except Exception:
                overdraft = 0.0
            partner.advance_available = total + overdraft - used
            partner.advance_credit_remaining = overdraft - used

    def action_pos_advance_history(self):
        """Abrir líneas CxC sin conciliar (pagos + notas crédito)."""
        self.ensure_one()
        lines = self._get_advance_outstanding_lines()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Saldo a Favor sin conciliar - %s') % self.display_name,
            'view_mode': 'tree,form',
            'res_model': 'account.move.line',
            'domain': [('id', 'in', lines.ids)] if lines else [('id', '=', False)],
            'context': {
                'default_partner_id': self.id,
            },
        }
