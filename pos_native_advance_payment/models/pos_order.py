# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

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
        return bool(self.env['pos.payment.method'].search(
            [('id', 'in', method_ids), ('is_advance_payment', '=', True)],
            limit=1,
        ))

    @api.model
    def _get_session_advance_used(self, session, partner, exclude_order_id=None):
        """Saldo ya digitado con el método en la sesión abierta (órdenes
        guardadas; la actual aún no existe en BD y llega por UI). Evita que
        dos ventas seguidas rebasen el cupo antes del cierre."""
        domain = [
            ('session_id', '=', session.id),
            ('partner_id', '=', partner.id),
            ('state', '!=', 'cancel'),
            ('is_advance_deposit', '=', False),
        ]
        if exclude_order_id:
            domain.append(('id', '!=', exclude_order_id))
        total = 0.0
        for other in self.search(domain):
            total += sum(other.payment_ids.filtered(
                lambda p: p.payment_method_id.is_advance_payment
            ).mapped('amount'))
        return total

    @api.model
    def _get_advance_credit_used(self, partner):
        """Sobregiro en uso: residual abierto de facturas nacidas de ventas
        TPV con Saldo a Favor. Esas facturas consumieron cupo de crédito que
        aún no se ha pagado por otra vía."""
        methods = self.env['pos.payment.method'].search(
            [('is_advance_payment', '=', True)])
        if not methods:
            return 0.0
        payments = self.env['pos.payment'].search(
            [('payment_method_id', 'in', methods.ids)])
        order_names = [p.pos_order_id.name for p in payments
                       if p.pos_order_id.partner_id == partner]
        if not order_names:
            return 0.0
        invoices = self.env['account.move'].search([
            ('type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('invoice_origin', 'in', order_names),
            ('amount_residual', '>', 0.001),
        ])
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
                    if method.exists() and method.is_advance_payment:
                        advance_amount += amount
                        advance_methods |= method
            else:  # Llamadas sin payload (revalidaciones internas)
                found = order.payment_ids.filtered(
                    lambda p: p.payment_method_id.is_advance_payment
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
            partner = order.partner_id
            # Serializa consumidores concurrentes del mismo saldo: el segundo
            # cajero recibe "reintente" en vez de permitir sobregiro doble.
            try:
                self.env.cr.execute("""
                    SELECT id FROM account_move_line
                    WHERE partner_id = %s
                      AND account_id = %s
                      AND reconciled = false
                      AND move_id IN (SELECT id FROM account_move WHERE state = 'posted')
                    FOR UPDATE NOWAIT
                """, [partner.id,
                      partner.property_account_receivable_id.id])
            except Exception as e:
                if 'could not obtain lock' in str(e).lower():
                    raise ValidationError(_(
                        "Otro cajero usa el saldo de este cliente. "
                        "Reintente el pago."))
                raise
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
                self._get_advance_credit_used(partner)
            if order.session_id:
                available -= self._get_session_advance_used(
                    order.session_id, partner,
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
            self._reverse_advance_refund(order)
        return res

    def _reverse_advance_refund(self, refund):
        """Aplica la nota de devolución a facturas abiertas con Saldo (FIFO,
        antiguas primero) del mismo socio. Sin buscar "la" venta original:
        con compras repetidas es inidentificable y no hace falta — el crédito
        de la nota es fungible. Remanente sin facturas abiertas queda como
        crédito nuevo gastable. Sin historia que desemparejar. Errores:
        propagan (rollback)."""
        rinv = refund.account_move
        if not rinv or rinv.type != 'out_refund' or rinv.state != 'posted':
            _logger.info('Devolución %s sin nota crédito publicada; se omite.',
                         refund.name)
            return False
        partner = refund.partner_id
        rxc = partner.property_account_receivable_id
        order_names = [o.name for o in self.search([
            ('partner_id', '=', partner.id),
            ('is_advance_deposit', '=', False),
        ]) if o.payment_ids.filtered(
            lambda p: p.payment_method_id.is_advance_payment)]
        invoices = self.env['account.move'].search([
            ('partner_id', '=', partner.id),
            ('type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('invoice_origin', 'in', order_names or [False]),
            ('amount_residual', '>', 0.001),
        ], order='date asc, id asc')
        Partial = self.env['account.partial.reconcile']
        credit_lines = rinv.line_ids.filtered(
            lambda l: l.account_id == rxc and not l.reconciled
            and l.credit > 0.0)
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
                    Partial.create({
                        'debit_move_id': dline.id,
                        'credit_move_id': cline.id,
                        'amount': amount,
                    })
        _logger.info('Devolución %s: nota %s aplicada a facturas con saldo.',
                     refund.name, rinv.name)
        return True

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
