# -*- coding: utf-8 -*-
import logging

from odoo import _, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _validate_session(self):
        res = super(PosSession, self)._validate_session()
        # move_id ya publicado: se pueden crear/eliminar parciales.
        # La liquidación contable es parte del cierre: si falla, la excepción
        # revierte también el cierre nativo y la sesión queda reintentable.
        for session in self:
            session.with_context(
                force_company=session.company_id.id
            )._settle_advance_partners(raise_on_error=True)
        return res

    def reprocess_advance_settlement(self):
        """Re-ejecuta la liquidación sobre sesiones cerradas (idempotente).

        Permite reprocesar casos como POS/01303 sin reabrir la sesión: todos
        los pareos solo actúan sobre residuales abiertos, así que una segunda
        corrida no duplica parciales ni cambia residuales.
        """
        if not self.env.user.has_group('account.group_account_manager'):
            raise AccessError(_(
                'Solo un responsable contable puede reprocesar sesiones.'))
        for session in self:
            session.check_access_rule('read')
            if session.company_id not in self.env.user.company_ids:
                raise AccessError(_(
                    'No puede reprocesar una sesión de otra compañía.'))
            if session.state != 'closed' or not session.move_id:
                _logger.info(
                    'Sesión %s no cerrada o sin asiento; se omite reproceso.',
                    session.name)
                continue
            session.with_context(
                force_company=session.company_id.id
            )._settle_advance_partners(raise_on_error=True)
        return True

    def _log_settle_event(self, message, level='warning'):
        """Deja rastro persistente (ir.logging) además del syslog.

        Best-effort: jamás revienta el cierre.
        """
        try:
            self.env['ir.logging'].sudo().create({
                'name': 'pos_native_advance_payment',
                'type': 'server',
                'dbname': self._cr.dbname,
                'level': level.upper(),
                'message': message,
                'path': 'pos.session',
                'line': '0',
                'func': '_settle_advance_partners',
            })
        except Exception as e:
            _logger.warning('No se pudo persistir evento ir.logging: %s', e)

    def _settle_advance_partners(self, raise_on_error=False):
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
        self.env.cr.execute(
            'SELECT id FROM pos_session WHERE id = %s FOR UPDATE',
            [self.id])
        data = {}
        for order in self.order_ids.filtered(
                lambda o: o.partner_id and not o.is_advance_deposit
                and o.payment_ids.filtered(
                    lambda p: p.payment_method_id.is_advance_payment)):
            commercial = order.partner_id.commercial_partner_id
            # Las devoluciones (total negativo) van a rama propia: sus
            # líneas son el espejo exacto de la venta y no entran en la
            # cirugía de fondeado/descubierto.
            bucket = data.setdefault(commercial.id, {
                'partner': commercial,
                'sales': self.env['pos.order'],
                'refunds': self.env['pos.order'],
            })
            if (order.amount_total or 0.0) < -0.001:
                bucket['refunds'] |= order
            else:
                bucket['sales'] |= order
        for info in data.values():
            try:
                with self.env.cr.savepoint():
                    if info['sales']:
                        self._settle_advance_partner(
                            info['partner'], info['sales'])
                    if info['refunds']:
                        self._settle_advance_refund(
                            info['partner'], info['refunds'], info['sales'])
            except Exception as e:
                if raise_on_error:
                    raise
                _logger.warning(
                    'Socio %s excluido del pareo (%s); lo verá contabilidad.',
                    info['partner'].display_name, e,
                )
                self._log_settle_event(
                    'Sesión %s socio %s excluido del pareo: %s'
                    % (self.name, info['partner'].display_name, e),
                    level='error')
        # 2805 de depósitos: pareo FIFO global (ventas sin partner).
        try:
            with self.env.cr.savepoint():
                advance = self.company_id.pos_advance_account_id
                if advance:
                    self._pair_account_lines(advance)
        except Exception as e:
            if raise_on_error:
                raise
            _logger.warning('Pareo 2805 omitido: %s', e)
            self._log_settle_event(
                'Sesión %s: pareo 2805 omitido: %s' % (self.name, e),
                level='error')

    def _settle_advance_partner(self, commercial, orders):
        rxc = commercial.property_account_receivable_id
        if not rxc:
            raise UserError(_('Sin CxC para %s') % commercial.display_name)
        partners = commercial | commercial.child_ids
        MoveLine = self.env['account.move.line']

        advance_methods = self.env['pos.payment.method'].search(
            [('is_advance_payment', '=', True),
             ('company_id', '=', self.company_id.id)])
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
        if tendered > 0.001 and not inter:
            _logger.warning(
                'Saldo %s: digitado %s sin líneas split deudoras en sesión '
                '(métodos=%s, partners=%s); funded será 0.',
                commercial.display_name, tendered, method_names,
                partners.ids)
            self._log_settle_event(
                'Sesión %s socio %s: sin split deudores para fondear %s '
                '(métodos=%s).' % (
                    self.name, commercial.display_name, tendered,
                    method_names))
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
        mirrors = MoveLine.search([
            ('move_id', '=', self.move_id.id),
            ('account_id', '=', rxc.id),
            ('partner_id', 'in', partners.ids),
            ('credit', '>', 0.0),
            ('name', '=', 'From invoiced orders'),
        ])
        # Keep fully reconciled mirrors in the manual-payment exclusion. The
        # open subset is only for creating new partial reconciliations.
        mirror_ids = mirrors.ids
        open_mirrors = mirrors.filtered(
            lambda l: abs(l.amount_residual) > 0.001)
        dirty = self.env['account.partial.reconcile'].search([
            ('debit_move_id.move_id', 'in', invoices.ids),
            ('debit_move_id.account_id', '=', rxc.id),
            ('credit_move_id', 'not in', mirror_ids),
            ('credit_move_id.move_id.type', '!=', 'out_refund'),
        ])
        refund_links = self.env['account.partial.reconcile'].search([
            ('debit_move_id.move_id', 'in', invoices.ids),
            ('debit_move_id.account_id', '=', rxc.id),
            ('credit_move_id.move_id.type', '=', 'out_refund'),
        ])
        if dirty or refund_links:
            _logger.info(
                'Socio %s con pareos externos; se conserva pareo nativo '
                '(facturas=%s, espejo=%s, parciales=%s, notas=%s).',
                commercial.display_name, invoices.ids, mirror_ids,
                dirty.ids, refund_links.ids)
            self._log_settle_event(
                'Sesión %s socio %s: pareos externos, se conserva pareo '
                'nativo (facturas=%s, parciales=%s, notas=%s).' % (
                    self.name, commercial.display_name, invoices.ids,
                    dirty.ids, refund_links.ids))
            return

        if overdraft <= 0.001:
            # Todo fondeado, pero la factura puede seguir abierta si el
            # nativo nunca la enlazó con el espejo (p. ej. espejos neteados
            # con una devolución, caso Shop/1416). Pareo directo del espejo
            # restante; si no hay nada abierto, no hace nada.
            # NOTA: `Partial.create` directo no marca `reconciled=True`
            # (solo `reconcile()` lo hace); filtrar por residual evita
            # desemparejar enlaces ya consumidos (caso T5/SONIA).
            self._pair_mirror_to_invoices(
                open_mirrors, invoices, rxc, fresh)
            _logger.info(
                'Saldo liquidado %s: digitado %s, fondeado %s, fiado %s.',
                commercial.display_name, tendered, funded, overdraft)
            return  # Nativo correcto: todo fondeado.

        # 3) Desemparejar espejo↔factura por el descubierto y reasignar el
        # espejo al intermediario. Se refresca todo tras el unlink.
        mirror = mirrors
        linked = self.env['account.partial.reconcile'].search([
            ('credit_move_id', 'in', mirror.ids),
            ('debit_move_id.move_id', 'in', invoices.ids),
        ])
        if not linked:
            # Sin enlace previo del nativo: pareo directo del espejo
            # restante contra las facturas abiertas (caso Shop/1416).
            self._pair_mirror_to_invoices(
                open_mirrors, invoices, rxc, fresh)
            _logger.info(
                'Sin pareo nativo espejo↔factura para %s; pareo directo.',
                commercial.display_name)
            return
        _logger.info(
            'Saldo %s: recomponiendo espejo↔factura por fiado %s '
            '(espejo=%s, enlazados=%s, fondeado=%s, facturas=%s).',
            commercial.display_name, overdraft, mirror.ids, linked.ids,
            funded, invoices.ids)
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
                and l.debit > 0.0 and abs(l.amount_residual) > 0.001)
            if open_lines:
                self._pair_amount(
                    mirror.filtered(lambda l: not l.reconciled),
                    open_lines,
                    sum(open_lines.mapped('amount_residual')))
        _logger.info(
            'Saldo liquidado %s: digitado %s, fondeado %s, fiado %s.',
            commercial.display_name, tendered, funded, overdraft)

    # ---- helpers ----
    def _settle_advance_refund(self, commercial, refund_orders,
                               sale_orders=None):
        """Pareo de sobrantes de devolución con neteo por socio comercial.

        El `Dr From invoiced orders` de la sesión es NETO (nativo suma
        ventas − devoluciones por partner): asumir `Dr >= total devuelto`
        es falso cuando hay ventas facturadas al mismo socio en la misma
        sesión (caso POS/01303: Dr 61k vs devoluciones 157k).

        Pasos (idempotentes; solo actúan sobre residuales abiertos):
        1. Deshace pareos RINV↔sesión (el crédito vivo queda en la nota).
        2. Deshace pareos circulares sesión↔sesión previos para recomputar
           en limpio (caso 8475/8476, 1473-1475).
        3. Netea por socio: `net = ventas + devoluciones` (firmados). Si
           `net < 0`, parea `min(-net, Dr disponible)` de Cr de sesión
           contra Dr de sesión; el resto queda como crédito vivo en RINV
           (visible vía `advance_session_ghosts`), no en líneas de sesión.
        3b. Si `net >= 0` (las ventas cubren las devoluciones, caso SONIA),
           netea el Cr de sesión contra el Dr de venta con saldo libre:
           el dinero de la devolución financió la venta y la sesión queda
           vacía sin tocar RINV/INV ya conciliadas por el nativo.
        4. El remanente de Cr de sesión que exceda el Dr de sesión se aplica
           contra débitos abiertos (facturas con residual) del mismo socio.
        """
        rxc = commercial.property_account_receivable_id
        if not rxc:
            return
        partners = commercial | commercial.child_ids
        total = sum(-(o.amount_total or 0.0) for o in refund_orders)
        if total <= 0.001:
            return
        sale_orders = sale_orders or self.env['pos.order']
        net = sum((o.amount_total or 0.0)
                  for o in (sale_orders | refund_orders))
        # El cierre nativo puede haber emparejado la RINV de la devolución
        # contra el Dr del propio asiento de sesión, cerrando la RINV y
        # dejando el Cr del método huérfano: el saldo queda invisible (ni
        # pagos ni notas lo ven). Se deshace ese pareo para que el crédito
        # vivo quede en la nota y la sesión netee a cero.
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
            [('is_advance_payment', '=', True),
             ('company_id', '=', self.company_id.id)]).mapped('name')
        # 2) Circulares sesión↔sesión: se deshacen para recomputar en
        # limpio (idempotencia: reprocesar no duplica parciales).
        circular = self.env['account.partial.reconcile'].search([
            ('debit_move_id.move_id', '=', self.move_id.id),
            ('credit_move_id.move_id', '=', self.move_id.id),
            ('debit_move_id.account_id', '=', rxc.id),
            ('credit_move_id.account_id', '=', rxc.id),
            ('debit_move_id.partner_id', 'in', partners.ids),
            ('credit_move_id.partner_id', 'in', partners.ids),
        ])
        def is_advance_line(line):
            return any(name in (line.name or '') for name in method_names)

        circular = circular.filtered(lambda p: (
            (p.debit_move_id.name == 'From invoiced orders' and
             is_advance_line(p.credit_move_id)) or
            (p.credit_move_id.name == 'From invoiced orders' and
             is_advance_line(p.debit_move_id))))
        if circular:
            (circular.mapped('debit_move_id')
             | circular.mapped('credit_move_id')).remove_move_reconcile()
            _logger.info(
                'Reembolso %s: deshechos %d pareo(s) circular(es) '
                'sesión↔sesión (%s).',
                commercial.display_name, len(circular), circular.ids)
        MoveLine = self.env['account.move.line']
        debits = MoveLine.search([
            ('move_id', '=', self.move_id.id),
            ('company_id', '=', self.company_id.id),
            ('account_id', '=', rxc.id),
            ('reconciled', '=', False),
            ('debit', '>', 0.0),
            ('partner_id', 'in', partners.ids),
            ('name', '=', 'From invoiced orders'),
        ])
        credits = MoveLine.search([
            ('move_id', '=', self.move_id.id),
            ('company_id', '=', self.company_id.id),
            ('account_id', '=', rxc.id),
            ('reconciled', '=', False),
            ('credit', '>', 0.0),
            ('partner_id', 'in', partners.ids),
        ])
        if method_names:
            credits = credits.filtered(
                lambda l: any(n in (l.name or '') for n in method_names))
        need = min(total, -net) if net < -0.001 else 0.0
        paired = self._pair_amount(credits, debits, need) if need > 0.001 else 0.0
        # 3b) Ventas cubren devoluciones: el tender con saldo financió la
        # diferencia; netear Cr de sesión contra Dr de venta libre (solo
        # residuales abiertos: si el fondeo ya los consumió, no hace nada).
        if net >= -0.001 and total - paired > 0.001:
            sale_debits = MoveLine.search([
                ('move_id', '=', self.move_id.id),
                ('company_id', '=', self.company_id.id),
                ('account_id', '=', rxc.id),
                ('reconciled', '=', False),
                ('debit', '>', 0.0),
                ('partner_id', 'in', partners.ids),
                ('name', '!=', 'From invoiced orders'),
            ])
            if method_names:
                sale_debits = sale_debits.filtered(
                    lambda l: any(n in (l.name or '') for n in method_names))
            if sale_debits:
                paired += self._pair_amount(
                    credits, sale_debits, total - paired)
        # 4) Remanente de Cr de sesión: aplicarlo a débitos abiertos del
        # mismo socio (facturas con residual), en vez de dejarlo huérfano.
        leftover = total - paired
        applied_out = 0.0
        if leftover > 0.001:
            open_debits = MoveLine.search([
                ('account_id', '=', rxc.id),
                ('company_id', '=', self.company_id.id),
                ('partner_id', 'in', partners.ids),
                ('reconciled', '=', False),
                ('debit', '>', 0.0),
                ('move_id.state', '=', 'posted'),
                ('move_id', '!=', self.move_id.id),
                ('move_id.type', '=', 'out_invoice'),
            ], order='date asc, id asc')
            if open_debits:
                applied_out = self._pair_amount(credits, open_debits, leftover)
        _logger.info('Reembolso %s: neto sesión %s (neto socio %s, '
                     'devuelto %s); pareado interno %s, aplicado a '
                     'facturas %s.',
                     commercial.display_name, net, net, total, paired,
                     applied_out)
        if total - paired - applied_out > 0.001:
            self._log_settle_event(
                'Sesión %s socio %s: quedan %s sin parear en sesión '
                '(ver advance_session_ghosts).' % (
                    self.name, commercial.display_name,
                    total - paired - applied_out))

    def _split_debits(self, account, partners, method_names):
        lines = self.env['account.move.line'].search([
            ('move_id', '=', self.move_id.id),
            ('company_id', '=', self.company_id.id),
            ('account_id', '=', account.id),
            ('reconciled', '=', False),
            ('debit', '>', 0.0),
            ('partner_id', 'in', partners.ids),
        ])
        if method_names:
            named = lines.filtered(
                lambda l: any(n in (l.name or '') for n in method_names))
            return named
        return lines

    def _old_credits(self, account, partners):
        return self.env['account.move.line'].search([
            ('account_id', '=', account.id),
            ('company_id', '=', self.company_id.id),
            ('partner_id', 'in', partners.ids),
            ('reconciled', '=', False),
            ('move_id.state', '=', 'posted'),
            ('move_id', '!=', self.move_id.id),
            ('credit', '>', 0.0),
        ], order='date asc, id asc')

    def _pair_lines(self, debits, credits):
        """Pareo FIFO total; devuelve monto fondeado."""
        funded = 0.0
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
                self._create_advance_partial(debit, credit, amount)
                funded += amount
                remaining -= amount
        return funded

    def _pair_amount(self, credits, debits, amount):
        """Parea hasta `amount` entre conjuntos (FIFO por fecha)."""
        if amount <= 0.001:
            return 0.0
        paired = 0.0
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
                self._create_advance_partial(debit, credit, take)
                paired += take
                remaining -= take
        return paired

    def _create_advance_partial(self, debit, credit, amount):
        """Create a company-currency partial and complete full matching."""
        if (debit.currency_id or credit.currency_id or
                debit.account_id.currency_id):
            raise UserError(_(
                'No se puede conciliar automáticamente una línea en moneda '
                'extranjera; requiere revisión contable.'))
        self.env['account.partial.reconcile'].create({
            'debit_move_id': debit.id,
            'credit_move_id': credit.id,
            'amount': amount,
        })
        (debit | credit).check_full_reconcile()

    def _pair_mirror_to_invoices(self, mirror, invoices, rxc, fresh):
        """Pareo directo del espejo restante contra facturas abiertas.

        Red de seguridad cuando el nativo nunca enlazó espejo↔factura
        (p. ej. espejos neteados con una devolución, caso Shop/1416: la
        factura quedaba abierta para siempre). Solo pareo hasta el
        residual, facturas antiguas primero; si no hay nada abierto,
        no hace nada.
        """
        mirror = fresh(mirror.ids).filtered(lambda l: not l.reconciled)
        for inv in invoices.sorted('date'):
            open_lines = fresh(inv.line_ids.ids).filtered(
                lambda l: l.account_id == rxc and not l.reconciled
                and l.debit > 0.0 and abs(l.amount_residual) > 0.001)
            if open_lines:
                self._pair_amount(
                    mirror.filtered(
                        lambda l: not l.reconciled
                        and abs(l.amount_residual) > 0.001),
                    open_lines,
                    sum(open_lines.mapped('amount_residual')))

    def _pair_account_lines(self, account):
        """Pareo FIFO global en una cuenta de clearing (2805)."""
        lines = self.env['account.move.line'].search([
            ('account_id', '=', account.id),
            ('company_id', '=', self.company_id.id),
            ('reconciled', '=', False),
            ('move_id.state', '=', 'posted'),
        ], order='date asc, id asc')
        self._pair_lines(
            lines.filtered(lambda l: l.amount_residual > 0.001),
            lines.filtered(lambda l: l.amount_residual < -0.001))
