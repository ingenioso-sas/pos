# -*- coding: utf-8 -*-
import logging

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _validate_session(self):
        res = super(PosSession, self)._validate_session()
        # move_id ya publicado: se pueden crear/eliminar parciales.
        # Best-effort (nunca revienta el cierre).
        for session in self:
            try:
                session._settle_advance_partners()
            except Exception as e:
                _logger.warning(
                    'Conciliación de anticipos omitida en sesión %s: %s',
                    session.name, e,
                )
        return res

    def _settle_advance_partners(self):
        """Liquida por socio comercial el consumo de Saldo a Favor.

        El cierre nativo empareja espejo↔factura por el total, asumiendo
        fondos. Para el tramo fiado eso marcaría pagada una factura abierta.
        Aquí se recompone exacto: intermediario↔créditos (fondeado),
        espejo↔intermediario (fiado) y espejo↔factura (resto), quedando la
        factura abierta por el descubierto y cero fantasmas.
        """
        self.ensure_one()
        if self.state != 'closed' or not self.move_id:
            return
        groups = {}
        refunds = {}
        for order in self.order_ids.filtered(
                lambda o: o.partner_id and not o.is_advance_deposit
                and o.payment_ids.filtered(
                    lambda p: p.payment_method_id.is_advance_payment)):
            commercial = order.partner_id.commercial_partner_id
            # Las devoluciones (total negativo) van a rama propia: sus
            # líneas son el espejo exacto de la venta y no entran en la
            # cirugía de fondeado/descubierto.
            bucket = refunds if (order.amount_total or 0.0) < -0.001 \
                else groups
            bucket.setdefault(commercial.id, {
                'partner': commercial, 'orders': self.env['pos.order']})
            bucket[commercial.id]['orders'] |= order
        for info in groups.values():
            try:
                self._settle_advance_partner(
                    info['partner'], info['orders'])
            except Exception as e:
                _logger.warning(
                    'Socio %s excluido del pareo (%s); lo verá contabilidad.',
                    info['partner'].display_name, e,
                )
        for info in refunds.values():
            try:
                self._settle_advance_refund(
                    info['partner'], info['orders'])
            except Exception as e:
                _logger.warning(
                    'Reembolso %s excluido del pareo (%s).',
                    info['partner'].display_name, e,
                )
        # 2805 de depósitos: pareo FIFO global (ventas sin partner).
        try:
            advance = self.company_id.pos_advance_account_id
            if advance:
                self._pair_account_lines(advance)
        except Exception as e:
            _logger.warning('Pareo 2805 omitido: %s', e)

    def _settle_advance_partner(self, commercial, orders):
        rxc = commercial.property_account_receivable_id
        if not rxc:
            raise UserError(_('Sin CxC para %s') % commercial.display_name)
        partners = commercial | commercial.child_ids
        MoveLine = self.env['account.move.line']

        advance_methods = self.env['pos.payment.method'].search(
            [('is_advance_payment', '=', True)])
        method_names = advance_methods.mapped('name')

        tendered = 0.0
        for order in orders:
            tendered += sum(order.payment_ids.filtered(
                lambda p: p.payment_method_id.is_advance_payment
            ).mapped('amount'))

        invoices = orders.mapped('account_move').filtered(
            lambda m: m and m.type == 'out_invoice' and m.state == 'posted')

        def fresh(ids):
            return MoveLine.browse(ids).exists()

        # 1) Intermediario (split, con partner) ↔ créditos viejos.
        inter = self._split_debits(rxc, partners, method_names)
        olds = self._old_credits(rxc, partners)
        funded = self._pair_lines(inter, olds)
        overdraft = tendered - funded

        if not invoices:
            # Sin factura (legado): el fiado queda como débito abierto con
            # partner, visible y atribuible. Nada más que hacer.
            _logger.info('Saldo %s sin factura: digitado %s, fondeado %s.',
                         commercial.display_name, tendered, funded)
            return

        # 2) Si hay pagos manuales pre-cierre sobre estas facturas, no se
        # toca el pareo nativo (ya es correcto con fondos reales). OJO: el
        # espejo de ESTE cierre no cuenta como manual (se filtra abajo), y
        # tampoco las notas crédito de devolución (su remanente es crédito
        # nuevo legítimo, no fondos).
        mirror_ids = MoveLine.search([
            ('move_id', '=', self.move_id.id),
            ('account_id', '=', rxc.id),
            ('partner_id', '=', commercial.id),
            ('credit', '>', 0.0),
        ]).ids
        dirty = self.env['account.partial.reconcile'].search([
            ('debit_move_id.move_id', 'in', invoices.ids),
            ('debit_move_id.account_id', '=', rxc.id),
            ('credit_move_id', 'not in', mirror_ids),
            ('credit_move_id.move_id.type', '!=', 'out_refund'),
        ])
        if dirty:
            _logger.info(
                'Socio %s con pagos manuales; se conserva pareo nativo.',
                commercial.display_name)
            return

        if overdraft <= 0.001:
            return  # Nativo correcto: todo fondeado.

        # 3) Desemparejar espejo↔factura por el descubierto y reasignar el
        # espejo al intermediario. Se refresca todo tras el unlink.
        mirror = MoveLine.search([
            ('move_id', '=', self.move_id.id),
            ('account_id', '=', rxc.id),
            ('partner_id', '=', commercial.id),
            ('credit', '>', 0.0),
        ])
        linked = self.env['account.partial.reconcile'].search([
            ('credit_move_id', 'in', mirror.ids),
            ('debit_move_id.move_id', 'in', invoices.ids),
        ])
        if not linked:
            _logger.warning('Sin pareo espejo↔factura para %s; revisión.',
                            commercial.display_name)
            return
        (linked.mapped('debit_move_id')
         | linked.mapped('credit_move_id')).remove_move_reconcile()
        mirror = fresh(mirror.ids).filtered(lambda l: not l.reconciled)
        inter = fresh(inter.ids).filtered(lambda l: not l.reconciled)
        # Espejo ↔ intermediario por el descubierto.
        self._pair_amount(mirror, inter, overdraft)
        # Espejo restante ↔ facturas (antiguas primero: el fiado queda en
        # las nuevas, que conservan su residual abierto).
        mirror = fresh(mirror.ids).filtered(lambda l: not l.reconciled)
        for inv in invoices.sorted('date'):
            open_lines = fresh(inv.line_ids.ids).filtered(
                lambda l: l.account_id == rxc and not l.reconciled
                and l.debit > 0.0)
            if open_lines:
                self._pair_amount(
                    mirror.filtered(lambda l: not l.reconciled),
                    open_lines,
                    sum(open_lines.mapped('amount_residual')))
        _logger.info(
            'Saldo liquidado %s: digitado %s, fondeado %s, fiado %s.',
            commercial.display_name, tendered, funded, overdraft)

    # ---- helpers ----
    def _settle_advance_refund(self, commercial, refund_orders):
        """Pareo de sobrantes de devolución: espejo-Dr ('From invoiced
        orders') ↔ inter-Cr (nombre del método) del mismo asiento, hasta el
        total devuelto. La RINV↔factura y la restauración ya ocurrieron en el
        hook; si no (sin original), esto al menos netea la sesión."""
        rxc = commercial.property_account_receivable_id
        if not rxc:
            return
        partners = commercial | commercial.child_ids
        total = sum(-(o.amount_total or 0.0) for o in refund_orders)
        if total <= 0.001:
            return
        # El cierre nativo puede haber emparejado la RINV de la devolución
        # contra el Dr del propio asiento de sesión, cerrando la RINV y
        # dejando el Cr del método huérfano: el saldo queda invisible (ni
        # pagos ni notas lo ven). Se deshace ese pareo para que el crédito
        # vivo quede en la RINV y la sesión netee a cero.
        for refund in refund_orders:
            rinv = refund.account_move
            if not rinv or rinv.type != 'out_refund' \
                    or rinv.state != 'posted':
                continue
            bad = self.env['account.partial.reconcile'].search([
                ('debit_move_id.move_id', '=', self.move_id.id),
                ('credit_move_id.move_id', '=', rinv.id),
            ]) | self.env['account.partial.reconcile'].search([
                ('debit_move_id.move_id', '=', rinv.id),
                ('credit_move_id.move_id', '=', self.move_id.id),
            ])
            bad = bad.filtered(
                lambda p: p.debit_move_id.account_id == rxc
                and p.credit_move_id.account_id == rxc)
            if bad:
                (bad.mapped('debit_move_id')
                 | bad.mapped('credit_move_id')).remove_move_reconcile()
                _logger.info(
                    'Reembolso %s: deshecho pareo RINV↔sesión (%s); '
                    'el crédito vuelve a la nota.',
                    refund.name, bad.ids)
        method_names = self.env['pos.payment.method'].search(
            [('is_advance_payment', '=', True)]).mapped('name')
        MoveLine = self.env['account.move.line']
        debits = MoveLine.search([
            ('move_id', '=', self.move_id.id),
            ('account_id', '=', rxc.id),
            ('reconciled', '=', False),
            ('debit', '>', 0.0),
            ('partner_id', '=', commercial.id),
            ('name', '=', 'From invoiced orders'),
        ])
        credits = MoveLine.search([
            ('move_id', '=', self.move_id.id),
            ('account_id', '=', rxc.id),
            ('reconciled', '=', False),
            ('credit', '>', 0.0),
            ('partner_id', 'in', partners.ids),
        ])
        if method_names:
            credits = credits.filtered(
                lambda l: any(n in (l.name or '') for n in method_names))
        paired = self._pair_amount(credits, debits, total)
        _logger.info('Reembolso %s: neto de sesión %s de %s.',
                     commercial.display_name, paired, total)

    def _split_debits(self, account, partners, method_names):
        lines = self.env['account.move.line'].search([
            ('move_id', '=', self.move_id.id),
            ('account_id', '=', account.id),
            ('reconciled', '=', False),
            ('debit', '>', 0.0),
            ('partner_id', 'in', partners.ids),
        ])
        if method_names:
            named = lines.filtered(
                lambda l: any(n in (l.name or '') for n in method_names))
            return named or lines
        return lines

    def _old_credits(self, account, partners):
        return self.env['account.move.line'].search([
            ('account_id', '=', account.id),
            ('partner_id', 'in', partners.ids),
            ('reconciled', '=', False),
            ('move_id.state', '=', 'posted'),
            ('move_id', '!=', self.move_id.id),
            ('credit', '>', 0.0),
        ], order='date asc, id asc')

    def _pair_lines(self, debits, credits):
        """Pareo FIFO total; devuelve monto fondeado."""
        funded = 0.0
        Partial = self.env['account.partial.reconcile']
        for debit in debits.sorted('date'):
            remaining = debit.amount_residual
            if remaining <= 0.001 or debit.reconciled:
                continue
            for credit in credits.sorted('date'):
                if remaining <= 0.001:
                    break
                if credit.reconciled:
                    continue
                avail = abs(credit.amount_residual)
                if avail <= 0.001:
                    continue
                amount = min(remaining, avail)
                try:
                    Partial.create({
                        'debit_move_id': debit.id,
                        'credit_move_id': credit.id,
                        'amount': amount,
                    })
                    funded += amount
                    remaining -= amount
                except Exception as e:
                    _logger.warning('Pareo omitido Dr %s Cr %s: %s',
                                    debit.id, credit.id, e)
        return funded

    def _pair_amount(self, credits, debits, amount):
        """Parea hasta `amount` entre conjuntos (FIFO por fecha)."""
        if amount <= 0.001:
            return 0.0
        paired = 0.0
        Partial = self.env['account.partial.reconcile']
        for debit in debits.sorted('date'):
            if paired >= amount - 0.001:
                break
            need = amount - paired
            remaining = min(debit.amount_residual, need)
            if remaining <= 0.001 or debit.reconciled:
                continue
            for credit in credits.sorted('date'):
                if remaining <= 0.001:
                    break
                if credit.reconciled:
                    continue
                avail = abs(credit.amount_residual)
                if avail <= 0.001:
                    continue
                take = min(remaining, avail)
                try:
                    Partial.create({
                        'debit_move_id': debit.id,
                        'credit_move_id': credit.id,
                        'amount': take,
                    })
                    paired += take
                    remaining -= take
                except Exception as e:
                    _logger.warning('Pareo omitido Dr %s Cr %s: %s',
                                    debit.id, credit.id, e)
        return paired

    def _pair_account_lines(self, account):
        """Pareo FIFO global en una cuenta de clearing (2805)."""
        lines = self.env['account.move.line'].search([
            ('account_id', '=', account.id),
            ('reconciled', '=', False),
            ('move_id.state', '=', 'posted'),
        ], order='date asc, id asc')
        self._pair_lines(
            lines.filtered(lambda l: l.amount_residual > 0.001),
            lines.filtered(lambda l: l.amount_residual < -0.001))
