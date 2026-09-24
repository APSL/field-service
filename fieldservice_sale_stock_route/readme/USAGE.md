## Configuration

Before creating sales orders, you can configure delivery schedules:

1. Navigate to **Field Service > Configuration > Availability > Delivery Time Ranges**.
2. Create time ranges (e.g., `08:00` to `16:00`). You can leave them as year-round defaults or specify seasonal date windows.
3. Assign time ranges directly to **FSM Locations** or **FSM Routes**. If left unassigned, the system will fall back to global schedules or default date times.

---

## Operating Flow

1. Navigate to **Sales > Orders** and create a new sales order.
2. Select the **Customer** and **FSM Location**.
3. Add a product configured with Field Service tracking (`field_service_tracking` set to create an FSM order).
4. In the **Other Info** tab, set the **Delivery Date** and **Delivery End Date** fields, or leave them empty:
   - If left empty, the system automatically assigns the next available route day (or tomorrow if no route is assigned).
   - If set manually, the system preserves the selected calendar dates.
   - In both cases, start and end hours are standardized using the 5-tier delivery schedule hierarchy (Location Seasonal ⟶ Location Default ⟶ Route Seasonal ⟶ Route Default ⟶ Global Fallback).
5. Click **Confirm**.
   - If an assigned route has restricted operational days, the system validates the selected date unless **Force Schedule** is enabled on the route.
   - If no route or driver is assigned, the order confirms and creates an unassigned FSM order in the pending orders pool.
6. Open the generated **FSM Order**:
   - Schedule details reflect the delivery dates computed from the sales order.
   - Click **Postpone Delivery** in the header to reschedule the order to the next available route day.
   - Updating schedule dates on the FSM order automatically updates the sales order commitment dates and open stock pickings.