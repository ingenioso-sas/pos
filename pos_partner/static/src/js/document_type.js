odoo.define("pos_partner.document_type", function(require) {
    "use strict";

    var core = require("web.core");
    var rpc = require("web.rpc");
    var screens = require("point_of_sale.screens");

    var _t = core._t;

    // Load marker: if this line is missing from the POS console, the file
    // was not deployed (module not updated) and nothing below can run.
    console.info("[pos_partner] document_type.js loaded");

    // Document type field provided by l10n_co (NOT a dependency of this
    // module, so everything here is defensive: if the field -- or Jorels,
    // which owns this feature -- is present, this module steps aside).
    var FIELD = "l10n_co_document_type";

    // Per-session cache. done=false means "not checked yet".
    var check = {
        done: false,
        available: false,
        selection: [], // [[value, translated label], ...] from fields_get
    };

    function field_exists() {
        return rpc
            .query({
                model: "ir.model.fields",
                method: "search_read",
                domain: [
                    ["model", "=", "res.partner"],
                    ["name", "=", FIELD],
                ],
                fields: ["id"],
                limit: 1,
            })
            .then(function(records) {
                return records && records.length > 0;
            });
    }

    function load_selection() {
        return rpc
            .query({
                model: "res.partner",
                method: "fields_get",
                args: [[FIELD]],
                kwargs: {attributes: ["string", "selection"]},
            })
            .then(function(desc) {
                var info = desc && desc[FIELD];
                return (info && info.selection) || [];
            });
    }

    function ensure_available() {
        // Resolves true when the field exists and its selection is cached.
        // Never rejects: any failure means "feature off".
        if (check.done) {
            return Promise.resolve(check.available);
        }
        return field_exists()
            .then(function(exists) {
                if (!exists) {
                    check.done = true;
                    check.available = false;
                    return false;
                }
                return load_selection().then(function(selection) {
                    check.done = true;
                    check.available = selection.length > 0;
                    check.selection = selection;
                    return check.available;
                });
            })
            .catch(function() {
                check.done = true;
                check.available = false;
                return false;
            });
    }

    function jorels_present($contents) {
        // Jorels (l10n_co_edi_jorels_pos) renders its own select with the
        // same field name. When it is there, Jorels owns this feature and
        // this module must not touch anything (labels, validation, save).
        return $contents.find("select[name='" + FIELD + "']").length > 0;
    }

    function selection_label(value) {
        for (var i = 0; i < check.selection.length; i++) {
            if (check.selection[i][0] === value) {
                return check.selection[i][1];
            }
        }
        return value || "";
    }

    // Native label column is 75px: "Identificación" overflows it and overlaps
    // the value. The width is set inline (not only via main.scss) so the fix
    // applies atomically with the rename even if the CSS bundle is stale.
    var LONG_LABEL_WIDTH = "115px";
    function rename_vat_label($contents) {
        // Only reached when Jorels is absent, so its own Tax ID -> NIT
        // rename can never be clobbered by this one.
        var label = _t("Identification");
        // Widen the whole label column (not just our row) so every label
        // stays right-aligned together and every value starts at the same x.
        // Scoped to forms we renamed: Jorels' short labels keep native width.
        $contents
            .find(".client-details-box")
            .addClass("pos-partner-wide-labels");
        // "Identificación" overflows the native 75px label column, so the
        // renamed rows get a marker class widened in main.scss.
        $contents
            .find("input.detail.vat")
            .closest(".client-detail")
            .addClass("pos-partner-long-label")
            .find("> span.label")
            .text(label)
            .css("width", LONG_LABEL_WIDTH);
        $contents
            .find("span.detail.vat")
            .closest(".client-detail")
            .addClass("pos-partner-long-label")
            .find("> span.label")
            .text(label)
            .css("width", LONG_LABEL_WIDTH);
    }

    function inject_edit($contents, partner) {
        if ($contents.find(".pos-partner-doctype").length) {
            return;
        }
        var $vat = $contents
            .find("input.detail.vat")
            .closest(".client-detail");
        if (!$vat.length) {
            return;
        }
        var current = (partner && partner[FIELD]) || "";
        var options = "<option value=''></option>";
        for (var i = 0; i < check.selection.length; i++) {
            var value = check.selection[i][0];
            var text = check.selection[i][1];
            options +=
                "<option value='" +
                _.escape(value) +
                "'" +
                (value === current ? " selected='selected'" : "") +
                ">" +
                _.escape(text) +
                "</option>";
        }
        $vat.after(
            "<div class='client-detail pos-partner-doctype'>" +
                "<span class='label'>" +
                _.escape(_t("Document Type")) +
                "</span>" +
                "<select class='detail needsclick' name='" +
                FIELD +
                "'>" +
                options +
                "</select>" +
                "</div>"
        );
    }

    function inject_read($contents, partner) {
        if ($contents.find(".pos-partner-doctype").length) {
            return;
        }
        var $box = $contents.find(".client-details-right");
        if (!$box.length) {
            return;
        }
        var value = (partner && partner[FIELD]) || "";
        $box.append(
            "<div class='client-detail pos-partner-doctype'>" +
                "<span class='label'>" +
                _.escape(_t("Document Type")) +
                "</span>" +
                "<span class='detail'>" +
                _.escape(value ? selection_label(value) : "N/A") +
                "</span>" +
                "</div>"
        );
    }

    function backfill_current(self, partner) {
        // Partners loaded at POS start do not carry the field (it is not in
        // static load_fields on purpose: the field may not exist). Fetch it
        // for the partner being edited so the select pre-selects correctly.
        if (!partner || !partner.id || partner[FIELD] !== undefined) {
            return;
        }
        rpc.query({
            model: "res.partner",
            method: "search_read",
            domain: [["id", "=", partner.id]],
            fields: [FIELD],
            limit: 1,
        })
            .then(function(records) {
                if (records && records.length) {
                    partner[FIELD] = records[0][FIELD] || "";
                    var $select = self.$("select[name='" + FIELD + "']");
                    if ($select.length) {
                        $select.val(partner[FIELD]);
                    }
                }
            })
            .catch(function() {
                // Feature stays usable with an empty selection.
            });
    }

    screens.ClientListScreenWidget.include({
        display_client_details: function(visibility, partner, clickpos) {
            var self = this;
            var ret = this._super(visibility, partner, clickpos);
            if (visibility !== "edit" && visibility !== "show") {
                return ret;
            }
            var $contents = this.$(".client-details-contents");
            if (jorels_present($contents)) {
                return ret;
            }
            // VAT label rename applies whenever Jorels is absent, whether or
            // not l10n_co is installed. It is synchronous on purpose: it must
            // not wait for (nor depend on) the document-type detection below.
            rename_vat_label($contents);
            ensure_available()
                .then(function(available) {
                    if (!available) {
                        return;
                    }
                    // Re-check after the async gap.
                    var $c = self.$(".client-details-contents");
                    if (jorels_present($c)) {
                        return;
                    }
                    if (visibility === "edit") {
                        inject_edit($c, partner);
                        backfill_current(self, partner);
                    } else {
                        inject_read($c, partner);
                    }
                })
                .catch(function() {
                    // Never break the client form.
                });
            return ret;
        },
    });
});
