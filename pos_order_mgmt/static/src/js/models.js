/* Copyright 2018 Tecnativa - David Vidal
   License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl). */

odoo.define("pos_order_mgmt.models", function(require) {
    "use strict";

    var models = require("point_of_sale.models");

    var order_super = models.Order.prototype;

    models.Order = models.Order.extend({
        init_from_JSON: function(json) {
            order_super.init_from_JSON.apply(this, arguments);
            this.returned_order_id = json.returned_order_id;
            this.returned_order_reference = json.returned_order_reference;
            this.original_payments = json.original_payments;
            this.user_id = json.user_id;
            this.employee_id = json.employee_id;
            this.to_electronic_invoice = json.to_electronic_invoice;
        },
        export_as_JSON: function() {
            var res = order_super.export_as_JSON.apply(this, arguments);
            res.returned_order_id = this.returned_order_id;
            res.returned_order_reference = this.returned_order_reference;
            res.original_payments = this.original_payments;
            res.to_electronic_invoice = this.to_electronic_invoice;
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
            res.to_electronic_invoice = this.to_electronic_invoice;
            return res;
        },
    });
});
