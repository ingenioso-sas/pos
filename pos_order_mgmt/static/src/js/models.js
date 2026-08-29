/* Copyright 2018 Tecnativa - David Vidal
   License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl). */

odoo.define("pos_order_mgmt.models", function(require) {
    "use strict";

    var core = require("web.core");
    var _t = core._t;
    var models = require("point_of_sale.models");

    var order_super = models.Order.prototype;

    models.Order = models.Order.extend({
        initialize: function(attr, options) {
            order_super.initialize.apply(this, arguments);
            this.allowed_to_modify = false;
        },
        add_product: function(product, _options) {
            // A return order must only contain returned products. Block any
            // attempt to add a sale product to it, regardless of the electronic
            // invoicing configuration.
            if (this.returned_order_id) {
                this.pos.gui.show_popup("error", {
                    title: _t("No sales on return orders"),
                    body: _t(
                        "You cannot sell products in a return order. " +
                        "Please finish the return and create a new order to sell."
                    ),
                });
                return;
            }
            return order_super.add_product.apply(this, arguments);
        },
        init_from_JSON: function(json) {
            order_super.init_from_JSON.apply(this, arguments);
            this.returned_order_id = json.returned_order_id;
            this.returned_order_reference = json.returned_order_reference;
            this.original_payments = json.original_payments;
            this.user_id = json.user_id;
            this.employee_id = json.employee_id;
        },
        export_as_JSON: function() {
            var res = order_super.export_as_JSON.apply(this, arguments);
            res.returned_order_id = this.returned_order_id;
            res.returned_order_reference = this.returned_order_reference;
            res.original_payments = this.original_payments;
            if (this.returned_order_id) {
                if (this.user_id) {
                    res.user_id = this.user_id;
                }
                if (this.employee_id) {
                    res.employee_id = this.employee_id;
                }
            }
            return res;
        },
        export_for_printing: function() {
            var res = order_super.export_for_printing.apply(this, arguments);
            res.returned_order_id = this.returned_order_id;
            res.returned_order_reference = this.returned_order_reference;
            res.original_payments = this.original_payments;
            return res;
        },
    });

    var orderline_super = models.Orderline.prototype;
    models.Orderline = models.Orderline.extend({
        set_quantity: function(quantity, _keep_price) {
            // A return order can only refund products, so its lines must stay
            // negative. Prevent flipping a return line to a positive quantity.
            if (this.order && this.order.returned_order_id && quantity > 0) {
                this.pos.gui.show_popup("error", {
                    title: _t("No sales on return orders"),
                    body: _t(
                        "You cannot change a return line to a positive " +
                        "quantity. To sell products, create a new order instead."
                    ),
                });
                return;
            }
            return orderline_super.set_quantity.apply(this, arguments);
        },
    });
});
