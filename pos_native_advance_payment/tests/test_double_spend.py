# -*- coding: utf-8 -*-
"""Reproduce el doble gasto del mismo saldo a favor dentro de una sesión.

Escenario del reporte: el cliente tiene 2000 disponibles, se hace una venta
de 2000 pagada con Saldo a Favor y, sin cerrar sesión, se hace otra venta de
2000 con el mismo saldo. La segunda debe bloquearse porque el saldo ya se
gastó en la primera (el descuento contable real ocurre al cierre).
"""
from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestDoubleSpendSameSession(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.config = self.env["pos.config"].search(
            [("company_id", "=", self.company.id)], limit=1
        )
        self.assertTrue(self.config, "Debe existir una caja POS")
        self.advance_method = self.env["pos.payment.method"].search(
            [
                ("is_advance_payment", "=", True),
                ("company_id", "=", self.company.id),
            ],
            limit=1,
        )
        self.assertTrue(
            self.advance_method, "Debe existir un método Saldo a Favor"
        )
        self.partner = self.env["res.partner"].create(
            {
                "name": "Carlos Doble Gasto",
                "vat": "9001234504",
                "country_id": self.env.ref("base.co").id,
            }
        )
        # Anticipo real: pago inbound publicado sin conciliar = 2000.
        self._make_advance(self.partner, 2000.0)
        self.assertAlmostEqual(self.partner.pos_advance_balance, 2000.0)
        self.assertAlmostEqual(self.partner.advance_available, 2000.0)
        # Sesión: reutilizar una abierta de la misma caja si existe (el
        # TPV real opera así); si no, crear una (se revierte al final).
        self.session = self.env["pos.session"].search(
            [("config_id", "=", self.config.id), ("state", "!=", "closed")],
            limit=1,
        )
        if not self.session:
            self.session = self.env["pos.session"].create(
                {"config_id": self.config.id}
            )

    def _make_advance(self, partner, amount):
        bank_journal = self.env["account.journal"].search(
            [("type", "=", "bank"), ("company_id", "=", self.company.id)],
            limit=1,
        )
        self.assertTrue(bank_journal, "Debe existir un diario banco")
        pay_method = self.env["account.payment.method"].search(
            [("payment_type", "=", "inbound"), ("code", "=", "manual")],
            limit=1,
        )
        payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": partner.id,
                "amount": amount,
                "journal_id": bank_journal.id,
                "payment_method_id": pay_method.id,
            }
        )
        payment.post()
        return payment

    def _make_order_with_advance(self, name, amount):
        order = self.env["pos.order"].create(
            {
                "name": name,
                "pos_reference": name,
                "session_id": self.session.id,
                "partner_id": self.partner.id,
                "amount_total": amount,
                "amount_tax": 0.0,
                "amount_paid": amount,
                "amount_return": 0.0,
            }
        )
        self.env["pos.payment"].create(
            {
                "amount": amount,
                "payment_method_id": self.advance_method.id,
                "pos_order_id": order.id,
                "payment_date": fields.Datetime.now(),
            }
        )
        return order

    def _make_order_with_advance_for(self, partner, name, amount):
        order = self.env["pos.order"].create(
            {
                "name": name,
                "pos_reference": name,
                "session_id": self.session.id,
                "partner_id": partner.id,
                "amount_total": amount,
                "amount_tax": 0.0,
                "amount_paid": amount,
                "amount_return": 0.0,
            }
        )
        self.env["pos.payment"].create(
            {
                "amount": amount,
                "payment_method_id": self.advance_method.id,
                "pos_order_id": order.id,
                "payment_date": fields.Datetime.now(),
            }
        )
        return order

    def _post_invoice_for(self, partner, order, amount):
        """Factura publicada con residual (lo que nace al facturar la orden)."""
        journal = self.env["account.journal"].search(
            [
                ("type", "=", "sale"),
                ("company_id", "=", self.company.id),
                ("resolution_id", "=", False),
            ],
            limit=1,
        )
        income = self.env["account.account"].search(
            [
                ("user_type_id.type", "=", "other"),
                ("company_id", "=", self.company.id),
            ],
            limit=1,
        ) or self.env["account.account"].search(
            [("company_id", "=", self.company.id)], limit=1
        )
        invoice = self.env["account.move"].create(
            {
                "type": "out_invoice",
                "partner_id": partner.id,
                "journal_id": journal.id,
                "invoice_origin": order.name,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Venta saldo",
                            "quantity": 1,
                            "price_unit": amount,
                            "account_id": income.id,
                        },
                    )
                ],
            }
        )
        invoice.post()
        return invoice

    def _ui_order(self, amount):
        return {
            "statement_ids": [
                [
                    0,
                    0,
                    {
                        "amount": amount,
                        "payment_method_id": self.advance_method.id,
                    },
                ]
            ],
        }

    def test_session_advance_used_counts_first_sale(self):
        """Lo gastado en la sesión debe restar del disponible."""
        self._make_order_with_advance("Test-1", 2000.0)
        used = self.env["pos.order"]._get_session_advance_used(
            self.session, self.partner
        )
        self.assertAlmostEqual(used, 2000.0)

    def test_second_sale_same_session_is_blocked(self):
        """La segunda venta con el mismo saldo debe fallar."""
        self._make_order_with_advance("Test-1", 2000.0)
        order2 = self.env["pos.order"].create(
            {
                "name": "Test-2",
                "pos_reference": "Test-2",
                "session_id": self.session.id,
                "partner_id": self.partner.id,
                "amount_total": 2000.0,
                "amount_tax": 0.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
            }
        )
        with self.assertRaises(ValidationError):
            order2._check_advance_payment_restrictions(
                ui_order=self._ui_order(2000.0)
            )

    def test_exact_math_no_double_count(self):
        """Saldo 4000, venta1 2000: la venta2 de 2000 debe PASAR.

        Simula el estado post-create_from_ui de la venta1 (pago en sesión +
        factura publicada con residual, que es lo que luego evalúa el guard):
        ese consumo NO debe contarse dos veces (una como pago de sesión y
        otra como residual de su factura).
        """
        partner = self.env["res.partner"].create(
            {
                "name": "Exacto Cuatro Mil",
                "vat": "9001234511",
                "country_id": self.env.ref("base.co").id,
            }
        )
        self._make_advance(partner, 4000.0)
        order1 = self._make_order_with_advance_for(
            partner, "Exact-1", 2000.0
        )
        invoice = self._post_invoice_for(partner, order1, 2000.0)
        self.assertGreater(invoice.amount_residual, 0.001)
        order2 = self.env["pos.order"].create(
            {
                "name": "Exact-2",
                "pos_reference": "Exact-2",
                "session_id": self.session.id,
                "partner_id": partner.id,
                "amount_total": 2000.0,
                "amount_tax": 0.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
            }
        )
        # No debe lanzar: la sesión abierta ya cuenta el consumo (2000) y
        # la factura de esa misma orden NO se suma de nuevo.
        order2._check_advance_payment_restrictions(
            ui_order=self._ui_order(2000.0)
        )

    def test_compute_available_discounts_open_sessions(self):
        """advance_available del partner debe incluir el cap de sesión.

        Consistencia compute <-> guard: tras un refresh del TPV el contador
        local desaparece y la UI se refresca vía RPC con estos campos; si no
        descuentan lo ya gastado en la sesión, la pantalla vuelve a ofrecer
        el saldo completo (el guard igual bloquea, pero tarde).
        """
        self._make_order_with_advance("Test-1", 1500.0)
        # Caché ORM: los computes sin `depends` pueden quedar stale en la
        # misma transacción; forzar lectura fresca.
        self.partner.invalidate_cache()
        # Lo gastado en la sesión abierta descuenta del disponible...
        self.assertAlmostEqual(
            self.partner.advance_available, 500.0)
        # ...y el guard del TPV debe ver exactamente lo mismo.
        order2 = self.env["pos.order"].create(
            {
                "name": "Test-2",
                "pos_reference": "Test-2",
                "session_id": self.session.id,
                "partner_id": self.partner.id,
                "amount_total": 600.0,
                "amount_tax": 0.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
            }
        )
        with self.assertRaises(ValidationError):
            order2._check_advance_payment_restrictions(
                ui_order=self._ui_order(600.0)
            )
        # 500 exactos sí pasan (sin redondeos de más).
        order3 = self.env["pos.order"].create(
            {
                "name": "Test-3",
                "pos_reference": "Test-3",
                "session_id": self.session.id,
                "partner_id": self.partner.id,
                "amount_total": 500.0,
                "amount_tax": 0.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
            }
        )
        order3._check_advance_payment_restrictions(
            ui_order=self._ui_order(500.0)
        )

    def test_multisession_cap_same_company(self):
        """Lo gastado en otra sesión ABIERTA también descuenta."""
        self._make_order_with_advance("Test-1", 2000.0)
        config2 = self.config.copy()
        session2 = self.env["pos.session"].create(
            {"config_id": config2.id}
        )
        order_b = self.env["pos.order"].create(
            {
                "name": "Test-B",
                "pos_reference": "Test-B",
                "session_id": session2.id,
                "partner_id": self.partner.id,
                "amount_total": 2000.0,
                "amount_tax": 0.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
            }
        )
        used = self.env["pos.order"]._get_open_sessions_advance_used(
            self.partner, self.company
        )
        self.assertAlmostEqual(used, 2000.0)
        with self.assertRaises(ValidationError):
            order_b._check_advance_payment_restrictions(
                ui_order=self._ui_order(2000.0)
            )
