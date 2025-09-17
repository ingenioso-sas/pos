# Copyright 2004-2010 OpenERP SA
# Copyright 2017 RGB Consulting S.L. (https://www.rgbconsulting.com)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, fields, models


class LoyaltyProgram(models.Model):
    _name = "loyalty.program"

    name = fields.Char(
        # string="Loyalty Program Name", size=32, index=True, required=True, translate=True
        string="Nombre programa de fidelidad",
        size=32,
        index=True,
        required=True,
        translate=True,
    )
    pp_currency = fields.Float(
        # string=_("Points per currency"),
        # help="Amount of loyalty points given to the " "customer per sold currency",
        string=_("Moneda por punto"),
        help=(
            "Monto en dinero que el cliente debe gastar para ganar 1 punto.\n"
            "Ejemplo: Por cada $1000 vendidos el cliente gana 1 punto."
        ),
        translate=True,
    )
    pp_product = fields.Float(
        # string=_("Points per product"),
        # help="Amount of loyalty points given to the " "customer per product sold",
        string=_("Puntos por producto"),
        help=(
            "Define cuántos puntos gana el cliente por cada producto.\n"
            "Ejemplo: 2 puntos por producto."
        ),
    )
    pp_order = fields.Float(
        # string=_("Points per order"),
        # help="Amount of loyalty points given to the "
        # "customer for each point of sale order","""
        string=_("Puntos por orden"),
        help=(
            "Define cuántos puntos gana el cliente por cada pedido."
            "Ejemplo: 5 puntos por pedido."
        ),
        translate=True,
    )
    rounding = fields.Float(
        # string="Points Rounding",
        string="Redondeo de puntos",
        default=1,
        # help="Loyalty point amounts will be rounded to " "multiples of this value",
        help=(
            "Los puntos ganados se redondean al múltiplo más cercano del valor"
            "configurado aqui. Ejemplo: con redondeo = 5,"
            "si ganas 3 → se ajusta a 5 ; si ganas 7 → se ajusta a 10."
            "Con redondeo = 1, los puntos no cambian (3 → 3, 7 → 7)."
        ),
        translate=True,
    )

    rule_ids = fields.One2many(
        comodel_name="loyalty.rule",
        inverse_name="loyalty_program_id",
        string="Reglas",  # string="Rules"
    )

    reward_ids = fields.One2many(
        comodel_name="loyalty.reward",
        inverse_name="loyalty_program_id",
        string="Recompensas",
        # string="Rewards",
    )
