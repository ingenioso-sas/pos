# Copyright (C) 2019 - Today: GRAP (http://www.grap.coop)
# @author: Sylvain LE GAL (https://twitter.com/legalsylvain)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestModule(TransactionCase):
    def setUp(self):
        super(TestModule, self).setUp()

        # Get Registry
        self.PosOrder = self.env["pos.order"]
        self.AccountPayment = self.env["account.payment"]

        # Get Objects
        self.pos_product = self.env["product.product"].create(
            {"name": "Test POS Product"}
        )
        self.pos_product_b = self.env["product.product"].create(
            {"name": "Test POS Product B", "list_price": 25.0}
        )
        self.pricelist = self.env["product.pricelist"].create(
            {
                "name": "Test pricelist",
                "currency_id": self.env.user.company_id.currency_id.id,
                "item_ids": [
                    (
                        0,
                        0,
                        {
                            "applied_on": "3_global",
                            "compute_price": "formula",
                            "base": "list_price",
                        },
                    )
                ],
            }
        )
        self.partner = self.env["res.partner"].create(
            {"name": "Mr. Odoo", "property_product_pricelist": self.pricelist.id}
        )

        # Create a new pos config and open it
        self.pos_config = self.env.ref("point_of_sale.pos_config_main").copy(
            {
                "available_pricelist_ids": [(6, 0, self.pricelist.ids)],
                "pricelist_id": self.pricelist.id,
            }
        )
        self.pos_config.open_session_cb()

    # Test Section
    def test_load_order(self):
        order = self._create_order()
        orders_data = self.PosOrder.search_done_orders_for_pos(
            [], self.pos_config.current_session_id.id
        )
        self.assertEqual(orders_data["total_items"], 1)
        self.assertEqual(len(orders_data["items"]), 1)
        self.assertEqual(orders_data["items"][0]["id"], order.id)
        orders_data2 = self.PosOrder.search_done_orders_for_pos(
            "0006", self.pos_config.current_session_id.id
        )
        self.assertEqual(orders_data2["total_items"], 1)
        self.assertEqual(len(orders_data2["items"]), 1)

        detail_data = order.load_done_order_for_pos()
        self.assertEqual(
            len(detail_data.get("line_ids", [])), 1, "Loading order detail failed"
        )

        self.assertEqual(order.refund_order_qty, 0)
        self.assertFalse(order.action_view_refund_orders().get("res_id", False))

        refund_order_data = order.refund()
        self.assertEqual(order.refund_order_qty, 1)
        self.assertEqual(
            order.action_view_refund_orders().get("res_id"), refund_order_data["res_id"]
        )

    def test_prepare_filters(self):
        prepare_filter = self.PosOrder._prepare_filter_for_pos(
            self.pos_config.current_session_id.id
        )
        self.assertEqual(prepare_filter[0][0], "state")
        query = "myquery"
        prepare_query = self.PosOrder._prepare_filter_query_for_pos(
            self.pos_config.current_session_id.id, query
        )
        self.assertEqual(prepare_query[3][2], query)
        self.assertEqual(prepare_query[4][2], query)
        self.assertEqual(prepare_query[5][2], query)

    def test_full_return(self):
        """Verify full return creates refund linked to original."""
        order = self._create_order(amount=50.0)
        original_total = order.amount_total

        refund_ui_data = {
            "id": "0006-001-0011",
            "to_invoice": False,
            "data": {
                "pricelist_id": self.pricelist.id,
                "user_id": 1,
                "name": "Refund 0006-001-0011",
                "partner_id": self.partner.id,
                "amount_paid": 0,
                "pos_session_id": self.pos_config.current_session_id.id,
                "returned_order_id": order.id,
                "lines": [
                    [
                        0,
                        0,
                        {
                            "product_id": self.pos_product.id,
                            "price_unit": 50.0,
                            "qty": -1,
                            "price_subtotal": -50.0,
                            "price_subtotal_incl": -50.0,
                        },
                    ]
                ],
                "statement_ids": [],
                "creation_date": u"2018-09-27 16:00:00",
                "amount_tax": 0,
                "fiscal_position_id": False,
                "uid": u"00001-001-0002",
                "amount_return": 0,
                "sequence_number": 2,
                "amount_total": -50.0,
            },
        }
        result = self.PosOrder.create_from_ui([refund_ui_data])
        refund_order = self.PosOrder.browse(result[0]["id"])

        self.assertEqual(refund_order.returned_order_id.id, order.id)
        self.assertEqual(order.refund_order_qty, 1)
        self.assertEqual(refund_order.amount_total, -50.0)

    def test_return_with_cash_change(self):
        """Verify return works when original had cash change (vueltas)."""
        order = self._create_order(
            amount=100.0, payment_amount=200.0, return_amount=100.0
        )

        refund_data = {
            "id": "0006-001-0012",
            "to_invoice": False,
            "data": {
                "pricelist_id": self.pricelist.id,
                "user_id": 1,
                "name": "Refund 0006-001-0012",
                "partner_id": self.partner.id,
                "amount_paid": 0,
                "pos_session_id": self.pos_config.current_session_id.id,
                "returned_order_id": order.id,
                "lines": [
                    [
                        0,
                        0,
                        {
                            "product_id": self.pos_product.id,
                            "price_unit": 100.0,
                            "qty": -1,
                            "price_subtotal": -100.0,
                            "price_subtotal_incl": -100.0,
                        },
                    ]
                ],
                "statement_ids": [],
                "creation_date": u"2018-09-27 16:00:00",
                "amount_tax": 0,
                "fiscal_position_id": False,
                "uid": u"00001-001-0003",
                "amount_return": 0,
                "sequence_number": 3,
                "amount_total": -100.0,
            },
        }
        result = self.PosOrder.create_from_ui([refund_data])
        refund_order = self.PosOrder.browse(result[0]["id"])

        self.assertEqual(refund_order.returned_order_id.id, order.id)
        self.assertEqual(refund_order.amount_total, -100.0)
        # Original payment stores the TENDERED amount (2000), not net of change
        self.assertEqual(order.refund_order_qty, 1)

    def test_partial_return(self):
        """Verify partial return of one product from a multi-product order."""
        account_receivable_id = (
            self.env.user.partner_id.property_account_receivable_id.id
        )
        current_session = self.pos_config.current_session_id
        payment_methods = current_session.payment_method_ids
        cash_method = payment_methods.filtered(
            lambda pm: pm.is_cash_count and not pm.split_transactions
        )[0]

        # Create order with 2 products: A (qty 3, price 10) + B (qty 1, price 25)
        order_data = {
            "id": "0006-001-0020",
            "to_invoice": False,
            "data": {
                "pricelist_id": self.pricelist.id,
                "user_id": 1,
                "name": "Order 0006-001-0020",
                "partner_id": self.partner.id,
                "amount_paid": 55.0,
                "pos_session_id": self.pos_config.current_session_id.id,
                "lines": [
                    [
                        0,
                        0,
                        {
                            "product_id": self.pos_product.id,
                            "price_unit": 10.0,
                            "qty": 3,
                            "price_subtotal": 30.0,
                            "price_subtotal_incl": 30.0,
                        },
                    ],
                    [
                        0,
                        0,
                        {
                            "product_id": self.pos_product_b.id,
                            "price_unit": 25.0,
                            "qty": 1,
                            "price_subtotal": 25.0,
                            "price_subtotal_incl": 25.0,
                        },
                    ],
                ],
                "statement_ids": [
                    [
                        0,
                        0,
                        {
                            "journal_id": self.pos_config.journal_id.id,
                            "amount": 55.0,
                            "name": fields.Datetime.now(),
                            "account_id": account_receivable_id,
                            "statement_id": current_session.statement_ids[0].id,
                            "payment_method_id": cash_method.id,
                        },
                    ]
                ],
                "creation_date": u"2018-09-27 15:51:03",
                "amount_tax": 0,
                "fiscal_position_id": False,
                "uid": u"00001-001-0020",
                "amount_return": 0,
                "sequence_number": 1,
                "amount_total": 55.0,
            },
        }
        result = self.PosOrder.create_from_ui([order_data])
        order = self.PosOrder.browse(result[0]["id"])

        # Return only product B (not A)
        refund_data = {
            "id": "0006-001-0021",
            "to_invoice": False,
            "data": {
                "pricelist_id": self.pricelist.id,
                "user_id": 1,
                "name": "Refund 0006-001-0021",
                "partner_id": self.partner.id,
                "amount_paid": 0,
                "pos_session_id": self.pos_config.current_session_id.id,
                "returned_order_id": order.id,
                "lines": [
                    [
                        0,
                        0,
                        {
                            "product_id": self.pos_product_b.id,
                            "price_unit": 25.0,
                            "qty": -1,
                            "price_subtotal": -25.0,
                            "price_subtotal_incl": -25.0,
                        },
                    ]
                ],
                "statement_ids": [],
                "creation_date": u"2018-09-27 16:00:00",
                "amount_tax": 0,
                "fiscal_position_id": False,
                "uid": u"00001-001-0021",
                "amount_return": 0,
                "sequence_number": 2,
                "amount_total": -25.0,
            },
        }
        result2 = self.PosOrder.create_from_ui([refund_data])
        refund_order = self.PosOrder.browse(result2[0]["id"])

        self.assertEqual(refund_order.returned_order_id.id, order.id)
        self.assertEqual(refund_order.amount_total, -25.0)
        # Only product B was returned
        self.assertEqual(len(refund_order.lines), 1)
        self.assertEqual(refund_order.lines[0].product_id.id, self.pos_product_b.id)
        self.assertEqual(refund_order.lines[0].qty, -1)

    def test_return_and_sale_combined_with_fully_refunded_product(self):
        """Verify a combined order (return one product + sell another that was
        already fully refunded) does not raise a misleading duplicate-refund
        error about a sale line."""
        account_receivable_id = (
            self.env.user.partner_id.property_account_receivable_id.id
        )
        current_session = self.pos_config.current_session_id
        payment_methods = current_session.payment_method_ids
        cash_method = payment_methods.filtered(
            lambda pm: pm.is_cash_count and not pm.split_transactions
        )[0]

        # Original order: product A (qty 1, 30.0) + product B (qty 1, 25.0)
        order_data = {
            "id": "0006-001-0060",
            "to_invoice": False,
            "data": {
                "pricelist_id": self.pricelist.id,
                "user_id": 1,
                "name": "Order 0006-001-0060",
                "partner_id": self.partner.id,
                "amount_paid": 55.0,
                "pos_session_id": self.pos_config.current_session_id.id,
                "lines": [
                    [
                        0,
                        0,
                        {
                            "product_id": self.pos_product.id,
                            "price_unit": 30.0,
                            "qty": 1,
                            "price_subtotal": 30.0,
                            "price_subtotal_incl": 30.0,
                        },
                    ],
                    [
                        0,
                        0,
                        {
                            "product_id": self.pos_product_b.id,
                            "price_unit": 25.0,
                            "qty": 1,
                            "price_subtotal": 25.0,
                            "price_subtotal_incl": 25.0,
                        },
                    ],
                ],
                "statement_ids": [
                    [
                        0,
                        0,
                        {
                            "journal_id": self.pos_config.journal_id.id,
                            "amount": 55.0,
                            "name": fields.Datetime.now(),
                            "account_id": account_receivable_id,
                            "statement_id": current_session.statement_ids[0].id,
                            "payment_method_id": cash_method.id,
                        },
                    ]
                ],
                "creation_date": u"2018-09-27 15:51:03",
                "amount_tax": 0,
                "fiscal_position_id": False,
                "uid": u"00001-001-0060",
                "amount_return": 0,
                "sequence_number": 1,
                "amount_total": 55.0,
            },
        }
        result = self.PosOrder.create_from_ui([order_data])
        order = self.PosOrder.browse(result[0]["id"])

        # Full refund of product B
        refund_b = {
            "id": "0006-001-0061",
            "to_invoice": False,
            "data": {
                "pricelist_id": self.pricelist.id,
                "user_id": 1,
                "name": "Refund 0006-001-0061",
                "partner_id": self.partner.id,
                "amount_paid": 0,
                "pos_session_id": self.pos_config.current_session_id.id,
                "returned_order_id": order.id,
                "lines": [
                    [
                        0,
                        0,
                        {
                            "product_id": self.pos_product_b.id,
                            "price_unit": 25.0,
                            "qty": -1,
                            "price_subtotal": -25.0,
                            "price_subtotal_incl": -25.0,
                        },
                    ]
                ],
                "statement_ids": [],
                "creation_date": u"2018-09-27 16:00:00",
                "amount_tax": 0,
                "fiscal_position_id": False,
                "uid": u"00001-001-0061",
                "amount_return": 0,
                "sequence_number": 2,
                "amount_total": -25.0,
            },
        }
        self.PosOrder.create_from_ui([refund_b])

        # Combined order: return product A (negative) + sell product B (positive)
        combined = {
            "id": "0006-001-0062",
            "to_invoice": False,
            "data": {
                "pricelist_id": self.pricelist.id,
                "user_id": 1,
                "name": "Order 0006-001-0062",
                "partner_id": self.partner.id,
                "amount_paid": 15.0,
                "pos_session_id": self.pos_config.current_session_id.id,
                "returned_order_id": order.id,
                "lines": [
                    [
                        0,
                        0,
                        {
                            "product_id": self.pos_product.id,
                            "price_unit": 30.0,
                            "qty": -1,
                            "price_subtotal": -30.0,
                            "price_subtotal_incl": -30.0,
                        },
                    ],
                    [
                        0,
                        0,
                        {
                            "product_id": self.pos_product_b.id,
                            "price_unit": 45.0,
                            "qty": 1,
                            "price_subtotal": 45.0,
                            "price_subtotal_incl": 45.0,
                        },
                    ],
                ],
                "statement_ids": [
                    [
                        0,
                        0,
                        {
                            "journal_id": self.pos_config.journal_id.id,
                            "amount": 15.0,
                            "name": fields.Datetime.now(),
                            "account_id": account_receivable_id,
                            "statement_id": current_session.statement_ids[0].id,
                            "payment_method_id": cash_method.id,
                        },
                    ]
                ],
                "creation_date": u"2018-09-27 17:00:00",
                "amount_tax": 0,
                "fiscal_position_id": False,
                "uid": u"00001-001-0062",
                "amount_return": 0,
                "sequence_number": 3,
                "amount_total": 15.0,
            },
        }
        result3 = self.PosOrder.create_from_ui([combined])
        combined_order = self.PosOrder.browse(result3[0]["id"])
        self.assertEqual(combined_order.returned_order_id.id, order.id)

    def test_mixed_sign_order_rejected(self):
        """Verify a combined order (sale + return in the same order) is
        rejected with UserError."""
        order = self._create_order(amount=50.0)

        mixed = {
            "id": "0006-001-0070",
            "to_invoice": False,
            "data": {
                "pricelist_id": self.pricelist.id,
                "user_id": 1,
                "name": "Order 0006-001-0070",
                "partner_id": self.partner.id,
                "amount_paid": 0,
                "pos_session_id": self.pos_config.current_session_id.id,
                "returned_order_id": order.id,
                "lines": [
                    [
                        0,
                        0,
                        {
                            "product_id": self.pos_product.id,
                            "price_unit": 50.0,
                            "qty": -1,
                            "price_subtotal": -50.0,
                            "price_subtotal_incl": -50.0,
                        },
                    ],
                    [
                        0,
                        0,
                        {
                            "product_id": self.pos_product_b.id,
                            "price_unit": 60.0,
                            "qty": 1,
                            "price_subtotal": 60.0,
                            "price_subtotal_incl": 60.0,
                        },
                    ],
                ],
                "statement_ids": [],
                "creation_date": u"2018-09-27 17:00:00",
                "amount_tax": 0,
                "fiscal_position_id": False,
                "uid": u"00001-001-0070",
                "amount_return": 0,
                "sequence_number": 4,
                "amount_total": 10.0,
            },
        }
        with self.assertRaises(UserError):
            self.PosOrder.create_from_ui([mixed])

    def test_duplicate_return_prevention(self):
        """Verify duplicate full return raises UserError."""
        order = self._create_order(amount=30.0)

        refund_data = {
            "id": "0006-001-0030",
            "to_invoice": False,
            "data": {
                "pricelist_id": self.pricelist.id,
                "user_id": 1,
                "name": "Refund 0006-001-0030",
                "partner_id": self.partner.id,
                "amount_paid": 0,
                "pos_session_id": self.pos_config.current_session_id.id,
                "returned_order_id": order.id,
                "lines": [
                    [
                        0,
                        0,
                        {
                            "product_id": self.pos_product.id,
                            "price_unit": 30.0,
                            "qty": -1,
                            "price_subtotal": -30.0,
                            "price_subtotal_incl": -30.0,
                        },
                    ]
                ],
                "statement_ids": [],
                "creation_date": u"2018-09-27 16:00:00",
                "amount_tax": 0,
                "fiscal_position_id": False,
                "uid": u"00001-001-0030",
                "amount_return": 0,
                "sequence_number": 3,
                "amount_total": -30.0,
            },
        }
        # First return should succeed
        self.PosOrder.create_from_ui([refund_data])

        # Second return with same product should fail
        refund_data["id"] = "0006-001-0031"
        refund_data["data"]["uid"] = "00001-001-0031"
        refund_data["data"]["sequence_number"] = 4
        with self.assertRaises(UserError):
            self.PosOrder.create_from_ui([refund_data])

    def test_partial_then_full_return_prevention(self):
        """Verify partial return + second partial exceeding qty raises error."""
        # Create order with qty 2 of same product
        account_receivable_id = (
            self.env.user.partner_id.property_account_receivable_id.id
        )
        current_session = self.pos_config.current_session_id
        payment_methods = current_session.payment_method_ids
        cash_method = payment_methods.filtered(
            lambda pm: pm.is_cash_count and not pm.split_transactions
        )[0]

        order_data = {
            "id": "0006-001-0040",
            "to_invoice": False,
            "data": {
                "pricelist_id": self.pricelist.id,
                "user_id": 1,
                "name": "Order 0006-001-0040",
                "partner_id": self.partner.id,
                "amount_paid": 20.0,
                "pos_session_id": self.pos_config.current_session_id.id,
                "lines": [
                    [
                        0,
                        0,
                        {
                            "product_id": self.pos_product.id,
                            "price_unit": 10.0,
                            "qty": 2,
                            "price_subtotal": 20.0,
                            "price_subtotal_incl": 20.0,
                        },
                    ]
                ],
                "statement_ids": [
                    [
                        0,
                        0,
                        {
                            "journal_id": self.pos_config.journal_id.id,
                            "amount": 20.0,
                            "name": fields.Datetime.now(),
                            "account_id": account_receivable_id,
                            "statement_id": current_session.statement_ids[0].id,
                            "payment_method_id": cash_method.id,
                        },
                    ]
                ],
                "creation_date": u"2018-09-27 15:51:03",
                "amount_tax": 0,
                "fiscal_position_id": False,
                "uid": u"00001-001-0040",
                "amount_return": 0,
                "sequence_number": 1,
                "amount_total": 20.0,
            },
        }
        result = self.PosOrder.create_from_ui([order_data])
        order = self.PosOrder.browse(result[0]["id"])

        # First partial return: 1 unit
        refund_data = {
            "id": "0006-001-0041",
            "to_invoice": False,
            "data": {
                "pricelist_id": self.pricelist.id,
                "user_id": 1,
                "name": "Refund 0006-001-0041",
                "partner_id": self.partner.id,
                "amount_paid": 0,
                "pos_session_id": self.pos_config.current_session_id.id,
                "returned_order_id": order.id,
                "lines": [
                    [
                        0,
                        0,
                        {
                            "product_id": self.pos_product.id,
                            "price_unit": 10.0,
                            "qty": -1,
                            "price_subtotal": -10.0,
                            "price_subtotal_incl": -10.0,
                        },
                    ]
                ],
                "statement_ids": [],
                "creation_date": u"2018-09-27 16:00:00",
                "amount_tax": 0,
                "fiscal_position_id": False,
                "uid": u"00001-001-0041",
                "amount_return": 0,
                "sequence_number": 2,
                "amount_total": -10.0,
            },
        }
        self.PosOrder.create_from_ui([refund_data])

        # Second partial return: 1 unit (remaining, should succeed)
        refund_data2 = {
            "id": "0006-001-0042",
            "to_invoice": False,
            "data": {
                "pricelist_id": self.pricelist.id,
                "user_id": 1,
                "name": "Refund 0006-001-0042",
                "partner_id": self.partner.id,
                "amount_paid": 0,
                "pos_session_id": self.pos_config.current_session_id.id,
                "returned_order_id": order.id,
                "lines": [
                    [
                        0,
                        0,
                        {
                            "product_id": self.pos_product.id,
                            "price_unit": 10.0,
                            "qty": -1,
                            "price_subtotal": -10.0,
                            "price_subtotal_incl": -10.0,
                        },
                    ]
                ],
                "statement_ids": [],
                "creation_date": u"2018-09-27 17:00:00",
                "amount_tax": 0,
                "fiscal_position_id": False,
                "uid": u"00001-001-0042",
                "amount_return": 0,
                "sequence_number": 3,
                "amount_total": -10.0,
            },
        }
        self.PosOrder.create_from_ui([refund_data2])

        # Third partial return: 1 unit (exceeds, should fail)
        refund_data3 = {
            "id": "0006-001-0043",
            "to_invoice": False,
            "data": {
                "pricelist_id": self.pricelist.id,
                "user_id": 1,
                "name": "Refund 0006-001-0043",
                "partner_id": self.partner.id,
                "amount_paid": 0,
                "pos_session_id": self.pos_config.current_session_id.id,
                "returned_order_id": order.id,
                "lines": [
                    [
                        0,
                        0,
                        {
                            "product_id": self.pos_product.id,
                            "price_unit": 10.0,
                            "qty": -1,
                            "price_subtotal": -10.0,
                            "price_subtotal_incl": -10.0,
                        },
                    ]
                ],
                "statement_ids": [],
                "creation_date": u"2018-09-27 18:00:00",
                "amount_tax": 0,
                "fiscal_position_id": False,
                "uid": u"00001-001-0043",
                "amount_return": 0,
                "sequence_number": 4,
                "amount_total": -10.0,
            },
        }
        with self.assertRaises(UserError):
            self.PosOrder.create_from_ui([refund_data3])

    def test_return_from_multiple_payment_methods(self):
        """Verify returns track multiple payment methods correctly."""
        account_receivable_id = (
            self.env.user.partner_id.property_account_receivable_id.id
        )
        current_session = self.pos_config.current_session_id
        payment_methods = current_session.payment_method_ids
        cash_method = payment_methods.filtered(
            lambda pm: pm.is_cash_count and not pm.split_transactions
        )[0]
        # Get a non-cash method
        other_method = payment_methods.filtered(
            lambda pm: not pm.is_cash_count
        )
        if not other_method:
            other_method = payment_methods[0]

        order_data = {
            "id": "0006-001-0050",
            "to_invoice": False,
            "data": {
                "pricelist_id": self.pricelist.id,
                "user_id": 1,
                "name": "Order 0006-001-0050",
                "partner_id": self.partner.id,
                "amount_paid": 100.0,
                "pos_session_id": self.pos_config.current_session_id.id,
                "lines": [
                    [
                        0,
                        0,
                        {
                            "product_id": self.pos_product.id,
                            "price_unit": 100.0,
                            "qty": 1,
                            "price_subtotal": 100.0,
                            "price_subtotal_incl": 100.0,
                        },
                    ]
                ],
                "statement_ids": [
                    [
                        0,
                        0,
                        {
                            "journal_id": self.pos_config.journal_id.id,
                            "amount": 60.0,
                            "name": fields.Datetime.now(),
                            "account_id": account_receivable_id,
                            "statement_id": current_session.statement_ids[0].id,
                            "payment_method_id": cash_method.id,
                        },
                    ],
                    [
                        0,
                        0,
                        {
                            "journal_id": self.pos_config.journal_id.id,
                            "amount": 40.0,
                            "name": fields.Datetime.now(),
                            "account_id": account_receivable_id,
                            "statement_id": current_session.statement_ids[0].id,
                            "payment_method_id": other_method.id,
                        },
                    ],
                ],
                "creation_date": u"2018-09-27 15:51:03",
                "amount_tax": 0,
                "fiscal_position_id": False,
                "uid": u"00001-001-0050",
                "amount_return": 0,
                "sequence_number": 1,
                "amount_total": 100.0,
            },
        }
        result = self.PosOrder.create_from_ui([order_data])
        order = self.PosOrder.browse(result[0]["id"])

        self.assertTrue(order.payment_ids.filtered(
            lambda p: p.payment_method_id == cash_method
        ))
        self.assertTrue(order.payment_ids.filtered(
            lambda p: p.payment_method_id == other_method
        ))

    def test_prepare_fields_for_pos_includes_refund_qty(self):
        """Verify search_done_orders_for_pos includes refund_order_qty."""
        order = self._create_order(amount=15.0)
        fields_list = self.PosOrder._prepare_fields_for_pos_list()
        self.assertIn("refund_order_qty", fields_list)

        orders_data = self.PosOrder.search_done_orders_for_pos(
            [], self.pos_config.current_session_id.id
        )
        self.assertIn("refund_order_qty", orders_data[0])

    def test_load_done_order_includes_refund_qty(self):
        """Verify load_done_order_for_pos includes refund_order_qty."""
        order = self._create_order(amount=20.0)
        detail_data = order.load_done_order_for_pos()
        self.assertIn("refund_order_qty", detail_data)

    def _create_order(self, amount=0.9, payment_amount=None, return_amount=0):
        account_receivable_id = (
            self.env.user.partner_id.property_account_receivable_id.id
        )
        current_session = self.pos_config.current_session_id
        payment_methods = current_session.payment_method_ids
        cash_method = payment_methods.filtered(
            lambda pm: pm.is_cash_count and not pm.split_transactions
        )
        if not cash_method:
            cash_method = payment_methods[0]
        else:
            cash_method = cash_method[0]
        paid = payment_amount if payment_amount is not None else amount
        order_data = {
            "id": "0006-001-0010",
            "to_invoice": True,
            "data": {
                "pricelist_id": self.pricelist.id,
                "user_id": 1,
                "name": "Order 0006-001-0010",
                "partner_id": self.partner.id,
                "amount_paid": paid,
                "pos_session_id": self.pos_config.current_session_id.id,
                "lines": [
                    [
                        0,
                        0,
                        {
                            "product_id": self.pos_product.id,
                            "price_unit": amount,
                            "qty": 1,
                            "price_subtotal": amount,
                            "price_subtotal_incl": amount,
                        },
                    ]
                ],
                "statement_ids": [
                    [
                        0,
                        0,
                        {
                            "journal_id": self.pos_config.journal_id.id,
                            "amount": paid,
                            "name": fields.Datetime.now(),
                            "account_id": account_receivable_id,
                            "statement_id": current_session.statement_ids[0].id,
                            "payment_method_id": cash_method.id,
                        },
                    ]
                ],
                "creation_date": u"2018-09-27 15:51:03",
                "amount_tax": 0,
                "fiscal_position_id": False,
                "uid": u"00001-001-0001",
                "amount_return": return_amount,
                "sequence_number": 1,
                "amount_total": amount,
            },
        }

        result = self.PosOrder.create_from_ui([order_data])
        order = self.PosOrder.browse(result[0]["id"])
        return order
