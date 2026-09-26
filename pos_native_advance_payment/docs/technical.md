# Technical Documentation — POS Native Advance Payment (Cartera)

## Architecture Overview

This Odoo 13 addon bridges native accounting advance payments with the Point of Sale.  
It reads directly from `account.move.line` — no parallel wallet tables.

```
┌──────────────────────────────────────────────────────────────┐
│                    POS Native Advance Payment                │
├──────────────────────────────────────────────────────────────┤
│  Models                                                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐  │
│  │res_partner│ │res_company│ │pos.payment│ │  pos.order    │  │
│  │          │ │          │ │ .method  │ │              │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────────┘  │
│  ┌──────────────────┐ ┌──────────────────┐                  │
│  │advance.balance   │ │pay.advance.wizard│                  │
│  │.report (wizard)  │ │(wizard)          │                  │
│  └──────────────────┘ └──────────────────┘                  │
├──────────────────────────────────────────────────────────────┤
│  Frontend (Odoo 13 POS — Backbone.js)                       │
│  ┌──────────────────┐ ┌──────────────────┐                  │
│  │PaymentScreen     │ │ClientListScreen  │                  │
│  │Widget            │ │Widget            │                  │
│  └──────────────────┘ └──────────────────┘                  │
└──────────────────────────────────────────────────────────────┘
```

---

## Models

### `res.company` — `pos_advance_account_id`

| Field | Type | Description |
|-------|------|-------------|
| `pos_advance_account_id` | Many2one → `account.account` | Cuenta de anticipos para TPV |
| `advance_overdraft_limit` | Float | Límite de sobregiro por defecto |

**Domain:** `[('reconcile', '=', True), ('internal_type', 'in', ['receivable', 'payable'])]`

**Account type guidance:**

The advance account must be a **liability (payable)** account — customer advances are money the
company owes the customer (in goods, services, or refunds), not an asset. For the Colombian PUC,
use **2805 - Anticipos de Clientes** (e.g. `280505`).

Required account configuration:
1. `internal_type` = `payable` (`Pagado / Cuenta por pagar`)
2. `reconcile` = `True`

`reconcile=True` is mandatory because:
- `_reconcile_advance_lines()` creates `account.partial.reconcile` records between deposit credits
  and consumption debits (FIFO). Partial reconciliations are only allowed on reconcilable accounts.
- `pos_advance_balance` filters on `reconciled=False`; that field is only maintained on reconcilable
  accounts. Without it, all historical lines would count and the available balance would be wrong.
- `amount_residual` (needed for per-deposit/aging tracking) is only maintained on reconcilable accounts.

The `domain` allows both `receivable` and `payable`; ensure only a payable account is selected for
customer advances.

### `res.config.settings`

Related fields mirror those in `res.company`:

| Field | Related |
|-------|---------|
| `pos_advance_account_id` | `company_id.pos_advance_account_id` |
| `advance_overdraft_limit` | `company_id.advance_overdraft_limit` |

### `res.partner` — `pos_advance_balance`

| Field | Type | Description |
|-------|------|-------------|
| `pos_advance_balance` | Float (compute) | Saldo a favor disponible |
| `advance_payment_allowed` | Boolean (default True) | Permite usar saldo a favor en TPV |
| `advance_overdraft_limit` | Float (default 0.0) | Límite de sobregiro individual |

**Computation** (`_compute_pos_advance_balance`):

```python
lines = account.move.line.search([
    ('partner_id', '=', partner.id),
    ('account_id', '=', advance_account.id),
    ('reconciled', '=', False),
    ('move_id.state', '=', 'posted'),
])
balance = sum(line.credit - line.debit for line in lines)
```

Key points:
- Non-stored computed field (no `@api.depends` — `unreconciled_aml_ids` does not exist in Odoo 13).
- Multi-company: uses `partner.company_id` if set, falls back to `self.env.company`.
- Positive balance = customer has credit available (saldo a favor).

**`action_pos_advance_history()`** returns an `ir.actions.act_window` with the last 50 `account.move.line` records for this partner on the advance account.

### `pos.payment.method` — `is_advance_payment`

| Field | Type | Description |
|-------|------|-------------|
| `is_advance_payment` | Boolean | Marca el método como Saldo a Favor |

**Onchange behavior:**
- When checked: sets `receivable_account_id` to the company's `pos_advance_account_id`
- When unchecked: clears `receivable_account_id` if it matched the advance account
- Multi-company safe: uses `record.company_id`

**Constraint:** `is_advance_payment` and `is_cash_count` cannot both be True.

### `pos.order` — Deposit Orders (`is_advance_deposit`)

| Field | Type | Description |
|-------|------|-------------|
| `is_advance_deposit` | Boolean | Marca pedidos de depósito para aumentar saldo a favor del cliente |

**`_create_account_move_and_reconcile()`** — Extended Flow:

