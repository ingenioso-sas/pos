# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PayAdvanceWizard(models.TransientModel):
    _name = 'pay.advance.wizard'
    _description = 'Pagar Facturas con Saldo a Favor'

    partner_id = fields.Many2one('res.partner', string='Cliente', required=True)
    advance_balance = fields.Float(string='Saldo a Favor Disponible',
                                   compute='_compute_advance_balance')
    total_selected = fields.Float(string='Total Seleccionado',
                                  compute='_compute_total_selected')
    company_id = fields.Many2one('res.company', string='Compañía',
                                 default=lambda self: self.env.company)
    invoice_ids = fields.Many2many(
        'account.move', string='Facturas por Pagar',
        domain=[('type', '=', 'out_invoice'),
                ('state', '=', 'posted')])
    payment_ids = fields.Many2many(
        'account.payment', string='Pagos sin conciliar',
        compute='_compute_payment_ids')
    credit_note_ids = fields.Many2many(
        'account.move', string='Notas crédito sin conciliar',
        compute='_compute_credit_note_ids',
        domain=[('type', '=', 'out_refund'),
                ('state', '=', 'posted')])

    @api.model
    def _pos_order_names(self):
        """Nombres de pedidos TPV (para excluir sus facturas: el cierre las
        concilia solo; un pago manual intermedio descuadraría el reparto)."""
        orders = self.env['pos.order'].search([('partner_id', '!=', False)])
        return [o.name for o in orders if o.payment_ids.filtered(
            lambda p: p.payment_method_id.is_advance_payment)]

    def _compute_advance_balance(self):
        for wiz in self:
            if wiz.partner_id:
                wiz.advance_balance = wiz.partner_id.pos_advance_balance
            else:
                wiz.advance_balance = 0.0

    def _compute_total_selected(self):
        for wiz in self:
            wiz.total_selected = sum(wiz.invoice_ids.mapped('amount_residual'))

    @api.depends('partner_id')
    def _compute_payment_ids(self):
        Payment = self.env['account.payment']
        for wiz in self:
            if not wiz.partner_id:
                wiz.payment_ids = False
                continue
            unreconciled = wiz.partner_id._get_unreconciled_advance_payments()
            wiz.payment_ids = [(6, 0, [p.id for p, _r in unreconciled])]

    @api.depends('partner_id')
    def _compute_credit_note_ids(self):
        for wiz in self:
            if not wiz.partner_id:
                wiz.credit_note_ids = False
                continue
            notes = wiz.partner_id._get_unreconciled_credit_notes()
            wiz.credit_note_ids = [(6, 0, notes.ids)]

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if not self.partner_id:
            self.invoice_ids = False
            return
        excluded = self._pos_order_names()
        domain = [
            ('partner_id', '=', self.partner_id.id),
            ('type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('invoice_payment_state', '!=', 'paid'),
        ]
        if excluded:
            domain.append(('invoice_origin', 'not in', excluded))
        self.invoice_ids = self.env['account.move'].search(domain)

    def action_pay(self):
        """Aplica pagos y notas crédito al saldo mediante el mecanismo
        estándar de facturas.

        Usa invoice.js_assign_outstanding_line() (misma cuenta CxC), en lugar
        del anterior partial.reconcile cruzado 2805<->CxC que Odoo rechaza
        por ser cuentas distintas. Pagos y notas son líneas Cr en la misma
        CxC, por eso comparten el mismo mecanismo.
        """
        self.ensure_one()
        if not self.invoice_ids:
            raise UserError(_("Seleccione al menos una factura para pagar."))
        unreconciled = self.partner_id._get_unreconciled_advance_payments()
        notes = self.partner_id._get_unreconciled_credit_notes()
        if not unreconciled and not notes:
            raise UserError(_("El cliente no tiene saldo a favor sin conciliar."))
        available = sum(r for _p, r in unreconciled) + \
            sum(n.amount_residual for n in notes)
        total = sum(self.invoice_ids.mapped('amount_residual'))
        if total - available > 0.001:
            raise UserError(_(
                "El total pendiente (%s) excede el saldo a favor (%s)."
            ) % (total, available))

        MoveLine = self.env['account.move.line']
        payment_lines = MoveLine.browse()
        for payment, _res in unreconciled:
            domain = [
                ('partner_id', '=', self.partner_id.id),
                ('reconciled', '=', False),
                ('move_id.state', '=', 'posted'),
                ('credit', '>', 0.0),
            ]
            if 'payment_id' in MoveLine._fields:
                domain.append(('payment_id', '=', payment.id))
            elif getattr(payment, 'move_name', False):
                move = self.env['account.move'].search(
                    [('name', '=', payment.move_name)], limit=1)
                if move:
                    domain.append(('move_id', '=', move.id))
            payment_lines |= MoveLine.search(domain)
        # Remanentes de devoluciones: líneas Cr de out_refund en la misma CxC.
        if notes:
            receivable = self.partner_id.property_account_receivable_id
            note_lines = MoveLine.search([
                ('move_id', 'in', notes.ids),
                ('account_id', '=', receivable.id),
                ('reconciled', '=', False),
                ('credit', '>', 0.0),
            ])
            payment_lines |= note_lines

        applied = 0
        errors = []
        for invoice in self.invoice_ids.sorted('invoice_date'):
            if invoice.invoice_payment_state == 'paid':
                continue
            for pline in payment_lines.filtered(lambda l: not l.reconciled):
                try:
                    # v13: js_assign_outstanding_line (soporta parciales).
                    invoice.js_assign_outstanding_line(pline.id)
                    applied += 1
                    break
                except Exception as e:
                    errors.append('%s: %s' % (invoice.name, e))
                    continue
        if applied:
            return {'type': 'ir.actions.client', 'tag': 'reload'}
        raise UserError(
            _("No se pudo aplicar ningún pago.") + ('\n%s' % '\n'.join(errors[:3]) if errors else ''))
