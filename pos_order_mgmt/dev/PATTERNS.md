# Patterns - pos_order_mgmt

### Extended RPC for POS Data Retrieval

**Category**: HTTP/API | Database

**Evidence**: Used in:
- `models/pos_order.py:100` (`search_done_orders_for_pos`)
- `static/src/js/widgets.js:464` (`search_done_orders`)

**Example**:
```python
@api.model
def search_done_orders_for_pos(self, query, pos_session_id, page=0):
    # Logic to filter and paginate orders for POS frontend
    # ...
    return {
        "items": result_query,
        "total_items": total_items,
        # ... pagination metadata
    }
```

**Cuándo usar**: Cuando el POS necesita datos de modelos que no se cargan completamente al inicio de la sesión, permitiendo búsqueda y paginación en el servidor.

### Action Hooks on Reloaded Orders

**Category**: UI/UX | Frontend

**Evidence**: Used in:
- `static/src/js/widgets.js:256` (`order_list_actions`)
- `static/src/js/widgets.js:275` (`action_print`)

**Example**:
```javascript
action_print: function (order_data, order) {
    this.pos.reloaded_order = order;
    this.gui.show_screen("receipt");
    this.pos.reloaded_order = false;
}
```

**Cuándo usar**: Para realizar acciones específicas sobre registros antiguos recuperados vía RPC, manteniendo el estado original del POS al finalizar la acción.

### Data Inheritance for Refund Traceability

**Category**: Database | Business Logic

**Evidence**: Used in:
- `models/pos_order.py:12` (`returned_order_id`)
- `models/pos_order.py:72` (`copy` method override)

**Example**:
```python
def copy(self, default=None):
    order = super().copy(default=default)
    if self.env.context.get("refund", False):
        order.returned_order_id = self.id
    return order
```

**Cuándo usar**: Para mantener la trazabilidad entre el pedido original y el pedido de devolución/reembolso.
