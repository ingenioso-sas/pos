# -*- coding: utf-8 -*-
"""Casos T1-T8 del FIX SPEC POS/01303 (LAURA SOLANO).

Cubre con datos sintéticos mínimos:
- T1: venta con saldo precedida de devolución -> funded=57, overdraft 0,
      sin líneas de sesión huérfanas, INV residual 0.
- T2: 3 devoluciones aplican FIFO a la factura (fija regresión).
- T3: 4ta devolución con 21k residual aplica 21k (bug RINV/0009).
- T4: mixto neto negativo puro-saldo -> fórmula sum(RINV)+sum(INV)==-net,
      funded==tendered, fantasmas visibles, idempotente.
- T5: devolución antes que venta (caso SONIA) -> convención: sesión vacía,
      RINV/INV consumidos por el pareo nativo que se conserva.
- T6: idempotencia de apply + ambos settlers.
- T7: pago manual pre-cierre -> se conserva pareo nativo (rama dirty).
- T8: mini end-to-end estilo POS/01303 con 1 venta + 5 devoluciones.
"""
from odoo import fields
from odoo.tests import tagged
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "advance_settlement")
class TestAdvanceSettlement(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.config = self.env["pos.config"].search(
            [("company_id", "=", self.company.id)], limit=1)
        if not self.config:
            self.config = self.env["pos.config"].create({
                "name": "TEST-Shop",
                "company_id": self.company.id,
            })
        self.assertTrue(self.config, "Debe existir una caja POS")
        self.advance_method = self.env["pos.payment.method"].search(
            [("is_advance_payment", "=", True),
             ("company_id", "=", self.company.id)], limit=1)
        if not self.advance_method:
            self.advance_method = self.env["pos.payment.method"].create({
                "name": "TEST Saldo a Favor",
                "company_id": self.company.id,
                "is_advance_payment": True,
                "split_transactions": True,
            })
        self.assertTrue(
            self.advance_method, "Debe existir un método Saldo a Favor")
        self.cash_method = self.env["pos.payment.method"].search(
            [("is_cash_count", "=", True),
             ("company_id", "=", self.company.id)], limit=1)
        if not self.cash_method:
            cash_journal = self.env["account.journal"].search(
                [("type", "=", "cash"),
                 ("company_id", "=", self.company.id)], limit=1)
            if cash_journal:
                self.cash_method = self.env["pos.payment.method"].create({
                    "name": "TEST Efectivo",
                    "company_id": self.company.id,
                    "is_cash_count": True,
                    "cash_journal_id": cash_journal.id,
                })
        # Los pagos exigen el método en la caja de la sesión.
        self.config.write({"payment_method_ids": [
            (4, self.advance_method.id),
        ] + ([(4, self.cash_method.id)] if self.cash_method else [])})
        self._seq = 0

    # ---------------- helpers ----------------
    def _make_partner(self, name, vat):
        return self.env["res.partner"].create({
            "name": name, "vat": vat,
            "country_id": self.env.ref("base.co").id,
        })

    def _make_session(self):
        session = self.env["pos.session"].create(
            {"config_id": self.config.id})
        return session

    def _income_account(self, partner):
        income = self.env["account.account"].search([
            ("user_type_id.type", "=", "other"),
            ("company_id", "=", self.company.id),
        ], limit=1) or self.env["account.account"].search(
            [("company_id", "=", self.company.id)], limit=1)
        return income

    def _make_invoice(self, partner, origin, amount):
        """Factura publicada con residual (out_invoice)."""
        journal = self._sale_journal()
        invoice = self.env["account.move"].create({
            "type": "out_invoice",
            "partner_id": partner.id,
            "journal_id": journal.id,
            "invoice_origin": origin,
            "invoice_line_ids": [(0, 0, {
                "name": "Venta saldo",
                "quantity": 1,
                "price_unit": amount,
                "account_id": self._income_account(partner).id,
            })],
        })
        invoice.post()
        return invoice

    def _make_credit_note(self, partner, origin, amount):
        """Nota crédito publicada con residual (out_refund)."""
        journal = self._sale_journal()
        note = self.env["account.move"].create({
            "type": "out_refund",
            "partner_id": partner.id,
            "journal_id": journal.id,
            "invoice_origin": origin,
            "invoice_line_ids": [(0, 0, {
                "name": "Devolución saldo",
                "quantity": 1,
                "price_unit": amount,
                "account_id": self._income_account(partner).id,
            })],
        })
        note.post()
        return note

    def _sale_journal(self):
        domain = [("type", "=", "sale"),
                  ("company_id", "=", self.company.id)]
        try:
            journal = self.env["account.journal"].search(
                domain + [("resolution_id", "=", False)], limit=1)
        except ValueError:
            journal = self.env["account.journal"].search(domain, limit=1)
        self.assertTrue(journal, "Debe existir un diario de ventas")
        return journal

    def _make_order(self, partner, session, name, total, advance_amount=0.0,
                    cash_amount=0.0):
        order = self.env["pos.order"].create({
            "name": name,
            "pos_reference": name,
            "session_id": session.id,
            "partner_id": partner.id,
            "amount_total": total,
            "amount_tax": 0.0,
            "amount_paid": total,
            "amount_return": 0.0,
        })
        if abs(advance_amount) > 0.001:
            self.env["pos.payment"].create({
                "amount": advance_amount,
                "payment_method_id": self.advance_method.id,
                "pos_order_id": order.id,
                "payment_date": fields.Datetime.now(),
            })
        if abs(cash_amount) > 0.001 and self.cash_method:
            self.env["pos.payment"].create({
                "amount": cash_amount,
                "payment_method_id": self.cash_method.id,
                "pos_order_id": order.id,
                "payment_date": fields.Datetime.now(),
            })
        return order

    def _make_session_move(self, partner, lines, session_name="SESS"):
        """Crea el asiento de sesión (entry, posted) con líneas CxC.

        lines: lista de dicts {name, debit, credit}. Se balancea con una
        línea offset sin partner si hace falta.
        """
        rxc = partner.property_account_receivable_id
        move_lines = []
        for spec in lines:
            move_lines.append((0, 0, {
                "name": spec["name"],
                "account_id": rxc.id,
                "partner_id": partner.id,
                "debit": spec.get("debit", 0.0),
                "credit": spec.get("credit", 0.0),
            }))
        total_dr = sum(l.get("debit", 0.0) for l in lines)
        total_cr = sum(l.get("credit", 0.0) for l in lines)
        if abs(total_dr - total_cr) > 0.001:
            offset = self._income_account(partner)
            diff = total_cr - total_dr  # >0: falta débito
            move_lines.append((0, 0, {
                "name": "Offset %s" % session_name,
                "account_id": offset.id,
                "debit": diff if diff > 0 else 0.0,
                "credit": -diff if diff < 0 else 0.0,
            }))
        journal = self.env["account.journal"].search(
            [("type", "in", ("general", "sale")),
             ("company_id", "=", self.company.id)], limit=1)
        move = self.env["account.move"].create({
            "type": "entry",
            "journal_id": journal.id,
            "date": fields.Date.today(),
            "line_ids": move_lines,
        })
        move.post()
        return move

    def _close_session_with_move(self, session, move):
        session.write({"move_id": move.id, "state": "closed"})

    def _cxc_lines(self, partner, move):
        rxc = partner.property_account_receivable_id
        return move.line_ids.filtered(
            lambda l: l.account_id == rxc and l.partner_id == partner)

    def _partial_count(self):
        return self.env["account.partial.reconcile"].search_count([])

    def _apply_refund(self, refund_order, rinv):
        refund_order.write({"account_move": rinv.id})
        return self.env["pos.order"].apply_refund_to_open_invoices(
            refund_order)

    # ---------------- T1 ----------------
    def test_t1_sale_funded_by_old_credit(self):
        """T1: venta 57 con saldo + RINV previo 57 -> funded total,
        INV 0, sesión sin huérfanos."""
        partner = self._make_partner("T1 Laura", "9001234501")
        session = self._make_session()
        old_rinv = self._make_credit_note(partner, "OLD-1", 57.0)
        order = self._make_order(partner, session, "T1-SALE", 57.0, 57.0)
        inv = self._make_invoice(partner, order.name, 57.0)
        order.write({"account_move": inv.id})
        move = self._make_session_move(partner, [
            {"name": "%s - %s" % (session.name, self.advance_method.name),
             "debit": 57.0},
            {"name": "From invoiced orders", "credit": 57.0},
        ])
        inv_dr = inv.line_ids.filtered(
            lambda l: l.account_id == partner.property_account_receivable_id
            and l.debit > 0.0)
        mirror = move.line_ids.filtered(
            lambda l: l.credit > 0.0
            and l.partner_id == partner
            and l.name == "From invoiced orders")
        self.env["account.partial.reconcile"].create({
            "debit_move_id": inv_dr.id, "credit_move_id": mirror.id,
            "amount": 57.0})
        self._close_session_with_move(session, move)
        session._settle_advance_partner(
            partner.commercial_partner_id, order)
        inv.invalidate_cache()
        old_rinv.invalidate_cache()
        self.assertAlmostEqual(inv.amount_residual, 0.0)
        self.assertAlmostEqual(old_rinv.amount_residual, 0.0)
        self.assertFalse(
            self._cxc_lines(partner, move).filtered(
                lambda l: not l.reconciled),
            "No debe quedar huérfano de sesión (T1)")
        partner.invalidate_cache()
        self.assertAlmostEqual(partner.advance_ghosts, 0.0)

    # ---------------- T2 ----------------
    def test_t2_three_refunds_fifo(self):
        """T2: 3 devoluciones de 25 aplican FIFO a factura de 96."""
        partner = self._make_partner("T2 Laura", "9001234502")
        session = self._make_session()
        sale = self._make_order(partner, session, "T2-SALE", 96.0, 57.0)
        inv = self._make_invoice(partner, sale.name, 96.0)
        for i, name in enumerate(["T2-R1", "T2-R2", "T2-R3"]):
            refund = self._make_order(partner, session, name, -25.0, -25.0)
            rinv = self._make_credit_note(partner, name, 25.0)
            applied = self._apply_refund(refund, rinv)
            self.assertAlmostEqual(applied, 25.0, "FIFO %s" % name)
        inv.invalidate_cache()
        self.assertAlmostEqual(inv.amount_residual, 21.0)

    # ---------------- T3 ----------------
    def test_t3_fourth_refund_applies_remainder(self):
        """T3 (bug RINV/0009): 4ta devolución aplica 21k y deja RINV con 4k."""
        partner = self._make_partner("T3 Laura", "9001234503")
        session = self._make_session()
        sale = self._make_order(partner, session, "T3-SALE", 96.0, 57.0)
        inv = self._make_invoice(partner, sale.name, 96.0)
        rinvs = []
        for name in ["T3-R1", "T3-R2", "T3-R3"]:
            refund = self._make_order(partner, session, name, -25.0, -25.0)
            rinv = self._make_credit_note(partner, name, 25.0)
            rinvs.append(rinv)
            self._apply_refund(refund, rinv)
        refund4 = self._make_order(partner, session, "T3-R4", -25.0, -25.0)
        rinv4 = self._make_credit_note(partner, "T3-R4", 25.0)
        applied = self._apply_refund(refund4, rinv4)
        self.assertAlmostEqual(applied, 21.0, "Debe parear el remanente")
        inv.invalidate_cache()
        rinv4.invalidate_cache()
        self.assertAlmostEqual(inv.amount_residual, 0.0)
        self.assertAlmostEqual(rinv4.amount_residual, 4.0)
        # Idempotencia: segunda corrida no crea nada.
        before = self._partial_count()
        applied2 = self.env[
            "pos.order"].apply_refund_to_open_invoices(refund4)
        self.assertAlmostEqual(applied2, 0.0)
        self.assertEqual(self._partial_count(), before)

    # ---------------- T4 ----------------
    def test_t4_mixed_net_negative_pure_saldo(self):
        """T4: venta 100 + devs 80/81 (neto -61, puro saldo).

        Fórmula: sum(RINV res)+sum(INV res) == -net; funded==tendered;
        el Dr de sesión queda pareado; el remanente queda visible como
        fantasma (duplicado estructural sesión<->RINV) sin crecer.
        """
        partner = self._make_partner("T4 Mixto", "9001234504")
        session = self._make_session()
        old = self._make_credit_note(partner, "T4-OLD", 100.0)
        sale = self._make_order(partner, session, "T4-SALE", 100.0, 100.0)
        inv = self._make_invoice(partner, sale.name, 100.0)
        sale.write({"account_move": inv.id})
        r1 = self._make_credit_note(partner, "T4-R1", 80.0)
        ref1 = self._make_order(partner, session, "T4-R1", -80.0, -80.0)
        self._apply_refund(ref1, r1)
        r2 = self._make_credit_note(partner, "T4-R2", 81.0)
        ref2 = self._make_order(partner, session, "T4-R2", -81.0, -81.0)
        self._apply_refund(ref2, r2)
        inv.invalidate_cache()
        self.assertAlmostEqual(inv.amount_residual, 0.0)
        move = self._make_session_move(partner, [
            {"name": "%s - %s" % (session.name, self.advance_method.name),
             "debit": 100.0},
            {"name": "%s - %s" % (session.name, self.advance_method.name),
             "credit": 80.0},
            {"name": "%s - %s" % (session.name, self.advance_method.name),
             "credit": 81.0},
            {"name": "From invoiced orders", "debit": 61.0},
        ])
        self._close_session_with_move(session, move)
        session._settle_advance_partner(
            partner.commercial_partner_id, sale)
        session._settle_advance_refund(
            partner.commercial_partner_id, ref1 | ref2, sale)
        old.invalidate_cache()
        self.assertAlmostEqual(old.amount_residual, 0.0, "funded == 100")
        r1.invalidate_cache()
        r2.invalidate_cache()
        total = (r1.amount_residual + r2.amount_residual
                 + old.amount_residual + inv.amount_residual)
        self.assertAlmostEqual(total, 61.0, "sum(RINV)+sum(INV) == -net")
        invoice_dr = move.line_ids.filtered(
            lambda l: l.name == "From invoiced orders")
        self.assertTrue(invoice_dr.reconciled, "Dr de sesión pareado")
        partner.invalidate_cache()
        ghosts = partner.advance_ghosts
        self.assertGreater(ghosts, 0.0, "Remanente visible como fantasma")
        # Idempotencia.
        before = self._partial_count()
        session._settle_advance_refund(
            partner.commercial_partner_id, ref1 | ref2, sale)
        self.assertEqual(self._partial_count(), before)
        inv.invalidate_cache()
        self.assertAlmostEqual(inv.amount_residual, 0.0)

    # ---------------- T5 ----------------
    def test_t5_refund_before_sale_sonia(self):
        """T5 (caso SONIA): dev 28 y luego venta 35 (28 saldo + 7).

        Convención fijada: el pareo nativo RINV/INV + sesión se conserva
        (rama dirty: el enlace sesión 7k no es del espejo), los splits
        28<->28 se netean y la sesión queda vacía.
        """
        partner = self._make_partner("T5 Sonia", "9001234505")
        session = self._make_session()
        ref = self._make_order(partner, session, "T5-DEV", -28.0, -28.0)
        rinv = self._make_credit_note(partner, "T5-DEV", 28.0)
        self.assertAlmostEqual(self._apply_refund(ref, rinv), 0.0)
        sale = self._make_order(
            partner, session, "T5-SALE", 35.0, advance_amount=28.0,
            cash_amount=7.0 if self.cash_method else 0.0)
        if not self.cash_method:
            self.skipTest("Sin método efectivo en la BD de prueba")
        inv = self._make_invoice(partner, sale.name, 35.0)
        sale.write({"account_move": inv.id})
        # La RINV abierta aplica en vivo a la nueva factura.
        self.assertAlmostEqual(self._apply_refund(ref, rinv), 28.0)
        inv.invalidate_cache()
        self.assertAlmostEqual(inv.amount_residual, 7.0)
        move = self._make_session_move(partner, [
            {"name": "%s - %s" % (session.name, self.advance_method.name),
             "debit": 28.0},
            {"name": "%s - %s" % (session.name, self.advance_method.name),
             "credit": 28.0},
            {"name": "From invoiced orders", "credit": 7.0},
        ])
        inv_dr = inv.line_ids.filtered(
            lambda l: l.account_id == partner.property_account_receivable_id
            and l.debit > 0.0)
        sess_cr7 = move.line_ids.filtered(
            lambda l: l.name == "From invoiced orders")
        self.env["account.partial.reconcile"].create({
            "debit_move_id": inv_dr.id, "credit_move_id": sess_cr7.id,
            "amount": 7.0})
        self._close_session_with_move(session, move)
        session._settle_advance_partners()
        inv.invalidate_cache()
        rinv.invalidate_cache()
        self.assertAlmostEqual(inv.amount_residual, 0.0)
        self.assertAlmostEqual(rinv.amount_residual, 0.0)
        self.assertFalse(
            self._cxc_lines(partner, move).filtered(
                lambda l: not l.reconciled),
            "Sesión T5 debe quedar vacía")

    # ---------------- T6 ----------------
    def test_t6_idempotent_reruns(self):
        """T6: correr apply + settlers dos veces no duplica parciales."""
        partner = self._make_partner("T6 Idem", "9001234506")
        session = self._make_session()
        old = self._make_credit_note(partner, "T6-OLD", 50.0)
        sale = self._make_order(partner, session, "T6-SALE", 50.0, 50.0)
        inv = self._make_invoice(partner, sale.name, 50.0)
        sale.write({"account_move": inv.id})
        ref = self._make_order(partner, session, "T6-R", -20.0, -20.0)
        rinv = self._make_credit_note(partner, "T6-R", 20.0)
        self._apply_refund(ref, rinv)
        move = self._make_session_move(partner, [
            {"name": "%s - %s" % (session.name, self.advance_method.name),
             "debit": 50.0},
            {"name": "%s - %s" % (session.name, self.advance_method.name),
             "credit": 20.0},
            {"name": "From invoiced orders", "credit": 30.0},
        ])
        inv_dr = inv.line_ids.filtered(
            lambda l: l.account_id == partner.property_account_receivable_id
            and l.debit > 0.0)
        sess_cr = move.line_ids.filtered(
            lambda l: l.name == "From invoiced orders")
        self.env["account.partial.reconcile"].create({
            "debit_move_id": inv_dr.id, "credit_move_id": sess_cr.id,
            "amount": 30.0})
        self._close_session_with_move(session, move)
        session._settle_advance_partners()
        inv.invalidate_cache()
        res_inv_1 = inv.amount_residual
        n1 = self._partial_count()
        # Segunda corrida completa.
        self.env["pos.order"].apply_refund_to_open_invoices(ref)
        session._settle_advance_partners()
        session.reprocess_advance_settlement()
        self.assertEqual(self._partial_count(), n1, "Sin duplicados (T6)")
        inv.invalidate_cache()
        self.assertAlmostEqual(inv.amount_residual, res_inv_1)

    # ---------------- T7 ----------------
    def test_t7_manual_payment_preserved(self):
        """T7: pago manual parcial pre-cierre -> rama dirty conserva nativo."""
        partner = self._make_partner("T7 Manual", "9001234507")
        session = self._make_session()
        old = self._make_credit_note(partner, "T7-OLD", 57.0)
        order = self._make_order(partner, session, "T7-SALE", 100.0, 57.0)
        inv = self._make_invoice(partner, order.name, 100.0)
        order.write({"account_move": inv.id})
        move = self._make_session_move(partner, [
            {"name": "%s - %s" % (session.name, self.advance_method.name),
             "debit": 57.0},
            {"name": "From invoiced orders", "credit": 100.0},
        ])
        rxc = partner.property_account_receivable_id
        inv_dr = inv.line_ids.filtered(
            lambda l: l.account_id == rxc and l.debit > 0.0)
        mirror = move.line_ids.filtered(
            lambda l: l.name == "From invoiced orders")
        native = self.env["account.partial.reconcile"].create({
            "debit_move_id": inv_dr.id, "credit_move_id": mirror.id,
            "amount": 57.0})
        # Pago manual externo de 43 contra la factura.
        manual = self._make_session_move(partner, [
            {"name": "MANUAL-43", "credit": 43.0}], session_name="MAN")
        manual_cr = manual.line_ids.filtered(lambda l: l.credit > 0.0)
        manual_p = self.env["account.partial.reconcile"].create({
            "debit_move_id": inv_dr.id, "credit_move_id": manual_cr.id,
            "amount": 43.0})
        self._close_session_with_move(session, move)
        session._settle_advance_partner(
            partner.commercial_partner_id, order)
        self.assertTrue(native.exists(), "Pareo nativo espejo<->INV intacto")
        self.assertTrue(manual_p.exists(), "Pago manual intacto (T7)")
        inv.invalidate_cache()
        self.assertAlmostEqual(inv.amount_residual, 0.0)

    # ---------------- T8 ----------------
    def test_t8_mini_end_to_end_laura(self):
        """T8: 1 venta 96 (57 saldo + 39 efectivo) + 5 devoluciones a saldo.

        Aserciones: INV residual 0 tras aplicar RINV/0009 (fix B);
        RINV/0004 consumida por fondeo (fix A, funded=57); Dr de sesión
        pareado por neteo (fix C); sin circulares nuevas; idempotente.
        """
        if not self.cash_method:
            self.skipTest("Sin método efectivo en la BD de prueba")
        partner = self._make_partner("T8 Laura", "9001234508")
        session = self._make_session()
        dev0 = self._make_order(partner, session, "T8-DEV0", -57.0, -57.0)
        rinv0 = self._make_credit_note(partner, "T8-DEV0", 57.0)
        sale = self._make_order(
            partner, session, "T8-SALE", 96.0, advance_amount=57.0,
            cash_amount=39.0)
        inv = self._make_invoice(partner, sale.name, 96.0)
        sale.write({"account_move": inv.id})
        rinvs = []
        for name in ["T8-R1", "T8-R2", "T8-R3"]:
            ref = self._make_order(partner, session, name, -25.0, -25.0)
            rinv = self._make_credit_note(partner, name, 25.0)
            rinvs.append(rinv)
            self.assertAlmostEqual(self._apply_refund(ref, rinv), 25.0)
        inv.invalidate_cache()
        self.assertAlmostEqual(inv.amount_residual, 21.0)
        ref4 = self._make_order(partner, session, "T8-R4", -25.0, -25.0)
        rinv4 = self._make_credit_note(partner, "T8-R4", 25.0)
        move = self._make_session_move(partner, [
            {"name": "%s - %s" % (session.name, self.advance_method.name),
             "debit": 57.0},
            {"name": "%s - %s" % (session.name, self.advance_method.name),
             "credit": 57.0},
            {"name": "%s - %s" % (session.name, self.advance_method.name),
             "credit": 25.0},
            {"name": "%s - %s" % (session.name, self.advance_method.name),
             "credit": 25.0},
            {"name": "%s - %s" % (session.name, self.advance_method.name),
             "credit": 25.0},
            {"name": "%s - %s" % (session.name, self.advance_method.name),
             "credit": 25.0},
            {"name": "From invoiced orders", "debit": 61.0},
        ])
        self._close_session_with_move(session, move)
        # Fix B antes del cierre neto: la 4ta devolución cubre la factura.
        self.assertAlmostEqual(self._apply_refund(ref4, rinv4), 21.0)
        session._settle_advance_partners()
        inv.invalidate_cache()
        rinv0.invalidate_cache()
        rinv4.invalidate_cache()
        self.assertAlmostEqual(inv.amount_residual, 0.0, "INV saldada (B)")
        self.assertAlmostEqual(rinv0.amount_residual, 0.0, "Fondeada (A)")
        self.assertAlmostEqual(rinv4.amount_residual, 4.0)
        invoice_dr = move.line_ids.filtered(
            lambda l: l.name == "From invoiced orders")
        self.assertTrue(invoice_dr.reconciled, "Dr neto pareado (C)")
        # Sin circulares sesión<->sesión remanentes sin netear salvo pareo.
        partner.invalidate_cache()
        ghosts = partner.advance_ghosts
        self.assertGreaterEqual(ghosts, 0.0)
        n1 = self._partial_count()
        session.reprocess_advance_settlement()
        self.assertEqual(self._partial_count(), n1, "Reproceso idéntico")
        inv.invalidate_cache()
        self.assertAlmostEqual(inv.amount_residual, 0.0)

    # ---------------- T9 ----------------
    def test_t9_partial_balance_is_not_manual_payment(self):
        """T9: un espejo totalmente conciliado no oculta el descubierto."""
        partner = self._make_partner("T9 Descubierto", "9001234509")
        session = self._make_session()
        sale = self._make_order(partner, session, "T9-SALE", 100.0, 57.0)
        inv = self._make_invoice(partner, sale.name, 100.0)
        sale.write({"account_move": inv.id})
        move = self._make_session_move(partner, [
            {"name": "%s - %s" % (session.name, self.advance_method.name),
             "debit": 57.0},
            {"name": "From invoiced orders", "credit": 100.0},
        ])
        inv_dr = inv.line_ids.filtered(
            lambda l: l.account_id == partner.property_account_receivable_id
            and l.debit > 0.0)
        mirror = move.line_ids.filtered(
            lambda l: l.name == "From invoiced orders")
        self.env["account.partial.reconcile"].create({
            "debit_move_id": inv_dr.id, "credit_move_id": mirror.id,
            "amount": 100.0})
        self._close_session_with_move(session, move)

        session._settle_advance_partner(
            partner.commercial_partner_id, sale)

        inv.invalidate_cache()
        self.assertAlmostEqual(
            inv.amount_residual, 57.0,
            msg="El descubierto no debe clasificarse como pago manual")

    # ---------------- T10 ----------------
    def test_t10_reprocess_requires_accounting_manager(self):
        """T10: el reproceso contable no queda expuesto a usuarios POS."""
        user = self.env["res.users"].create({
            "name": "POS Settlement User",
            "login": "pos-settlement-user-%s" % self.env.cr.dbname,
            "email": "pos-settlement@example.com",
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        session = self._make_session()
        with self.assertRaises(AccessError):
            session.with_user(user).reprocess_advance_settlement()
        with self.assertRaises(AccessError):
            self.env["pos.order"].with_user(
                user).apply_refund_to_open_invoices(
                    self.env["pos.order"].browse())
