# Copyright 2004-2010 OpenERP SA
# Copyright 2017 RGB Consulting S.L. (https://www.rgbconsulting.com)
# Copyright 2018 Lambda IS DOOEL <https://www.lambda-is.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class LoyaltyReward(models.Model):
    _name = "loyalty.reward"

    # name = fields.Char(string="Reward Name", size=32, index=True, required=True)
    name = fields.Char(
        string="Nombre de la recompensa", size=32, index=True, required=True
    )

    type = fields.Selection(
        # selection=[("gift", "Gift"), ("discount", "Discount"), ("resale", "Resale")],
        # string="Type",
        # selection=[("gift", "Regalo"), ("discount", "Descuento"), ("resale", "Reventa")],
        selection=[("discount", "Descuento")],
        string="Tipo",
        required=True,
        # help="Type of the reward",
        help="Selecciona la clase de recompensa que recibirá el cliente.",
        default="discount",
    )
    minimum_points = fields.Float(
        string="Puntos mínimos",
        help="Puntos mínimos requeridos para obtener esta recompensa.",
        # string="Minimum Points",
        # help="Minimum amount of points the customer"
        # " must have to qualify for this reward",
    )
    point_cost = fields.Float(
        # string="Point Cost", help="Cost of the reward per monetary unit " "discounted",
        string="Costo de puntos",
        help="Indica cuánto dinero equivale cada punto que el cliente redime.",
    )
    # discount = fields.Float(help="The discount percentage")
    discount = fields.Float(
        string="% de Descuento",
        help="Indica el porcentaje de descuento aplicado a la compra.",
        )

    discount_rounding = fields.Float(
        string="Redondeo del Valor del Descuento",
        default=0.0,
        help=(
            "Ingresa un valor en dinero para redondear el descuento hacia abajo al múltiplo más cercano.\n"
            "Ejemplo: con $100 COP, un descuento de $150 COP se convierte en $100 COP.\n"
            "Usa 0 para desactivar este redondeo."
        )
    )

    discount_max = fields.Float(
        # string="Discount limit",
        # help="Maximum discounted amount allowed for" "this discount reward",
        string="Límite de descuento",
        help="Monto máximo en dinero que se puede descontar con esta recompensa.",
    )
    loyalty_program_id = fields.Many2one(
        comodel_name="loyalty.program",
        # string="Loyalty Program",
        # help="The Loyalty Program this reward" " belongs to",
        string="Programa de fidelidad",
        help="El programa de lealtad al que pertenece esta recompensa",
    )

    gift_product_id = fields.Many2one(
        comodel_name="product.product",
        domain=[("available_in_pos", "=", True)],
        # string="Gift Product",
        # help="The product given as a reward",
        string="Producto de regalo",
        help="El producto entregado como recompensa.",
    )

    discount_product_id = fields.Many2one(
        comodel_name="product.product",
        domain=[("available_in_pos", "=", True)],
        # string="Discount Product",
        # help="The product used to apply " "discounts",
        string="Producto de descuento",
        help="Producto que representa el descuento en la venta.",
    )

    point_product_id = fields.Many2one(
        comodel_name="product.product",
        domain=[("available_in_pos", "=", True)],
        # string="Point Product",
        # help="Product that represents a point " "that is sold by the customer",
        string="Producto puntual",
        help="Producto que representa un punto que es vendido por el cliente.",
    )

    @api.constrains("type", "gift_product_id")
    def _check_gift_product(self):
        for reward in self:
            if reward.type == "gift" and not reward.gift_product_id:
                raise ValidationError(
                    # _("Gift product field is mandatory for gift rewards")
                    _(
                        "El campo de producto de regalo es obligatorio para las recompensas de regalo."
                    )
                )

    @api.constrains("type", "discount_product_id")
    def _check_discount_product(self):
        for reward in self:
            if reward.type == "discount" and not reward.discount_product_id:
                raise ValidationError(
                    # _("Discount product field is " "mandatory for discount rewards")
                    _(
                        "El campo de producto con descuento es obligatorio para las recompensas con descuento."
                    )
                )

    @api.constrains("type", "point_product_id")
    def _check_point_product(self):
        for reward in self:
            if reward.type == "resale" and not reward.point_product_id:
                raise ValidationError(
                    # _("Point product field is " "mandatory for point resale rewards")
                    _(
                        "El campo de producto de puntos es obligatorio para las recompensas de reventa de puntos."
                    )
                )
