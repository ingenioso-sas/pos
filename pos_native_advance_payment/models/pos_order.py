# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    is_advance_deposit = fields.Boolean(
        string="Depósito a Saldo a Favor",
        help="Pedido con el producto auxiliar de depósito. Su efectivo/banco "
             "queda en la sesión como una venta normal; el crédito aplicable "
             "a facturas se crea como account.payment (clearing)."
    )

    # ------------------------------------------------------------------
    # Entrada desde TPV
    # ------------------------------------------------------------------
    @api.model
    def create_from_ui(self, orders, draft=False):
        for order in orders:
            data = order.get('data', {})
            if data.get('is_advance_deposit') and not draft:
                self._validate_deposit_config_ui(data)
        try:
            res = super(PosOrder, self).create_from_ui(orders, draft=draft)
        except Exception:
            _logger.exception('create_from_ui falló para depósito TPV')
            raise
        if not draft:
            # Fuera del try interno del núcleo (action_pos_order_paid traga
            # excepciones no-DB): si esto falla, la transacción revierte
            # completa y no se pierde ni el efectivo ni el crédito.
            created = self.browse([r['id'] for r in res]) if res else self
            for order in created.filtered('is_advance_deposit'):
                self._create_advance_payment_for_deposit(order)
        return res

    @api.model
    def _validate_deposit_config_ui(self, data):
        pos_session = self.env['pos.session'].browse(data.get('pos_session_id'))
        if not pos_session.exists() or \
                pos_session.company_id not in self.env.user.company_ids:
            raise AccessError(_(
                'La sesión TPV no existe o pertenece a otra compañía.'))
        company = pos_session.company_id or self.env.company
        if not company.pos_advance_account_id:
            raise UserError(_(
                "No se puede procesar el depósito: "
                "no hay cuenta de anticipos configurada para la compañía '%s'.\n\n"
                "Configurela en: Ajustes > Punto de Venta > Anticipos y Saldos a Favor."
            ) % company.display_name)
        if not company.pos_deposit_product_id:
            raise UserError(_(
                "No se puede procesar el depósito: "
                "no hay producto auxiliar de depósito configurado.\n\n"
                "Configurelo en: Ajustes > Punto de Venta > Anticipos y Saldos a Favor."
            ))
        if not company.pos_advance_journal_id:
            raise UserError(_(
                "No se puede procesar el depósito: "
                "no hay diario clearing de anticipos configurado.\n\n"
                "Configurelo en: Ajustes > Punto de Venta > Anticipos y Saldos a Favor."
            ))
        if not data.get('lines'):
            raise UserError(_(
                "Depósito sin línea de producto. Actualice el TPV (producto "
                "auxiliar) y reintente."
            ))

    # ------------------------------------------------------------------
    # Restricciones al consumir saldo (toda venta con saldo => factura)
    # ------------------------------------------------------------------
    @api.model
    def _ui_uses_advance(self, ui_order):
        method_ids = []
        for st in ui_order.get('statement_ids') or []:
            try:
                method_ids.append(st[2].get('payment_method_id'))
            except Exception:
                continue
        if not method_ids:
            return False
        session = self.env['pos.session'].browse(ui_order.get('pos_session_id'))
        domain = [
            ('id', 'in', method_ids),
            ('is_advance_payment', '=', True),
        ]
        if session.company_id:
            domain.append(('company_id', '=', session.company_id.id))
        return bool(self.env['pos.payment.method'].search(domain, limit=1))

    @api.model
    def _get_session_advance_used(self, session, partner, exclude_order_id=None):
        """Saldo ya digitado con el método en UNA sesión abierta (órdenes
        guardadas; la actual aún no existe en BD y llega por UI). Evita que
        dos ventas seguidas rebasen el cupo antes del cierre."""
        if not session:
            return 0.0
        return self._get_open_sessions_advance_used(
            partner,
            session.company_id,
            session_ids=session.ids,
            exclude_order_id=exclude_order_id,
        )

    @api.model
    def _get_open_sessions_advance_used(self, partner, company, session_ids=None,
                                        exclude_order_id=None):
        """Uso de saldo en TODAS las sesiones abiertas de la compañía.

        El saldo es fungible por socio: dos cajas/turnos con sesiones
        abiertas distintas no pueden gastar el mismo dinero (cubre sesiones
        rescue y multicaja). La orden actual se excluye (aún no existe en
        BD y llega por UI).

        Solo cuentan los consumos positivos: las devoluciones (montos
        negativos) NO consumen saldo, lo crean (su nota crédito ya suma
        en el total). Restar un negativo inflaría el disponible.
        """
        domain = [
            ("partner_id", "=", partner.id),
            ("state", "!=", "cancel"),
            ("is_advance_deposit", "=", False),
        ]
        if session_ids is None:
            open_sessions = self.env["pos.session"].search(
                [
                    ("state", "!=", "closed"),
                    ("config_id.company_id", "=", company.id),
                ]
            )
            domain.append(("session_id", "in", open_sessions.ids))
        else:
            domain.append(("session_id", "in", session_ids))
        if exclude_order_id:
            domain.append(("id", "!=", exclude_order_id))
        total = 0.0
        for other in self.search(domain):
            total += sum(
                amount for amount in other.payment_ids.filtered(
                    lambda p: p.payment_method_id.is_advance_payment
                ).mapped('amount') if amount > 0.0)
        return total

    @api.model
    def _get_advance_credit_used(self, partner, exclude_open_sessions=True,
                                 company=None):
        """Sobregiro en uso: residual abierto de facturas nacidas de ventas
        TPV con Saldo a Favor. Esas facturas consumieron cupo de crédito que
        aún no se ha pagado por otra vía.

        Con exclude_open_sessions (defecto) se ignoran las facturas cuyo
        pedido origen sigue en sesión abierta: ese consumo ya lo descuenta
        el cap de sesiones y contarlo dos veces bloquearía de más ventas
        legítimas (p. ej. saldo 4000, venta1 2000, venta2 2000).
        """
        company = company or self.env.company
        partner = partner.with_context(force_company=company.id)
        methods = self.env['pos.payment.method'].search(
            [('is_advance_payment', '=', True),
             ('company_id', '=', company.id)])
        if not methods:
            return 0.0
        payments = self.env['pos.payment'].search(
            [('payment_method_id', 'in', methods.ids),
             ('pos_order_id.company_id', '=', company.id)])
        order_names = [p.pos_order_id.name for p in payments
                       if p.pos_order_id.partner_id == partner]
        if not order_names:
            return 0.0
        invoices = self.env['account.move'].search([
            ('type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('company_id', '=', company.id),
            ('invoice_origin', 'in', order_names),
            ('amount_residual', '>', 0.001),
        ])
        if exclude_open_sessions:
            open_names = set(self.search([
                ('partner_id', '=', partner.id),
                ('company_id', '=', company.id),
                ('state', 'not in', ('cancel', 'done')),
            ]).mapped('name'))
            invoices = invoices.filtered(
                lambda inv: inv.invoice_origin not in open_names)
        return sum(invoices.mapped('amount_residual'))

    @api.model
    def _get_effective_overdraft(self, partner):
        """Cupo de crédito (delega en el partner)."""
        return partner._get_effective_overdraft()

    def _check_advance_payment_restrictions(self, ui_order=None):
        # BUG CORREGIDO: antes se leía order.payment_ids, que en órdenes
        # nuevas aún está vacío (los pagos se crean después en el super),
        # así que la validación JAMÁS se ejecutaba y pasaba saldo 0.
        # Ahora se lee el payload del TPV (statement_ids).
        for order in self:
            advance_amount = 0.0
            advance_methods = self.env['pos.payment.method'].browse()
            if ui_order is not None:
                methods = self.env['pos.payment.method']
                for st in ui_order.get('statement_ids') or []:
                    try:
                        vals = st[2] or {}
                    except Exception:
                        continue
                    amount = vals.get('amount') or 0.0
                    if amount <= 0.0:
                        continue
                    method = methods.browse(vals.get('payment_method_id'))
                    if (method.exists() and method.is_advance_payment and
                            method.company_id == order.company_id):
                        advance_amount += amount
                        advance_methods |= method
            else:  # Llamadas sin payload (revalidaciones internas)
                found = order.payment_ids.filtered(
                    lambda p: p.payment_method_id.is_advance_payment and
                    p.payment_method_id.company_id == order.company_id
                )
                advance_amount = sum(found.mapped('amount'))
                advance_methods = found.mapped('payment_method_id')
            if order.is_advance_deposit:
                if advance_amount > 0.001:
                    raise ValidationError(_(
                        "No puede pagar un depósito a Saldo a Favor con "
                        "Saldo a Favor."
                    ))
                continue
            if advance_amount <= 0.001:
                continue
            for method in advance_methods:
                if not method.split_transactions:
                    raise ValidationError(_(
                        "El método '%s' debe tener activado 'Dividir "
                        "transacciones' (atribución por cliente al cierre)."
                    ) % method.display_name)
            if not order.partner_id:
                raise ValidationError(_(
                    "Debe seleccionar un cliente para usar el método de Saldo a Favor."
                ))
            partner = order.partner_id.with_context(
                force_company=order.company_id.id)
            # Serializa consumidores concurrentes del mismo saldo: el segundo
            # cajero recibe "reintente" en vez de permitir sobregiro doble.
            try:
                self.env.cr.execute(
                    'SELECT id FROM res_partner WHERE id = %s FOR UPDATE NOWAIT',
                    [partner.id])
                self.env.cr.execute("""
                    SELECT id FROM account_move_line
                    WHERE partner_id = %s
                      AND account_id = %s
                      AND company_id = %s
                      AND reconciled = false
                      AND move_id IN (SELECT id FROM account_move WHERE state = 'posted')
                    FOR UPDATE NOWAIT
                """, [partner.id,
                      partner.property_account_receivable_id.id,
                      order.company_id.id])
            except Exception as e:
                if 'could not obtain lock' in str(e).lower():
                    raise ValidationError(_(
                        "Otro cajero usa el saldo de este cliente. "
                        "Reintente el pago."))
                raise
            foreign_lines = partner._get_advance_outstanding_lines(
                order.company_id).filtered(
                    lambda l: l.currency_id or l.account_id.currency_id)
            if foreign_lines:
                raise ValidationError(_(
                    'El saldo a favor de este cliente está en moneda '
                    'extranjera y requiere revisión contable antes de usarlo '
                    'en el TPV.'))
            if not partner.advance_payment_allowed:
                raise ValidationError(_(
                    "El cliente %s no está habilitado para usar Saldo a Favor en TPV."
                ) % partner.display_name)
            if not partner.vat:
                raise ValidationError(_(
                    "El cliente %s no tiene NIT/documento registrado.\n\n"
                    "Las ventas con Saldo a Favor siempre se facturan: "
                    "complete la identificación fiscal del cliente y reintente."
                ) % partner.display_name)
            # Sin vueltos en saldo: lo ofrecido con el método no puede
            # superar el total (si no, el excedente se volvería efectivo).
            if advance_amount - (order.amount_total or 0.0) > 0.001:
                raise ValidationError(_(
                    "El monto con Saldo a Favor (%s) supera el total (%s). "
                    "Ajuste el medio de pago; no se dan vueltos en saldo."
                ) % (advance_amount, order.amount_total))
            available = partner.pos_advance_balance + \
                self._get_effective_overdraft(partner) - \
                self._get_advance_credit_used(
                    partner, company=order.company_id) - \
                self._get_open_sessions_advance_used(
                    partner,
                    order.company_id or order.session_id.company_id,
                    exclude_order_id=order.id or None)
            if advance_amount - available > 0.001:
                raise ValidationError(_(
                    "Saldo a favor insuficiente para %s.\n"
                    "Solicitado: %s | Disponible (saldo + cupo - en uso, "
                    "incluye sesión actual): %s."
                ) % (partner.display_name, advance_amount, available))

    def _process_payment_lines(self, pos_order, order, pos_session, draft):
        order._check_advance_payment_restrictions(ui_order=pos_order)
        return super(PosOrder, self)._process_payment_lines(
            pos_order, order, pos_session, draft)

    # ------------------------------------------------------------------
    # Pago del depósito: fuera del try del núcleo
    # ------------------------------------------------------------------
    # NOTA: no se sobrescribe action_pos_order_paid: el núcleo lo ejecuta
    # dentro de try/except que traga toda excepción no-DB (solo loguea).
    # Cualquier error nuestro ahí dejaría la orden pagada sin crédito.
    # - Depósitos: se crean en create_from_ui (post-super, propaga).
    # - Ventas con saldo: la factura es nativa y TODO el consumo se resuelve
    #   al cierre (pos.session._settle_advance_partner). Aplicar créditos al
    #   crear la factura es incompatible con el pareo del cierre (doble
    #   conteo contra el intermediario): por eso no hay hook de invoice.

    # NOTA: action_pos_order_invoice es 100% nativo a propósito (ver arriba).

    def action_pos_order_invoice(self):
        res = super(PosOrder, self).action_pos_order_invoice()
        # Solo devoluciones con Saldo. Los errores SÍ propagan (rollback
        # seguro; nada queda a medias). Solo la falta de original única se
        # omite con aviso (devolver no puede bloquearse por historia).
        for order in self.filtered(
                lambda o: not o.is_advance_deposit and (o.amount_total or 0.0) < -0.001
                and sum(o.payment_ids.filtered(
                    lambda p: p.payment_method_id.is_advance_payment
                ).mapped('amount')) < -0.001):
            self._apply_refund_to_open_invoices(order)
        return res

    def _get_refund_order_names(self, partner, company):
        """Nombres de pedidos del socio pagados (total o parcial) con Saldo.

        Fuente única: `pos.payment` con método de anticipo (igual que
        `_get_advance_credit_used`). Robusto frente al momento de llamada:
        no depende de que los `pos.payment` de la devolución en curso ya
        existan en BD.
        """
        methods = self.env['pos.payment.method'].search(
            [('is_advance_payment', '=', True),
             ('company_id', '=', company.id)])
        if not methods:
            return []
        payments = self.env['pos.payment'].search([
            ('payment_method_id', 'in', methods.ids),
            ('pos_order_id.partner_id', '=', partner.id),
            ('pos_order_id.company_id', '=', company.id),
        ])
        names = set()
        for pay in payments:
            order = pay.pos_order_id
            if order and not order.is_advance_deposit:
                names.add(order.name)
        return sorted(names)

    @api.model
    def apply_refund_to_open_invoices(self, refund):
        """RPC-safe wrapper for the internal refund reconciliation helper."""
        if not self.env.user.has_group('account.group_account_manager'):
            raise AccessError(_(
                'Solo un responsable contable puede reprocesar devoluciones.'))
        return self._apply_refund_to_open_invoices(refund)

    @api.model
    def _apply_refund_to_open_invoices(self, refund):
        """Aplica la nota crédito de una devolución TPV a facturas abiertas
        con Saldo a Favor del mismo socio (FIFO: antiguas primero).

        Idempotente y re-ejecutable (cron/wizard para huérfanos como
        RINV/2026/0009 del caso POS/01303): solo crea parciales por
        residuales abiertos; una segunda corrida no duplica nada.
        Devuelve el monto aplicado (0.0 si no había nada que aplicar).
        Los errores propagan (rollback seguro; nada queda a medias).
        """
        refund.ensure_one()
        if refund._name != 'pos.order':
            raise UserError(_('El registro no es una devolución TPV.'))
        if (refund.amount_total or 0.0) >= -0.001:
            raise UserError(_('La orden TPV no tiene un total negativo.'))
        if sum(refund.payment_ids.filtered(
                lambda p: p.payment_method_id.is_advance_payment
        ).mapped('amount')) >= -0.001:
            raise UserError(_(
                'La devolución no fue pagada con Saldo a Favor.'))
        if refund.state == 'cancel':
            raise UserError(_('No se puede reprocesar una devolución cancelada.'))
        company = refund.company_id
        if not company:
            raise UserError(_('La devolución no tiene compañía.'))
        self.env.cr.execute(
            'SELECT id FROM pos_order WHERE id = %s FOR UPDATE',
            [refund.id])
        refund = refund.with_context(force_company=company.id)
        rinv = refund.account_move
        if not rinv or rinv.type != 'out_refund' or rinv.state != 'posted':
            _logger.info('Devolución %s sin nota crédito publicada; se omite.',
                         refund.name)
            return 0.0
        partner = refund.partner_id
        rxc = partner.property_account_receivable_id
        if not rxc:
            return 0.0
        order_names = self._get_refund_order_names(partner, company)
        invoices = self.env['account.move'].search([
            ('partner_id', '=', partner.id),
            ('type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('company_id', '=', company.id),
            ('invoice_origin', 'in', order_names or [False]),
            ('amount_residual', '>', 0.001),
        ], order='date asc, id asc')
        credit_lines = rinv.line_ids.filtered(
            lambda l: l.account_id == rxc and not l.reconciled
            and l.credit > 0.0)
        debit_lines = invoices.mapped('line_ids').filtered(
            lambda l: l.account_id == rxc and not l.reconciled
            and l.debit > 0.0)
        lock_ids = credit_lines.ids + debit_lines.ids
        if lock_ids:
            self.env.cr.execute(
                'SELECT id FROM account_move_line '
                'WHERE id IN %s FOR UPDATE', [tuple(lock_ids)])
            self.env['account.move.line'].invalidate_cache(
                ids=lock_ids)
        _logger.info(
            'Devolución %s: RINV %s; órdenes con saldo=%s; '
            'facturas abiertas=%s; líneas crédito=%s.',
            refund.name, rinv.name, order_names,
            [(m.name, m.invoice_origin, m.amount_residual) for m in invoices],
            [(l.id, l.amount_residual) for l in credit_lines],
        )
        applied = 0.0
        for cline in credit_lines:
            if cline.reconciled:
                continue
            for inv in invoices:
                if cline.reconciled:
                    break
                debit_lines = inv.line_ids.filtered(
                    lambda l: l.account_id == rxc and not l.reconciled
                    and l.debit > 0.0)
                for dline in debit_lines:
                    if cline.reconciled or dline.reconciled:
                        continue
                    amount = min(abs(cline.amount_residual),
                                 abs(dline.amount_residual))
                    if amount <= 0.001:
                        continue
                    self._create_advance_partial(dline, cline, amount)
                    applied += amount
                    _logger.info(
                        'Devolución %s: aplicado %s '
                        '(Dr %s factura %s ↔ Cr %s nota %s).',
                        refund.name, amount,
                        dline.id, inv.name, cline.id, rinv.name,
                    )
        _logger.info('Devolución %s: nota %s aplicada a facturas con saldo; '
                     'total aplicado %s.',
                     refund.name, rinv.name, applied)
        return applied

    def _create_advance_partial(self, debit, credit, amount):
        """Create a safe company-currency partial and complete full matching."""
        if (debit.currency_id or credit.currency_id or
                debit.account_id.currency_id):
            raise UserError(_(
                'No se puede conciliar automáticamente una línea en moneda '
                'extranjera; requiere revisión contable.'))
        partial = self.env['account.partial.reconcile'].create({
            'debit_move_id': debit.id,
            'credit_move_id': credit.id,
            'amount': amount,
        })
        (debit | credit).check_full_reconcile()
        return partial

    def _create_advance_payment_for_deposit(self, order):
        """Crea el account.payment del depósito (idempotente).

        El asiento TPV ya registró Dr Caja/Banco / Cr Anticipos (producto
        auxiliar). Este pago registra Dr Anticipos / Cr CxC en el diario
        clearing, sin tocar efectivo. El crédito en CxC es el saldo a favor
        aplicable a facturas con el widget estándar.
        Se ejecuta en la misma transacción: si falla, todo revierte y no se
        pierde ni el efectivo ni el crédito.
        """
        Payment = self.env['account.payment']
        existing = Payment.search([('pos_order_id', '=', order.id)], limit=1)
        if existing:
            return existing
        if not order.partner_id or not order.payment_ids:
            raise UserError(_(
                "Depósito %s sin cliente o sin pago.") % order.name)
        company = order.company_id
        journal = company.pos_advance_journal_id
        advance = company.pos_advance_account_id
        if not journal or not advance:
            raise UserError(_(
                "Depósito %s: falta diario clearing o cuenta de anticipos."
            ) % order.name)
        if journal.type == 'cash':
            raise UserError(_(
                "El diario clearing '%s' no puede ser de efectivo."
            ) % journal.name)
        amount = sum(order.payment_ids.mapped('amount'))
        if amount <= 0.0:
            raise UserError(_(
                "El monto del depósito %s debe ser positivo.") % order.name)
        payment = Payment.create_pos_advance_payment(
            order.partner_id, amount, journal,
            communication=_('%s DEPÓSITO') % order.name,
            pos_order=order,
        )
        _logger.info(
            'Anticipo TPV: orden %s -> pago %s (%.2f)',
            order.name, payment.name, amount,
        )
        return payment

    # ------------------------------------------------------------------
    # Conciliación al consumir saldo en TPV (sobre CxC, no 2805)
    # ------------------------------------------------------------------
    def _order_fields(self, ui_order):
        res = super(PosOrder, self)._order_fields(ui_order)
        if ui_order.get('is_advance_deposit'):
            res['is_advance_deposit'] = True
            # Seguridad: con producto auxiliar ya viene correcto, pero si el
            # total llegara en 0 (cliente viejo sin actualizar), igualarlo al
            # pagado evita el 502 por orden en cero.
            if not res.get('amount_total'):
                res['amount_total'] = res.get('amount_paid', 0.0)
            return res
        # Regla de negocio: toda venta que usa Saldo a Favor se factura.
        # Incluye devoluciones con Saldo (total negativo): sin factura no
        # nace out_refund y el crédito para cambios se perdería.
        # Autoritativo en backend (el JS se puede saltar).
        try:
            if self._ui_uses_advance(ui_order):
                res['to_invoice'] = True
        except Exception:
            _logger.warning('No se pudo forzar factura en orden TPV',
                            exc_info=True)
        return res

    # NOTA: no existe _create_account_move_and_reconcile en el núcleo Odoo
    # 13 (ni en pos.order ni en pos.session). La conciliación vive en
    # pos.session: _settle_advance_partner (ventas con saldo) y pareo 2805
    # (depósitos).
