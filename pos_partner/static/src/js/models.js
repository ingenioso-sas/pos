odoo.define("pos_partner.models", function(require) {
    "use strict";
    var models = require("point_of_sale.models");
    // identificacion is NOT displayed anywhere; it is loaded only as a
    // transitional search fallback (I1) for partners still pending the
    // vat backfill. Every other searched field comes from the core loader.
    models.load_fields("res.partner", ["fecha_nac", "identificacion"]);
});