```
super() creates standard accounting entries (only for non-deposit orders)
         │
         ▼
  ┌──────────────────┐
  │ Split self:      │
  │ deposit_orders   │
  │ normal_orders    │
  └────────┬─────────┘
           │
     ┌─────┴─────┐
     │           │
     ▼           ▼
  (normal)    (deposit)
     │           │
     ▼           ▼
  super()    _create_deposit_
  + _recon-  accounting()
  cile_       │
  advance_    └─→ Dr. Journal Account (cash)
  lines()         Cr. Advance Account (pos_advance_account_id)
     │
     ▼
  FIFO partial matching
  (same as v1.0)
```

**`_create_deposit_accounting(order)`** — creates the manual Journal Entry:

```python
move_vals = {
    'journal_id': journal.id,
    'ref': '%s DEPÓSITO' % order.name,
    'line_ids': [
        (0, 0, {  # Dr. Cash
            'account_id': cash_account.id,
            'debit': amount,
            'credit': 0.0,
            'partner_id': partner.id,
        }),
        (0, 0, {  # Cr. Advance
            'account_id': advance_account.id,
            'debit': 0.0,
            'credit': amount,
            'partner_id': partner.id,
        }),
    ],
}
```

Key differences from normal orders:
- Does **not** call `super()` for deposit orders — no product invoice, no standard payment moves.
- Manually creates posted move with Dr. Cash / Cr. Advance.
- Links `order.account_move` and `payment.account_move_id` to the new move.
- `_check_advance_payment_restrictions` skips deposit orders.

### `pos.order` — Reconciliation Logic (Normal Orders)

**`_check_advance_payment_restrictions()`**  
Called from `_process_payment_lines()`. Validates:
- Partner is set
- `advance_payment_allowed` is True

Raises `ValidationError` if either fails.

**`_create_account_move_and_reconcile()`** — Extended Flow:

```
super() creates standard accounting entries
         │
         ▼
  ┌──────────────────────────┐
  │ Advance account set?     │──No──→ return res
  │ Payment uses advance?    │
  │ account_move exists?     │
  │ partner exists?          │
  └──────────┬───────────────┘
             │ Yes
             ▼
  ┌──────────────────────────┐
  │ SELECT ... FOR UPDATE    │  ← Pessimistic lock
  │ NOWAIT                   │
  └──────────┬───────────────┘
             │
             ▼
  ┌──────────────────────────┐
  │ Find new_lines on        │
  │ advance account for this │
  │ order + partner          │
  └──────────┬───────────────┘
             │
             ▼
  ┌──────────────────────────┐
  │ Split new_lines:         │
  │  - debit_lines (consumo) │  → reconcile against old credits
  │  - credit_lines (abono)  │  → leave as new available balance
  └──────────┬───────────────┘
             │
             ▼
  ┌──────────────────────────┐
  │ FIFO partial matching    │
  │ For each debit_line:     │
  │   match amount_residual  │
  │   against old credit     │
  │   lines (date asc)       │
  │   Create account.partial │
  │   .reconcile per pair    │
  └──────────────────────────┘
```

**FIFO Partial Matching Details:**

```python
for new_line in debit_lines:
    debit_residual = new_line.amount_residual
    for old_credit in old_lines:
        match_amount = min(debit_residual, abs(credit_residual))
        AccountPartialReconcile.create({
            'debit_move_id': new_line.id,
            'credit_move_id': old_credit.id,
            'amount': match_amount,
        })
        debit_residual -= match_amount
```

Each pair gets its own `account.partial.reconcile` record. This allows matching any amount (no requirement for `total_debit == total_credit`). Failures are logged at `WARNING` level.

---

### Transient Wizards

#### `advance.balance.report`

| Field | Type | Description |
|-------|------|-------------|
| `company_id` | Many2one → `res.company` | Compañía |
| `advance_account_id` | Related (readonly) | Cuenta de anticipos |
| `partner_ids` | Many2many → `res.partner` | Filtro de clientes |
| `include_zero` | Boolean | Incluir saldos en cero |
| `line_ids` | One2many → `advance.balance.report.line` | Resultados |

**Methods:**
- `action_generate()`: Queries unreconciled lines on advance account, groups by partner, creates report lines with aging.
- `action_print_pdf()`: Generates report + renders QWeb PDF.

**`advance.balance.report.line`** — sub-model with:
- `partner_id`, `balance`, `days_oldest`, `aging_range` (computed: ≤30, 31–60, >60)

#### `pay.advance.wizard`

| Field | Type | Description |
|-------|------|-------------|
| `partner_id` | Many2one → `res.partner` (required) | Cliente |
| `advance_balance` | Float (compute) | Saldo disponible |
| `total_selected` | Float (compute) | Total de facturas seleccionadas |
| `company_id` | Many2one → `res.company` | Compañía |
| `invoice_ids` | Many2many → `account.move` | Facturas a pagar |

**Methods:**
- `action_pay()`: Finds unreconciled credit lines on advance account + unreconciled debit lines on receivable account for the selected invoices, then creates `account.partial.reconcile` records between them (FIFO).

---

## Frontend (POS)

### JavaScript — `pos_native_advance_payment.js`

**Loaded fields:**
- `res.partner`: `pos_advance_balance`, `advance_payment_allowed`, `advance_overdraft_limit`
- `pos.payment.method`: `is_advance_payment`

**Custom popup:**

