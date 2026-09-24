This module integrates `fieldservice_sale_stock`, `fieldservice_route`, and `fieldservice_availability`, enabling automatic creation and scheduling of FSM orders from sales orders with flexible route assignment and delivery time slot management.

## Confirmation of Sales Orders

When a sales order contains a product that generates an FSM order:
- An FSM location must be set on the sales order.
- Route assignment, FSM person, and route days are optional upon confirmation. If no route or driver is assigned, the order confirms flexibly and creates an unassigned FSM order in the pending orders pool.

## Automatic Scheduling and Delivery Time Ranges

The active delivery time range for any sale order is resolved using a 5-tier hierarchy (see `fieldservice_availability` for details):
1. **Location Seasonal Schedule**
2. **Location Default Schedule**
3. **Route Seasonal Schedule**
4. **Route Default Schedule**
5. **Global Fallback**

This hierarchy is applied universally to all delivery date calculations upon order confirmation:
- **Unset Delivery Dates:** If `commitment_date` and `commitment_date_end` are not set upon confirmation, the system assigns the next available route day (or tomorrow if no route is assigned) and sets the start and end hours resolved from the time range hierarchy.
- **Manual Delivery Dates:** If delivery dates are set manually, the system preserves the selected calendar days and standardizes the start and end hours using the time range hierarchy.
- **Route Validation & Force Schedule:** If a route is assigned, the delivery date is validated against the route's operational days. This validation can be overridden by enabling **Force Schedule** on the route.

## FSM Order Management

- **Postpone Delivery:** Users can postpone an FSM order to the next available route day directly from the FSM order form view.
- **Bidirectional Date Synchronization:** Updating dates on an FSM order automatically synchronizes the corresponding sales order commitment dates and active stock pickings while logging updates in the sales order chatter.