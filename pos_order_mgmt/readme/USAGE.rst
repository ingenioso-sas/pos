Once the PoS is loaded, you'll find a shopping trolley icon (🛒) in the top
bar that grants access to the order list screen.

.. image:: ../static/description/order-mgmt-icon.png

There you can find the number of past orders loaded according to your
configuration (see Configuration) as well as the orders you checked out in
the current session:

.. image:: ../static/description/order-mgmt-list.png

#. You can see their totals as well as their custumers if registered.
#. You can reprint their tickets clicking on the printer icon (⎙).
#. You can return them pressing on the arrow icon (↶).
#. You have a search input as well that lets you find past tickets by its
   reference number.

NOTE: You'll need your PoS to be online to be able to search or return a past
ticket.

Custom Business Rules
=====================

Zero-Quantity Line Validation
-----------------------------
When validating or paying an order, the system automatically checks all lines. If any line has a quantity of zero (0), the payment screen displays a warning popup showing the exact product with zero quantity and blocks validation.

Unsynced / Pending Order Modifications
--------------------------------------
If an order fails to synchronize with the backend and remains stored in the browser's local queue (unsynced/failed status):
* Attempting any change on it (e.g. clicking products, numpad buttons, customer button) will trigger a custom confirmation popup explaining the synchronization status and risks.
* The cashier must type exactly ``modificar orden`` in the popup input and confirm to unlock editing.
* If confirmed, the interface is unlocked, allowing them to edit the order. If canceled (or incorrect phrase entered), the action is blocked and a friendly warning popup is shown in the POS without any unhandled JS exceptions or traceback screens.

