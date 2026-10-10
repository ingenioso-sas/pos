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
            // invoicing configuration. Skipped when the config allows mixing
            // returns and sales.
            if (
                this.returned_order_id &&
                !this.pos.config.disable_mixed_return_sale_restriction
            ) {
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
            // Skipped when the config allows mixing returns and sales.
            if (
                this.order &&
                this.order.returned_order_id &&
                !this.pos.config.disable_mixed_return_sale_restriction &&
                quantity > 0
            ) {
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

    // Deshabilita solo la impresión del PDF de factura en la validación.
    // La facturación contable se mantiene: se envía con to_invoice=true,
    // el backend crea el account.move con normalidad.
    models.PosModel = models.PosModel.extend({
        push_and_invoice_order: function(order) {
            var self = this;
            var invoiced = new Promise(function(
                resolveInvoiced,
                rejectInvoiced
            ) {
                if (!order.get_client()) {
                    rejectInvoiced({
                        code: 400,
                        message: "Missing Customer",
                        data: {},
                    });
                } else {
                    var order_id = self.db.add_order(order.export_as_JSON());
                    self.flush_mutex.exec(function() {
                        var done = new Promise(function(
                            resolveDone,
                            rejectDone
                        ) {
                            var transfer = self._flush_orders(
                                [self.db.get_order(order_id)],
                                { timeout: 30000, to_invoice: true }
                            );
                            transfer.catch(function(error) {
                                rejectInvoiced(error);
                                rejectDone();
                            });
                            transfer.then(function(order_server_id) {
                                if (
                                    order_server_id &&
                                    order_server_id.length
                                ) {
                                    resolveInvoiced(order_server_id);
                                    resolveDone();
                                } else {
                                    rejectInvoiced({
                                        code: 401,
                                        message: "Backend Invoice",
                                        data: { order: order },
                                    });
                                    rejectDone();
                                }
                            });
                        });
                        return done;
                    });
                }
            });
            return invoiced;
        },
    });
});
