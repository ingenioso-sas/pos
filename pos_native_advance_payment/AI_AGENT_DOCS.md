# AI Agent Context: pos_native_advance_payment

## 1. Overview
This is a custom Odoo 13 addon built from scratch. Its purpose is to bridge native Odoo accounting advance payments (saldos a favor) with the Point of Sale (POS), eliminating the need for parallel wallet modules like `pos_debt_notebook`.

## 2. Technical Architecture & Models

### `res.company` & `res.config.settings`
- Added field `pos_advance_account_id` (Many2one: `account.account`).
- Defines the specific liability/receivable account where customer advances are tracked.
- Added `advance_overdraft_limit` (Float, default 0.0): Límite de sobregiro predeterminado para todos los clientes.

### `res.partner`
- Added computed field `pos_advance_balance` (Float).
- **Computation Logic:** Non-stored computed field (no `@api.depends` — not available in Odoo 13). Queries `account.move.line` for the partner, specifically looking for `reconciled = False`, `account_id = pos_advance_account_id`, and `move_id.state = 'posted'`. Sums up `(credit - debit)`. Since an advance is a liability/credit, positive value means the customer has credit available.
- **Multi-company:** Falls back to `partner.company_id` if set, otherwise uses `self.env.company`.
- **`advance_payment_allowed`** (Boolean, default True): Si el cliente puede usar saldo a favor en TPV.
- **`advance_overdraft_limit`** (Float, default 0.0): Límite de sobregiro individual.
- **`action_pos_advance_history()`**: Devuelve acción de ventana con las últimas 50 líneas de `account.move.line` del cliente en la cuenta de anticipos.

### `pos.payment.method`
- Added field `is_advance_payment` (Boolean).
- Automatically forces `receivable_account_id` to match the company's `pos_advance_account_id` via an `onchange` event (uses `record.company_id` for multi-company safety).
- Clears `receivable_account_id` when unchecking `is_advance_payment`.
- `_sql_constraints` / Python constraint prevents `is_advance_payment` + `is_cash_count` simultaneously.

### `pos.order`
- Overrides `_create_account_move_and_reconcile()`.
- **Auto-reconciliation Hook:** After standard POS accounting moves are generated, the system hunts for new debit lines on the `pos_advance_account_id` and older un-reconciled credit lines (advances) for the same partner.
- **FIFO Partial Matching:** Instead of calling `.reconcile()` on aggregated lines (which fails when totals don't match), it creates individual `account.partial.reconcile` records, matching each new debit line against old credit lines in FIFO order.
- **Refund handling:** Credit lines on the advance account (refunds) are detected and left as new available balance, not reconciled.
- **Server-side validation:** `_check_advance_payment_restrictions()` validates `advance_payment_allowed` before processing payments.
- **Pessimistic Locking:** Uses `SELECT ... FOR UPDATE NOWAIT` to prevent race conditions in multi-session POS environments.
- **Logging:** If a partial reconcile fails, the error is logged at `WARNING` level instead of being silently swallowed.

### Frontend (JavaScript / QWeb)
- **`pos_native_advance_payment.js`**: 
  - Uses `models.load_fields` to bring `pos_advance_balance`, `advance_payment_allowed`, `advance_overdraft_limit` into `res.partner` and `is_advance_payment` into `pos.payment.method`.
  - Overrides `PaymentScreenWidget.validate_order`: validates `advance_payment_allowed`, `advance_overdraft_limit`, and `pos_advance_balance`.
  - Overrides `PaymentScreenWidget.show`: refreshes balance + settings via RPC on every payment screen open.
  - CSS class `.advance-payment-method` added to advance payment buttons for visual distinction.
  - History button click handler: opens backend `action_pos_advance_history` in new tab.
- **`pos_native_advance_payment.xml`**:
  - Extends `ClientDetails` with balance display, history button.
  - Extends `ClientLine` and `ClientListScreenWidget` with balance column.
  - Extends `PaymentScreen` with inline balance display.
- **`pos_native_advance_payment.css`**:
  - Green border/background for advance payment method buttons.
  - Styling for balance info bar in payment screen.

## 3. Important Notes for AI Developers / Reverse Engineering
- **No isolated tables:** Unlike community modules, this module does NOT create its own tracking tables. The truth always resides in `account.move.line`.
- **Partial reconciliation:** The module creates `account.partial.reconcile` records individually for each debit-credit pair. If one fails (e.g., multi-currency), it is logged but does not block the order. The accountant can manually reconcile later.
- **Refund reconciliation:** Refunds that credit the advance account (credit lines) are automatically detected and left untouched — they become new available balance rather than being reconciled against other credits.
- **Pessimistic locking:** The `FOR UPDATE NOWAIT` clause in `pos_order.py` blocks concurrent transactions from using the same advance lines simultaneously. If a lock cannot be acquired, the transaction fails (Odoo's rollback mechanism handles the error gracefully).
- **Dependencies:** Relies heavily on Odoo's standard reconciliation process. If the user accidentally reconciles an advance manually before the POS payment, the POS will see the balance as 0 and block the transaction.
- **Saldo refresh:** The POS fetches the current balance from the server every time the payment screen is shown (`show()`), not only at POS startup.
- **Advance balance report:** `advance.balance.report` transient model with PDF output. Accessible from Accounting → Receivables → Cartera - Saldos a Favor.
- **Pay invoices wizard:** `pay.advance.wizard` transient model. Accessible from Accounting → Receivables → Pagar con Saldo a Favor. Matches credit lines on advance account against open invoices of the same partner.

## 4. Workflows for Bug Fixing
- If balance is incorrect in POS: Check `_compute_pos_advance_balance` in `res_partner.py`. Ensure the account selected in settings has un-reconciled credit lines.
- If JS validation fails: Clear browser cache, ensure `is_advance_payment` is checked on the payment method.
- If partial reconciliation fails in logs: Check the Odoo server logs for `WARNING` messages containing "Partial reconcile failed". Common causes: multi-currency mismatch, account reconciliation settings.
- If a `FOR UPDATE NOWAIT` error occurs: Another POS session is processing the same client's advance simultaneously; retry the order.