| Widget | Template | Behavior |
|--------|----------|----------|
| `DepositAmountPopup` (`PopupWidget`) | `DepositAmountPopup` | Custom popup with numeric input for deposit amount. Confirms value > 0, calls `options.confirm(value)` on submit. |

Registered with GUI in `gui.Gui.include()` as `popup_widgets['deposit_amount']`.

**Widget extensions:**

| Widget | Method | Behavior |
|--------|--------|----------|
| `PaymentScreenWidget` | `show()` | RPC refresh of balance + settings; renders view |
| `PaymentScreenWidget` | `validate_order()` | Validates: client exists, advance allowed, sufficient balance + overdraft |
| `ProductScreenWidget` | `render()` | Binds click handler to `.o_deposit_button` |
| `ProductScreenWidget` | `_on_deposit_click()` | Checks client selected + empty order, shows `deposit_amount` popup |
| `ProductScreenWidget` | `_process_deposit(amount)` | Calls `create_from_ui` via RPC with `is_advance_deposit: true` |
| `PaymentMethodButton` | `render()` | Adds `.advance-payment-method` CSS class for advance methods |

**Deposit RPC call (`_process_deposit`):**

```javascript
rpc.query({
    model: 'pos.order',
    method: 'create_from_ui',
    args: [[{
        data: {
            amount_paid: amount,
            lines: [],        // sin productos
            partner_id: client.id,
            payments: [{ amount, payment_method_id: cash_method.id }],
            session_id: this.pos.session.id,
            is_advance_deposit: true,
        },
        uid: 'deposit_' + client.id + '_' + timestamp,
    }]],
}).then(function (result) {
    // show success popup
    // refresh client balance via rpc query
});
```

On success, client's `pos_advance_balance` is refreshed via a secondary RPC to `res.partner.read`.

**Validation logic in `validate_order()`:**
1. Sum `amount` from all payment lines where `payment_method.is_advance_payment`
2. If `advance_paid > 0`:
   - Client must exist
   - `advance_payment_allowed` must be `true` (default if undefined)
   - `advance_paid ≤ client.pos_advance_balance + (advance_overdraft_limit or 0)`
3. If validation fails, popup shown with `return` (order not finalized)

**History button:**  
Button in `ClientDetails` template with class `.o_advance_history_btn`.  
On click: reads `data-partner-id` → RPC to `action_pos_advance_history` → opens backend URL in new tab.

### QWeb Templates — `pos_native_advance_payment.xml`

| Template | Extension | Content |
|----------|-----------|---------|
| `DepositAmountPopup` | *(standalone)* | Custom popup with numeric input and confirm/cancel buttons |
| `ProductScreen` | `.product-screen` append | "Abonar a Saldo a Favor" button (`.o_deposit_button`) |
| `ClientDetails` | `.client-details-right` append | Balance display + "Ver movimientos" button |
| `ClientLine` | `tr.client-line` append | Balance column in client list |
| `ClientListScreenWidget` | `table.client-list thead tr` append | "Saldo a Favor" header column |
| `PaymentScreen` | `.payment-screen` append | Balance info bar when client has advance balance |

### CSS — `pos_native_advance_payment.css`

- `.advance-payment-method .payment-button`: green border + light green background
- `.advance-payment-method .payment-button:hover`: darker green background
- `.advance-balance-info .detail`: flex layout, border-top separator
- `.advance-balance-info .label`: bold

---

## Security

File: `security/ir.model.access.csv`

| id | model_id | group_id | permissions |
|----|----------|----------|-------------|
| `access_advance_balance_report` | `advance.balance.report` | `base.group_user` | read |
| `access_pay_advance_wizard` | `pay.advance.wizard` | `account.group_account_manager` | read, write, create |

All other models (`res.partner`, `pos.order`, etc.) use their existing ACLs from `base`, `account`, and `point_of_sale` modules.

---

## Dependencies

- `point_of_sale` — POS core (templates, widgets, `pos.order`)
- `account` — `account.move.line`, `account.partial.reconcile`, `account.payment`

---

## Known Limitations

1. **No `@api.depends`** on `pos_advance_balance`: Odoo 13's `res.partner` lacks `unreconciled_aml_ids`. Field is computed on every access.
2. **Race condition handling:** `FOR UPDATE NOWAIT` prevents concurrent use of the same advance lines, but the failing transaction throws an error that the user sees as a server error. A retry mechanism is not implemented.
3. **Multi-currency:** `account.partial.reconcile` records are created with `amount_currency = 0` and `currency_id = False`. Multi-currency reconciliations may require manual intervention.
4. **JS refresh:** Balance is refreshed when `PaymentScreenWidget.show()` is called, but stale data may appear briefly before the RPC completes.
5. **History button:** Opens the backend tree view in a new tab — does not work in offline POS mode.
6. **Deposit payment method selection:** The deposit button auto-selects the first non-advance payment method with a journal. The cashier cannot choose the payment method from the UI — if a specific method is needed, the advance must be registered from **Contabilidad → Pagos**.
7. **Deposit empty order requirement:** The deposit button is disabled when the current order has product lines. The cashier must finalize the current order before making a deposit.
