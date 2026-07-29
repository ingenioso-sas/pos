# AI Agent Context: pos_payment_method_comission

## 1. Overview
This is an Odoo 13 addon created by Ing.Factura S.L. It introduces the ability to calculate internal commissions (merchant fees) on Point of Sale (PoS) payment methods and automatically generate the corresponding accounting journal entries as expenses.

## 2. Technical Architecture & Models

### `pos.payment.method` (Inherited)
Added fields for commission configuration:
- `has_commission` (Boolean): Toggle commission feature.
- `commission_rate` (Float): Percentage-based commission.
- `commission_fixed_amount` (Monetary): Fixed amount commission.
- `commission_journal_id` (Many2one: `account.journal`): Target journal for accounting move.
- `commission_account_id` (Many2one: `account.account`): Expense account for debit.

### `pos.payment` (Inherited)
Added field:
- `commission` (Float): Stores the calculated commission for a specific payment line.

### `pos.order` (Inherited)
Overrides:
- `_payment_fields`: Extracts the `commission` value sent from the JS UI (`ui_paymentline`).
- `_process_order`: Hooked to call `_create_commission_moves` immediately after order creation.
- `_create_commission_moves`: Automatically generates an `account.move` per payment with commission. 
  - **Debit**: `commission_account_id` (Expense).
  - **Credit**: `receivable_account_id` (from the payment method).

### Frontend (JavaScript / QWeb)
- **`pos_payment_method_commission.js`**: Calculates the commission dynamically on the payment screen based on the chosen payment method configuration. Propagates the calculated `commission` inside the paymentline payload to the backend.
- **`pos_payment_method_commission.xml`**: Injects UI elements to display the calculated commission below the payment line and on the receipt.

## 3. Important Notes for AI Developers / Reverse Engineering
- **Currency Handling**: When creating accounting moves, `_prepare_commission_move` converts the commission amount from the pricelist currency to the company's base currency using `currency_id._convert()`.
- **Validation**: `_check_commission_rate` constrains percentage from 0 to 100.
- **Module State**: If asked to modify, remember that accounting models in Odoo 13 rely heavily on `account.move` (not `account.move.line` directly for creation in many cases, though lines are passed in `line_ids`).
- **Dependencies**: Modifying POS JS requires restarting Odoo or clearing browser cache (or using debug=assets).

## 4. Workflows for Bug Fixing / Feature Addition
- If fixing JS: Check `static/src/js/pos_payment_method_commission.js`.
- If modifying accounting logic: Check `_prepare_commission_move` in `models/pos_order.py`.
