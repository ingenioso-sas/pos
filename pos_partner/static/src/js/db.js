odoo.define("pos_partner_pos.DB", function(require) {
    "use strict";

    var PosDB = require("point_of_sale.DB");
    var utils = require("web.utils");

    // Shared normalization for queries and corpus: lowercase, no accents
    // (same utils.unaccent the core uses), no spaces/hyphens/dots so that
    // "171-123 4567" finds "1711234567" on both sides.
    function normalize(str) {
        if (str === undefined || str === null) {
            return "";
        }
        str = utils.unaccent(str.toString().toLowerCase());
        return str.replace(/[\s\-_./()]/g, "");
    }

    PosDB.include({
        _partner_search_string: function(partner) {
            var str = partner.name || "";
            if (partner.barcode) {
                str += "|" + partner.barcode;
            }
            if (partner.address) {
                str += "|" + partner.address;
            }
            if (partner.phone) {
                str += "|" + partner.phone.split(" ").join("");
            }
            if (partner.mobile) {
                str += "|" + partner.mobile.split(" ").join("");
            }
            if (partner.email) {
                str += "|" + partner.email;
            }
            if (partner.vat) {
                str += "|" + partner.vat;
            }
            // Transitional search fallback (I1): kept out of every display,
            // only so partners still pending the vat backfill stay findable.
            if (partner.identificacion) {
                str += "|" + partner.identificacion;
            }
            str =
                String(partner.id) +
                ":" +
                str.replace(":", "").replace(/\n/g, " ") +
                "\n";
            return str;
        },
        _pos_partner_search_string: function(partner) {
            return normalize(this._partner_search_string(partner));
        },
        // Local, stateless search: no RegExp, so no lastIndex pitfalls, and
        // identical results when typing or deleting. Same signature and
        // ordering (partner_sorted) as the core version, honoring this.limit.
        // Empty query returns the full sorted list, like perform_search does.
        search_partner: function(query) {
            query = normalize(query);
            if (!query) {
                return this.get_partners_sorted();
            }
            var results = [];
            var ids = this.partner_sorted || [];
            for (var i = 0, len = ids.length; i < len; i++) {
                var partner = this.get_partner_by_id(ids[i]);
                if (!partner) {
                    continue;
                }
                if (
                    this._pos_partner_search_string(partner).indexOf(query) !==
                    -1
                ) {
                    results.push(partner);
                    if (results.length >= this.limit) {
                        break;
                    }
                }
            }
            return results;
        },
    });

    return PosDB;
});
