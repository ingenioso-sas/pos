# Copyright 2004-2010 OpenERP SA
# Copyright 2017 RGB Consulting S.L. (https://www.rgbconsulting.com)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import math

from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    loyalty_points = fields.Float(
        string="Puntos de lealtad",
        help="La cantidad de puntos de fidelidad otorgados al cliente con este pedido",
        readonly=True,
    )

    def _get_loyalty_points_securely(self):
        self.ensure_one()
        if not self.partner_id or not self.session_id.config_id.loyalty_id:
            return 0

        # Security check: do not award points if there is any discount
        if any(line.discount > 0 for line in self.lines):
            return 0

        loyalty = self.session_id.config_id.loyalty_id
        rounding = loyalty.rounding
        if rounding <= 0:
            rounding = 1.0

        points = 0.0
        product_sold = 0.0
        total_sold = 0.0

        for line in self.lines:
            # Rewards are not eligible for points
            if line.reward_id:
                continue

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
            # Category rules have lower priority
            rules = sorted(rules, key=lambda r: 1 if r.type == "category" else 0)

            for rule in rules:
                rule_points = 0.0
                rule_points += (
                    math.ceil((line.qty * rule.pp_product) / rounding) * rounding
                )
                rule_points += (
                    math.ceil((line.price_subtotal_incl * rule.pp_currency) / rounding)
                    * rounding
                )
                line_points += rule_points
                if not rule.cumulative:
                    overridden = True
                    break

            if not overridden:
                product_sold += line.qty
                total_sold += line.price_subtotal_incl

            points += line_points

        if loyalty.pp_currency > 0:
            points += (
                math.ceil((total_sold / loyalty.pp_currency) / rounding) * rounding
            )
        points += math.ceil((product_sold * loyalty.pp_product) / rounding) * rounding
        points += math.ceil(loyalty.pp_order / rounding) * rounding

        return points

    @api.model
    def _order_fields(self, ui_order):
        res = super(PosOrder, self)._order_fields(ui_order)
        # We remove the loyalty points from here for security reasons.
        # It will be computed on the backend.
        res.pop("loyalty_points", None)
        return res

    @api.model
    def create_from_ui(self, orders, draft=False):
        created_orders_data = super(PosOrder, self).create_from_ui(orders, draft=draft)
        order_ids = [o['id'] for o in created_orders_data]
        for order in self.browse(order_ids):
            if order.partner_id:
                points_won = order._get_loyalty_points_securely()
                # In this version, spent points are negative lines, so we just sum everything.
                # The secure function already filters reward lines for won points.
                points_spent = 0
                for line in order.lines:
                    if line.reward_id and line.price_subtotal_incl < 0:
                        # This logic might need to be adapted if rewards can be returned
                        # or if their cost is calculated differently.
                        # For now, assuming spent points are negative price lines.
                        pass  # Further logic needed to calculate spent points from rewards

                total_points = points_won - points_spent
                order.write({"loyalty_points": total_points})
                if total_points != 0:
                    order.partner_id.loyalty_points += total_points
        return created_orders_data
