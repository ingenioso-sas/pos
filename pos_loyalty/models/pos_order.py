# Copyright 2004-2010 OpenERP SA
# Copyright 2017 RGB Consulting S.L. (https://www.rgbconsulting.com)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.tools import float_round


class PosOrder(models.Model):
    _inherit = "pos.order"

    loyalty_points = fields.Float(
        string="Puntos de lealtad",
        help="La cantidad de puntos de fidelidad otorgados al cliente con este pedido",
        readonly=True,
    )

    def _calculate_loyalty_points_securely(self):
        self.ensure_one()
        if not self.partner_id or not self.session_id.config_id.loyalty_id:
            return 0, 0

        # Security check: do not award points if there is any standard discount
        if any(line.discount > 0 for line in self.lines):
            return 0, 0

        loyalty = self.session_id.config_id.loyalty_id
        rounding = loyalty.rounding
        if rounding <= 0:
            rounding = 1.0

        points_won = 0.0
        points_spent = 0.0
        product_sold = 0.0
        total_sold = 0.0
        reward_discount_total = 0.0

        for line in self.lines:
            # Case 1: The line is a reward, calculate spent points
            if line.reward_id:
                reward = line.reward_id
                if reward.type == "gift":
                    points_spent += float_round(
                        line.qty * reward.point_cost,
                        precision_rounding=rounding,
                        rounding_method="UP",
                    )
                elif reward.type == "discount":
                    discount_amount = abs(line.price_subtotal_incl)
                    reward_discount_total += discount_amount
                    if reward.point_cost > 0:
                        points_spent += float_round(
                            discount_amount / reward.point_cost,
                            precision_rounding=rounding,
                            rounding_method="UP",
                        )
                elif reward.type == "resale":
                    points_spent += abs(line.qty)
                continue  # Go to next line

            # Case 2: The line is a regular product, calculate won points
            rules = self.env["loyalty.rule"].search(
                [
                    ("loyalty_program_id", "=", loyalty.id),
                    "|",
                    ("product_id", "=", line.product_id.id),
                    ("category_id", "in", line.product_id.pos_categ_id.ids),
                ]
            )

            line_points = 0.0
            overridden = False
            rules = sorted(rules, key=lambda r: 1 if r.type == "category" else 0)

            for rule in rules:
                rule_points = 0.0
                rule_points += float_round(
                    line.qty * rule.pp_product,
                    precision_rounding=rounding,
                    rounding_method="UP",
                )
                rule_points += float_round(
                    line.price_subtotal_incl * rule.pp_currency,
                    precision_rounding=rounding,
                    rounding_method="UP",
                )
                line_points += rule_points
                if not rule.cumulative:
                    overridden = True
                    break

            if not overridden:
                product_sold += line.qty
                total_sold += line.price_subtotal_incl

            points_won += line_points

        # Calculate global points on the net amount
        net_total_sold = total_sold - reward_discount_total
        if loyalty.pp_currency > 0 and net_total_sold > 0:
            points_won += float_round(
                net_total_sold / loyalty.pp_currency,
                precision_rounding=rounding,
                rounding_method="UP",
            )

        points_won += float_round(
            product_sold * loyalty.pp_product,
            precision_rounding=rounding,
            rounding_method="UP",
        )
        points_won += float_round(
            loyalty.pp_order, precision_rounding=rounding, rounding_method="UP"
        )

        return points_won, points_spent

    @api.model
    def _order_fields(self, ui_order):
        res = super(PosOrder, self)._order_fields(ui_order)
        res.pop("loyalty_points", None)
        return res

    @api.model
    def create_from_ui(self, orders, draft=False):
        created_orders_data = super(PosOrder, self).create_from_ui(orders, draft=draft)
        order_ids = [o["id"] for o in created_orders_data]
        for order in self.browse(order_ids):
            if order.partner_id:
                points_won, points_spent = order._calculate_loyalty_points_securely()

                total_points_change = points_won - points_spent
                order.write({"loyalty_points": total_points_change})
                if total_points_change != 0:
                    order.partner_id.loyalty_points += total_points_change
        return created_orders_data