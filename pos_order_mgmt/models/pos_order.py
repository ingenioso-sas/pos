# Copyright 2018 GRAP - Sylvain LE GAL
# Copyright 2018 Tecnativa S.L. - David Vidal
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = "pos.order"

    returned_order_id = fields.Many2one(
        comodel_name="pos.order", string="Returned Order", readonly=True,
    )

    returned_order_reference = fields.Char(
        related="returned_order_id.pos_reference",
        string="Reference of the returned Order",
    )

    refund_order_ids = fields.One2many(
        comodel_name="pos.order",
        inverse_name="returned_order_id",
        string="Refund Orders",
        readonly=True,
    )

    refund_order_qty = fields.Integer(
        compute="_compute_refund_order_qty", string="Refund Orders Quantity",
    )

    @api.depends("refund_order_ids")
    def _compute_refund_order_qty(self):
        for order in self:
            order.refund_order_qty = len(order.refund_order_ids)

    def action_view_refund_orders(self):
        self.ensure_one()

        action = self.env.ref("point_of_sale.action_pos_pos_form").read()[0]

        if self.refund_order_qty == 1:
            action["views"] = [
                (self.env.ref("point_of_sale.view_pos_pos_form").id, "form")
            ]
            action["res_id"] = self.refund_order_ids.ids[0]
        else:
            action["domain"] = [("id", "in", self.refund_order_ids.ids)]
        return action

    def refund(self):
        return super(PosOrder, self.with_context(refund=True)).refund()

    @api.returns("self", lambda value: value.id)
    def copy(self, default=None):
        self.ensure_one()
        order = super().copy(default=default)
        if self.env.context.get("refund", False):
            order.returned_order_id = self.id
        return order

    @api.model
    def _prepare_filter_for_pos(self, pos_session_id):
        return [
            ("state", "in", ["paid", "done", "invoiced"]),
        ]

    @api.model
    def _prepare_filter_query_for_pos(self, pos_session_id, query):
        return [
            "|",
            "|",
            "|",
            ("name", "ilike", query),
            ("pos_reference", "ilike", query),
            ("partner_id.display_name", "ilike", query),
            ('lines.product_id.name', 'ilike', query),
        ]

    @api.model
    def _prepare_fields_for_pos_list(self):
        return [
            "name",
            "pos_reference",
            "partner_id",
            "date_order",
            "amount_total",
            "refund_order_qty",
        ]

    @api.model
    def search_done_orders_for_pos(self, query, pos_session_id, page=0):
        session_obj = self.env["pos.session"]
        if not page or page <= 0:
            page = 0
        config = session_obj.browse(pos_session_id).config_id
        condition = self._prepare_filter_for_pos(pos_session_id)
        if not query:
            # Search only this POS orders
            condition += [("config_id", "=", config.id)]
        else:
            # Search globally by criteria
            condition += self._prepare_filter_query_for_pos(pos_session_id, query)
        field_names = self._prepare_fields_for_pos_list()

        page_size = config.iface_load_done_order_max_qty
        total_items = self.search_count(condition)
        result_query = []
        if page_size:
            result_query = self.search_read(
                condition,
                field_names,
                limit=page_size,
                offset=page * page_size,
            )
        return {
            "items": result_query,
            "current_page": page,
            "next_page": (
                page + 1
                if page_size and (page + 1) * page_size < total_items
                else None
            ),
            "prev_page": page - 1 if page > 0 else None,
            "total_items": total_items,
            "total_pages": (
                (total_items + page_size - 1) // page_size if page_size else 0
            ),
            "page_size": page_size,
        }

    @api.model
    def create_from_ui(self, orders, *args, **kwargs):
        for order in orders:
            returned_order_id = order.get("returned_order_id") or \
                order.get("data", {}).get("returned_order_id")
            if returned_order_id:
                self._check_refund_quantities(returned_order_id, order)
        return super().create_from_ui(orders, *args, **kwargs)

    @api.model
    def _check_refund_quantities(self, returned_order_id, order):
        original = self.browse(returned_order_id)
        if not original.exists():
            return
        lines_data = order.get("data", {}).get("lines", [])
        if not lines_data:
            return
        original_qty_by_product = {}
        for line in original.lines:
            original_qty_by_product[line.product_id.id] = (
                original_qty_by_product.get(line.product_id.id, 0) + line.qty
            )
        refunded_qty_by_product = {}
        refunds = original.refund_order_ids.filtered(
            lambda refund: refund.state in ("paid", "done", "invoiced")
        )
        if refunds:
            refunded_lines = self.env["pos.order.line"].search(
                [("order_id", "in", refunds.ids)]
            )
            for refunded_line in refunded_lines:
                refunded_qty_by_product[refunded_line.product_id.id] = (
                    refunded_qty_by_product.get(refunded_line.product_id.id, 0)
                    + abs(refunded_line.qty)
                )
        for line_vals in lines_data:
            line_data = line_vals[2] if isinstance(
                line_vals, (list, tuple)) and len(line_vals) == 3 else line_vals
            product_id = line_data.get("product_id")
            qty = abs(line_data.get("qty", 0))
            if not product_id or not qty:
                continue
            already_refunded = refunded_qty_by_product.get(product_id, 0)
            original_qty = original_qty_by_product.get(product_id, 0)
            if already_refunded + qty > original_qty + 0.001:
                product_name = line_data.get("product_name", product_id)
                raise UserError(_(
                    "The product '%s' from order %s has already been fully "
                    "refunded. Cannot create duplicate refund."
                ) % (product_name, original.pos_reference))

    def _prepare_done_order_for_pos(self):
        self.ensure_one()
        order_lines = []
        payment_lines = []
        for order_line in self.lines:
            order_line = self._prepare_done_order_line_for_pos(order_line)
            order_lines.append(order_line)
        for payment_line in self.payment_ids:
            payment_line = self._prepare_done_order_payment_for_pos(payment_line)
            payment_lines.append(payment_line)
        res = {
            "id": self.id,
            "date_order": self.date_order,
            "pos_reference": self.pos_reference,
            "name": self.name,
            "partner_id": self.partner_id.id,
            "fiscal_position": self.fiscal_position_id.id,
            "line_ids": order_lines,
            "statement_ids": payment_lines,
            "to_invoice": bool(self.to_invoice),
            "user_id": self.user_id.id,
            "employee_id": getattr(self, "employee_id", self.env['hr.employee']).id,
            "returned_order_id": self.returned_order_id.id,
            "returned_order_reference": self.returned_order_reference,
            "refund_order_qty": self.refund_order_qty,
        }
        return res

    def _prepare_done_order_line_for_pos(self, order_line):
        self.ensure_one()
        return {
            "product_id": order_line.product_id.id,
            "product_name": order_line.product_id.display_name,
            "qty": order_line.qty,
            "price_unit": order_line.price_unit,
            "discount": order_line.discount,
            "pack_lot_names": order_line.pack_lot_ids.mapped("lot_name"),
        }

    def _prepare_done_order_payment_for_pos(self, payment_line):
        self.ensure_one()
        return {
            "journal_id": payment_line.pos_order_id.sale_journal,
            "amount": payment_line.amount,
            "payment_method_id": payment_line.payment_method_id.id,
        }

    def load_done_order_for_pos(self):
        self.ensure_one()
        return self._prepare_done_order_for_pos()

    @api.model
    def _order_fields(self, ui_order):
        res = super()._order_fields(ui_order)
        res.update({"returned_order_id": ui_order.get("returned_order_id", False)})
        return res
