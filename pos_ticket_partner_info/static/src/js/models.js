/* License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl). */

odoo.define("pos_ticket_partner_info.models", function(require) {
    "use strict";

    // Var models = require("point_of_sale.models");
    var screens = require("point_of_sale.screens");

    var exports = {};

    screens.ReceiptScreenWidget.include({
        init: function(parent, options) {
            this._super(parent, options);
            // Var self = this;

            // Var curr_client = self.pos.get_order().get_client();
        },
        print_web: function() {
            alert(document.querySelector("span.change-value").innerText);
            document.querySelector(".pos .pos-receipt").style.width =
                "100px !important";
            this._super();
        },
        handle_auto_print: function() {
            // Alert("handle_auto_print")
            if (this.should_auto_print() && !this.pos.get_order().is_to_email()) {
                this.print();
                if (this.should_close_immediately()) {
                    this.click_next();
                }
            } else {
                this.lock_screen(false);
            }
        },
        render_change: function() {
            this._super();
            var self = this;
            var cliente = this.pos.get_order().get_client();
            self.phone_client = cliente && cliente.phone ? cliente.phone : "";
            self.name_client = cliente && cliente.name ? cliente.name : "";
        },
    });

    return exports;
});
