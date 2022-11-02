odoo.define("pos_discount_orders", function (require) {
    "use strict";

    var screens = require('point_of_sale.screens');
    var OrderWidget = require("point_of_sale.screens").OrderWidget;
    var models = require("point_of_sale.models");

    var modelDiscount = require('pos_discount.pos_discount');

    modelDiscount.DiscountButton.include({
        apply_discount: function(pc) {
            var order = this.pos.get_order();
            var lines = order.get_orderlines();

            _(lines).each(function (el) {
                el.set_discount(pc);
            });
        },
             
    });

});