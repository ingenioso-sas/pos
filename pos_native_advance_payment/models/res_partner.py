# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _get_context_company(self):
        company_id = self.env.context.get('force_company')
        company = self.env['res.company'].browse(company_id).exists() \
            if company_id else self.env['res.company']
        return company or self.env.user.company_id

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

    pos_advance_session_used = fields.Float(
        string="Saldo Gastado en Sesión Abierta",
        compute="_compute_advance_amounts",
        help="Lo ya pagado con Saldo a Favor en órdenes de sesiones TPV "
             "abiertas de la compañía. La UI lo usa con max(contador "
             "local, este valor) para evitar doble descuento tras un "
             "refresh del TPV."
    )

    advance_ghosts = fields.Float(
        string="Fantasmas de Sesión (CxC sin conciliar)",
        compute="_compute_advance_ghosts",
        groups="account.group_account_user",
        help="Suma de residuales de líneas CxC sin conciliar del socio en "
             "asientos de sesiones TPV (move_id de pos.session). Detecta "
             "líneas huérfanas del cierre (caso POS/01303: 8475/8476/8471/"
             "8472) sin SQL manual. 0.0 = sesión neta."
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

    def _get_unreconciled_advance_payments(self, company=None):
        """Devuelve los account.payment de cliente (inbound, posted) con residual > 0.

        Fuente del saldo a favor: incluye pagos creados desde TPV
        (depósitos) y desde Facturación. Un pago parcialmente aplicado aporta
        solo su residual, no el total original.
        """
        self.ensure_one()
        company = company or self._get_context_company()
        partner = self.with_context(force_company=company.id)
        Payment = self.env['account.payment']
        payments = Payment.search([
            ('partner_id', '=', self.id),
            ('company_id', '=', company.id),
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
                    residual = partner._get_payment_residual_fallback(payment)
                except Exception as e:
                    _logger.warning(
                        'No se pudo calcular residual del pago %s: %s',
                        payment.id, e,
                    )
                    residual = 0.0
            if residual > 0.001:
                result.append((payment, residual))
        return result

    def _get_unreconciled_credit_notes(self, company=None):
        """Créditos de notas (out_refund publicadas, residual abierto).

        Una devolución cuyo remanente no cerró factura queda aquí como
        crédito nuevo y gastable, igual que un pago.
        """
        self.ensure_one()
        company = company or self._get_context_company()
        moves = self.env['account.move'].search([
            ('partner_id', '=', self.id),
            ('company_id', '=', company.id),
            ('type', '=', 'out_refund'),
            ('state', '=', 'posted'),
            ('amount_residual', '>', 0.001),
        ])
        return moves

    def _get_advance_outstanding_lines(self, company=None):
        """Líneas CxC sin conciliar aplicables como saldo a favor.

        Fuente única para TPV, wizard y reportes: incluye tanto líneas
        de pagos (account.payment) como de notas crédito (out_refund).
        Ambas son créditos en la misma CxC y se aplican con el mecanismo
        estándar (js_assign_outstanding_line / partial.reconcile).
        """
        self.ensure_one()
        company = company or self._get_context_company()
        partner = self.with_context(force_company=company.id)
        receivable = partner.property_account_receivable_id
        if not receivable:
            return self.env['account.move.line'].browse()
        return self.env['account.move.line'].search([
            ('partner_id', '=', self.id),
            ('company_id', '=', company.id),
            ('account_id', '=', receivable.id),
            ('reconciled', '=', False),
            ('move_id.state', '=', 'posted'),
            ('credit', '>', 0.0),
        ])

    def _get_payment_residual_fallback(self, payment):
        """Residual del pago vía líneas a cobrar no conciliadas de su asiento."""
        partner = self.with_context(force_company=payment.company_id.id)
        receivable = partner.property_account_receivable_id
        MoveLine = self.env['account.move.line']
        domain = [
            ('partner_id', '=', self.id),
            ('company_id', '=', payment.company_id.id),
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
                    [('name', '=', payment.move_name),
                     ('company_id', '=', payment.company_id.id)], limit=1)
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
        company = (self._get_context_company()
                   if self.env.context.get('force_company')
                   else self.company_id or self.env.user.company_id)
        return (self.advance_overdraft_limit or 0.0) or \
            (company.advance_overdraft_limit or 0.0)

    def _compute_advance_amounts(self):
        # Versión batch: el search_read masivo del POS instancia miles de
        # partners y serializar cada uno disparaba este compute con N+1
        # queries por partner (timeout). Aquí van ~10 queries en total,
        # constantes respecto al nº de partners. Misma fórmula y valores
        # que la versión por partner (los helpers de socio único se
        # conservan para wizard/reporte/validación).
        if not self:
            return
        try:
            data = self._batch_advance_data()
        except Exception as e:
            _logger.warning(
                'Error calculando saldos a favor en batch: %s', e)
            data = {}
        for partner in self:
            try:
                vals = data.get(partner.id, {})
                total = vals.get('total', 0.0)
                used = vals.get('used', 0.0)
                overdraft = vals.get('overdraft', 0.0)
                session_used = vals.get('session_used', 0.0)
            except Exception:
                total = used = overdraft = session_used = 0.0
            partner.pos_advance_balance = total
            partner.advance_credit_used = used
            partner.advance_available = \
                total + overdraft - used - session_used
            partner.advance_credit_remaining = \
                overdraft - used - session_used
            partner.pos_advance_session_used = session_used

    def _batch_advance_data(self):
        """Mapas {partner_id: valores} con queries batch.

        Réplica exacta de la semántica por partner:
        - total = residuales de pagos inbound publicados sin conciliar
          (solo parte no aplicada) + residuales de out_refund abiertas.
        - used = residual abierto de out_invoice nacidas de ventas TPV
          con Saldo a Favor, excluyendo órdenes en sesión abierta.
        - session_used = consumos positivos con Saldo en sesiones
          abiertas (las devoluciones NO consumen: crean crédito).
        """
        partners = self
        pids = partners.ids
        pid_set = set(pids)
        MoveLine = self.env['account.move.line']
        Payment = self.env['account.payment']
        Move = self.env['account.move']
        PosOrder = self.env['pos.order']
        company = self._get_context_company()

        receivable_by_pid = {}
        for partner in partners:
            rxc = partner.with_context(
                force_company=company.id).property_account_receivable_id
            receivable_by_pid[partner.id] = rxc.id if rxc else False

        # 1) Residuales de pagos por partner (1-3 queries).
        pay_residual_by_pid = dict.fromkeys(pids, 0.0)
        payments = Payment.search([
            ('partner_id', 'in', pids),
            ('company_id', '=', company.id),
            ('payment_type', '=', 'inbound'),
            ('partner_type', '=', 'customer'),
            ('state', '=', 'posted'),
        ])
        pay_by_id = {pay.id: pay for pay in payments}
        has_payment_id = 'payment_id' in MoveLine._fields
        with_lines = set()
        if payments and has_payment_id:
            amls = MoveLine.search([
                ('payment_id', 'in', payments.ids),
                ('partner_id', 'in', pids),
                ('company_id', '=', company.id),
                ('reconciled', '=', False),
                ('move_id.state', '=', 'posted'),
            ])
            by_pay = {}
            for line in amls:
                by_pay.setdefault(line.payment_id.id, []).append(line)
            for pay_id, lines in by_pay.items():
                pay = pay_by_id.get(pay_id)
                if not pay:
                    continue
                rel = [line for line in lines
                       if line.account_id.id ==
                       receivable_by_pid.get(pay.partner_id.id)
                       and line.partner_id.id == pay.partner_id.id]
                if rel:
                    with_lines.add(pay_id)
                    pay_residual_by_pid[pay.partner_id.id] = \
                        pay_residual_by_pid.get(pay.partner_id.id, 0.0) + \
                        sum(-line.amount_residual for line in rel
                            if line.amount_residual < 0.0)
        # Fallback (sin payment_id en línea o pago sin líneas): misma
        # lógica que _get_payment_residual_fallback, en batch.
        missing = [pay for pay in payments if pay.id not in with_lines] \
            if has_payment_id else list(payments)
        if missing:
            names = [pay.move_name for pay in missing
                     if getattr(pay, 'move_name', False)]
            moves = Move.search([
                ('name', 'in', names),
                ('company_id', '=', company.id),
            ]) if names else Move
            move_by_name = {move.name: move for move in moves} \
                if moves else {}
            need = [pay for pay in missing
                    if move_by_name.get(getattr(pay, 'move_name', False))]
            amls_by_move = {}
            if need:
                need_move_ids = []
                for pay in need:
                    mid = move_by_name[pay.move_name].id
                    if mid not in need_move_ids:
                        need_move_ids.append(mid)
                for line in MoveLine.search([
                        ('move_id', 'in', need_move_ids),
                        ('partner_id', 'in', pids),
                        ('company_id', '=', company.id),
                        ('reconciled', '=', False),
                        ('move_id.state', '=', 'posted'),
                ]):
                    amls_by_move.setdefault(line.move_id.id, []).append(line)
            for pay in missing:
                move = move_by_name.get(getattr(pay, 'move_name', False))
                if not move:
                    pay_residual_by_pid[pay.partner_id.id] = \
                        pay_residual_by_pid.get(pay.partner_id.id, 0.0) + \
                        (0.0 if pay.invoice_ids else pay.amount)
                    continue
                rel = [line for line in amls_by_move.get(move.id, [])
                       if line.account_id.id ==
                       receivable_by_pid.get(pay.partner_id.id)
                       and line.partner_id.id == pay.partner_id.id]
                pay_residual_by_pid[pay.partner_id.id] = \
                    pay_residual_by_pid.get(pay.partner_id.id, 0.0) + \
                    sum(-line.amount_residual for line in rel
                        if line.amount_residual < 0.0)

        # 2) Notas crédito abiertas por partner (1 query).
        note_by_pid = dict.fromkeys(pids, 0.0)
        for row in Move.read_group(
                [('partner_id', 'in', pids),
                  ('company_id', '=', company.id),
                  ('type', '=', 'out_refund'),
                 ('state', '=', 'posted'),
                 ('amount_residual', '>', 0.001)],
                ['partner_id', 'amount_residual'], ['partner_id']):
            note_by_pid[row['partner_id'][0]] = row['amount_residual']

        total_by_pid = {
            pid: pay_residual_by_pid.get(pid, 0.0) +
            note_by_pid.get(pid, 0.0) for pid in pids}

        # 3) Crédito en uso por partner (4 queries máx).
        used_by_pid = dict.fromkeys(pids, 0.0)
        methods = self.env['pos.payment.method'].search(
            [('is_advance_payment', '=', True),
             ('company_id', '=', company.id)])
        if methods:
            adv_payments = self.env['pos.payment'].search([
                ('payment_method_id', 'in', methods.ids),
                ('pos_order_id.partner_id', 'in', pids),
                ('pos_order_id.company_id', '=', company.id),
            ])
            names_by_pid = {}
            for pay in adv_payments:
                order = pay.pos_order_id
                if order and order.partner_id.id in pid_set:
                    names_by_pid.setdefault(
                        order.partner_id.id, set()).add(order.name)
            all_names = set()
            for names in names_by_pid.values():
                all_names.update(names)
            invoices = Move.search([
                ('type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('company_id', '=', company.id),
                ('invoice_origin', 'in', list(all_names)),
                ('amount_residual', '>', 0.001),
            ]) if all_names else Move
            inv_by_origin = {}
            for inv in invoices:
                inv_by_origin.setdefault(inv.invoice_origin, []).append(inv)
            open_by_pid = {}
            for order in PosOrder.search([
                    ('partner_id', 'in', pids),
                    ('company_id', '=', company.id),
                    ('state', 'not in', ('cancel', 'done'))]):
                open_by_pid.setdefault(order.partner_id.id, set()).add(
                    order.name)
            for pid in pids:
                candidates = names_by_pid.get(pid, set()) - \
                    open_by_pid.get(pid, set())
                used_by_pid[pid] = sum(
                    inv.amount_residual for name in candidates
                    for inv in inv_by_origin.get(name, []))

        # 4) Uso en sesiones abiertas por compañía (2 queries por compañía).
        session_used_by_pid = dict.fromkeys(pids, 0.0)
        company_of = dict.fromkeys(pids, company.id)
        pids_by_company = {}
        for pid, cid in company_of.items():
            pids_by_company.setdefault(cid, []).append(pid)
        for cid, cpids in pids_by_company.items():
            open_sessions = self.env['pos.session'].search([
                ('state', '!=', 'closed'),
                ('config_id.company_id', '=', cid),
            ])
            if not open_sessions:
                continue
            for order in PosOrder.search([
                    ('partner_id', 'in', cpids),
                    ('session_id', 'in', open_sessions.ids),
                    ('company_id', '=', cid),
                    ('state', '!=', 'cancel'),
                    ('is_advance_deposit', '=', False)]):
                amount = sum(
                    value for value in order.payment_ids.filtered(
                        lambda p: p.payment_method_id.is_advance_payment and
                        p.payment_method_id.company_id.id == cid
                    ).mapped('amount') if value > 0.0)
                session_used_by_pid[order.partner_id.id] = \
                    session_used_by_pid.get(order.partner_id.id, 0.0) + amount

        # 5) Cupo por compañía (1 query) y ensamblado.
        company_ids = set(company_of.values())
        overdraft_by_company = {
            company.id: company.advance_overdraft_limit or 0.0
            for company in self.env['res.company'].browse(
                list(company_ids))}
        data = {}
        for partner in partners:
            own = partner.advance_overdraft_limit or 0.0
            company_default = overdraft_by_company.get(
                company_of[partner.id], 0.0) or 0.0
            data[partner.id] = {
                'total': total_by_pid.get(partner.id, 0.0),
                'used': used_by_pid.get(partner.id, 0.0),
                'overdraft': own or company_default,
                'session_used': session_used_by_pid.get(partner.id, 0.0),
            }
        return data

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

    def _compute_advance_ghosts(self):
        """Suma por socio de residuales CxC sin conciliar en asientos de
        sesiones TPV de la compañía activa (1 query, sin N+1)."""
        if not self:
            return
        company = self._get_context_company()
        commercial_ids = self.mapped('commercial_partner_id').ids
        ghost_by_pid = dict.fromkeys(commercial_ids, 0.0)
        session_moves = self.env['pos.session'].search([
            ('config_id.company_id', '=', company.id),
            ('move_id.state', '=', 'posted'),
        ]).mapped('move_id')
        if session_moves:
            lines = self.env['account.move.line'].search([
                ('partner_id.commercial_partner_id', 'in', commercial_ids),
                ('move_id', 'in', session_moves.ids),
                ('company_id', '=', company.id),
                ('reconciled', '=', False),
            ])
            for line in lines:
                commercial_id = line.partner_id.commercial_partner_id.id
                if line.account_id.internal_type != 'receivable':
                    continue
                ghost_by_pid[commercial_id] = \
                    ghost_by_pid.get(commercial_id, 0.0) + \
                    abs(line.amount_residual)
        for partner in self:
            partner.advance_ghosts = ghost_by_pid.get(
                partner.commercial_partner_id.id, 0.0)
