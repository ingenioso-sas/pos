odoo.define("pos_partner.models", function(require) {
    "use strict";
    var models = require("point_of_sale.models");
    models.load_fields("res.partner", ["fecha_nac", "identificacion"]);
});
