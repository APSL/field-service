# Copyright (C) 2019 Open Source Integrators
# Copyright (C) 2019 Serpent consulting Services
# Copyright 2022 Tecnativa - Víctor Martínez
# Copyright 2025 Patryk Pyczko (APSL-Nagarro)<ppyczko@apsl.net>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import datetime, timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, common


class FSMOrderRouteCase(common.TransactionCase):
    def setUp(self):
        super().setUp()
        self.fsm_stage_obj = self.env["fsm.stage"]
        self.fsm_order_obj = self.env["fsm.order"]
        self.fsm_route_obj = self.env["fsm.route"]
        self.fsm_dayroute_obj = self.env["fsm.route.dayroute"]
        self.test_person = self.env.ref("fieldservice.test_person")
        self.test_location = self.env.ref("fieldservice.test_location")
        date = datetime.now()
        self.date = date.replace(microsecond=0)
        self.days = [
            self.env.ref("fieldservice_route.fsm_route_day_0").id,
            self.env.ref("fieldservice_route.fsm_route_day_1").id,
            self.env.ref("fieldservice_route.fsm_route_day_2").id,
            self.env.ref("fieldservice_route.fsm_route_day_3").id,
            self.env.ref("fieldservice_route.fsm_route_day_4").id,
            self.env.ref("fieldservice_route.fsm_route_day_5").id,
            self.env.ref("fieldservice_route.fsm_route_day_6").id,
        ]
        self.fsm_route_id = self.fsm_route_obj.create(
            {
                "name": "Demo Route",
                "max_order": 10,
                "fsm_person_id": self.test_person.id,
                "day_ids": [(6, 0, self.days)],
            }
        )
        self.test_location.fsm_route_id = self.fsm_route_id.id
        self.location_no_route = self.env["fsm.location"].create(
            {
                "name": "No Route Location",
                "owner_id": self.test_location.owner_id.id,
            }
        )

    def _create_order(self, location=None, person=None, date=None):
        """Create an order the same way the web Form does: with
        ``person_id``/``fsm_route_id`` already resolved in ``vals``, so
        ``create()`` manages the dayroute (mirrors what onchange does when
        creating through the UI, see ``test_create_day_route``)."""
        location = location or self.test_location
        person = person or self.test_person
        date = date or self.date
        return self.fsm_order_obj.create(
            {
                "location_id": location.id,
                "fsm_route_id": location.fsm_route_id.id,
                "person_id": person.id,
                "scheduled_date_start": date,
            }
        )

    def test_create_day_route(self):
        order_form = Form(self.fsm_order_obj)
        order_form.location_id = self.test_location
        order_form.scheduled_date_start = self.date
        order = order_form.save()
        self.assertEqual(order.person_id, self.test_person)
        self.assertEqual(order.fsm_route_id, self.test_location.fsm_route_id)
        self.assertEqual(order.dayroute_id.person_id, order.person_id)
        self.assertEqual(order.dayroute_id.date, order.scheduled_date_start.date())
        self.assertEqual(order.dayroute_id.route_id, order.fsm_route_id)

    def test_write_unrelated_field_keeps_dayroute(self):
        """A write() that doesn't touch person/date/route must not
        re-trigger dayroute management (bug A). With the route already at
        capacity, re-running the search on every write kicks the order out
        into a brand new dayroute and orphans the original one — the exact
        duplicate reported in production, e.g. from the writes
        ``fieldservice_calendar`` performs right after create()."""
        self.fsm_route_id.max_order = 1
        order = self._create_order()
        dayroute = order.dayroute_id
        order.write({"description": "<p>irrelevant change</p>"})
        self.assertEqual(order.dayroute_id, dayroute)
        self.assertEqual(
            self.fsm_dayroute_obj.search_count(
                [
                    ("person_id", "=", self.test_person.id),
                    ("date", "=", self.date.date()),
                ]
            ),
            1,
        )

    def test_two_orders_same_day_share_dayroute(self):
        """Two orders for the same technician and day must share a single
        dayroute (the core of P0 #4)."""
        order1 = self._create_order()
        order2 = self._create_order()
        self.assertEqual(order1.dayroute_id, order2.dayroute_id)
        self.assertEqual(
            self.fsm_dayroute_obj.search_count(
                [
                    ("person_id", "=", self.test_person.id),
                    ("date", "=", self.date.date()),
                ]
            ),
            1,
        )

    def test_change_date_moves_and_cleans_dayroute(self):
        """Moving the only order of a dayroute to another day must create/
        reuse the dayroute of the new day and delete the now-empty old one
        (bug B: the cleanup must happen after the order is actually moved)."""
        order = self._create_order()
        old_dayroute = order.dayroute_id
        new_date = self.date + timedelta(days=1)
        order.write({"scheduled_date_start": new_date})
        self.assertNotEqual(order.dayroute_id, old_dayroute)
        self.assertFalse(old_dayroute.exists())
        self.assertEqual(order.dayroute_id.date, new_date.date())

    def test_change_date_keeps_nonempty_dayroute(self):
        """Moving one of several orders off a dayroute must not delete it
        while orders remain."""
        order1 = self._create_order()
        order2 = self._create_order()
        old_dayroute = order1.dayroute_id
        new_date = self.date + timedelta(days=1)
        order1.write({"scheduled_date_start": new_date})
        self.assertTrue(old_dayroute.exists())
        self.assertEqual(old_dayroute.order_ids, order2)

    def test_multi_record_write_no_cross_contamination(self):
        """A single write() on a recordset mixing orders of different
        technicians must resolve the dayroute of each record independently
        (bug A: the shared/mutated ``vals`` dict made every record end up
        pointing at the last computed dayroute)."""
        person2 = self.env["fsm.person"].create({"name": "Test Person 2"})
        location2 = self.env.ref("fieldservice.location_1")
        route2 = self.fsm_route_obj.create(
            {
                "name": "Demo Route 2",
                "max_order": 10,
                "fsm_person_id": person2.id,
                "day_ids": [(6, 0, self.days)],
            }
        )
        location2.fsm_route_id = route2.id

        order1 = self._create_order()
        order2 = self._create_order(location=location2, person=person2)
        new_date = self.date + timedelta(days=1)

        (order1 | order2).write({"scheduled_date_start": new_date})

        self.assertEqual(order1.dayroute_id.person_id, self.test_person)
        self.assertEqual(order2.dayroute_id.person_id, person2)
        self.assertEqual(order1.dayroute_id.date, new_date.date())
        self.assertEqual(order2.dayroute_id.date, new_date.date())
        self.assertNotEqual(order1.dayroute_id, order2.dayroute_id)

    def test_max_order_respected(self):
        """With a finite capacity, a full dayroute must not accept more
        orders: new orders open a new dayroute, and forcing one into the
        full dayroute must raise (bug C: with a real capacity limit, the
        domain must still find/refuse dayroutes correctly)."""
        self.fsm_route_id.max_order = 1
        order1 = self._create_order()
        order2 = self._create_order()
        self.assertNotEqual(order1.dayroute_id, order2.dayroute_id)
        with self.assertRaises(ValidationError):
            order2.dayroute_id = order1.dayroute_id.id

    def test_max_order_zero_unlimited(self):
        """``max_order = 0`` must mean "no limit": several orders for the
        same technician/day must all land on the same single dayroute
        without raising (bug C)."""
        self.fsm_route_id.max_order = 0
        orders = self.fsm_order_obj
        for _i in range(3):
            orders |= self._create_order()
        dayroutes = orders.mapped("dayroute_id")
        self.assertEqual(len(dayroutes), 1)
        self.assertEqual(
            self.fsm_dayroute_obj.search_count(
                [
                    ("person_id", "=", self.test_person.id),
                    ("date", "=", self.date.date()),
                ]
            ),
            1,
        )

    def test_unassign_clears_dayroute(self):
        """Unassigning an order (clearing both technician and scheduled
        date, as the auto-reschedule cron of the downstream product does)
        must detach it from its dayroute and delete the dayroute if it was
        the last order left in it (bug D)."""
        order = self._create_order()
        dayroute = order.dayroute_id
        self.assertTrue(dayroute)
        order.write({"person_id": False, "scheduled_date_start": False})
        self.assertFalse(order.dayroute_id)
        self.assertFalse(dayroute.exists())

    def test_unlink_open_dayroute_clears_person(self):
        """Deleting an open dayroute clears person_id and dayroute_id on its orders."""
        order = self._create_order()
        dayroute = order.dayroute_id

        self.assertTrue(order.person_id)
        dayroute.unlink()

        self.assertFalse(order.person_id)
        self.assertFalse(order.dayroute_id)

    def test_unlink_closed_dayroute_blocked(self):
        """Deleting a dayroute with closed orders must raise a UserError."""
        order = self._create_order()
        dayroute = order.dayroute_id

        closed_stage = self.env["fsm.stage"].search([("is_closed", "=", True)], limit=1)
        if not closed_stage:
            closed_stage = self.env["fsm.stage"].create(
                {"name": "Closed Stage", "is_closed": True, "stage_type": "route"}
            )
        order.stage_id = closed_stage.id

        with self.assertRaises(UserError):
            dayroute.unlink()

    def test_remove_order_from_dayroute_clears_person(self):
        """Removing an order from dayroute (dayroute_id=False) clears person_id."""
        order = self._create_order()
        self.assertTrue(order.person_id)

        order.write({"dayroute_id": False})
        self.assertFalse(order.person_id)
        self.assertFalse(order.dayroute_id)

    def test_remove_last_order_from_dayroute_header_keeps_dayroute_alive(self):
        """Removing the last order via Day Route header write keeps the Day Route
        record alive (preventing UI missing record crashes) while clearing person_id
        on the order.
        """
        order = self._create_order()
        dayroute = order.dayroute_id
        self.assertTrue(dayroute.exists())

        # Simulate removing the line directly from the Day Route form view
        dayroute.write({"order_ids": [(3, order.id)]})

        self.assertTrue(
            dayroute.exists(),
            "Day Route header must not be auto-deleted when edited from its form view.",
        )
        self.assertFalse(order.dayroute_id)
        self.assertFalse(order.person_id)

    def test_manual_duplicate_dayroute_raises_validation_error(self):
        """Manually creating a duplicate dayroute should raise a ValidationError."""
        order = self._create_order()

        with self.assertRaises(ValidationError):
            self.fsm_dayroute_obj.create(
                {
                    "date": order.scheduled_date_start.date(),
                    "person_id": order.person_id.id,
                    "route_id": order.fsm_route_id.id,
                }
            )

    def test_dayroute_fusion_on_write(self):
        """Top-down fusion: Changing dayroute header to an existing
        route merges orders."""
        order1 = self._create_order()
        person2 = self.env["fsm.person"].create({"name": "Test Person 2"})
        order2 = self._create_order(person=person2)

        dayroute1 = order1.dayroute_id
        dayroute2 = order2.dayroute_id

        self.assertNotEqual(dayroute1, dayroute2)

        # Change dayroute2 to match dayroute1
        dayroute2.write({"person_id": self.test_person.id})

        self.assertEqual(order1.dayroute_id, dayroute1)
        self.assertEqual(order2.dayroute_id, dayroute1)
        self.assertEqual(order2.person_id, self.test_person)
        self.assertFalse(dayroute2.exists())

    def test_routeless_dayroute_uniqueness_and_separation(self):
        """Scenario 2 & 4: Ensure route-less dayroutes enforce uniqueness,
        and that a person can have both a routed dayroute and a route-less
        dayroute on the same date.
        """
        order_routed = self._create_order()

        order_routeless = self.fsm_order_obj.create(
            {
                "location_id": self.location_no_route.id,
                "person_id": self.test_person.id,
                "scheduled_date_start": self.date,
            }
        )

        self.assertNotEqual(order_routed.dayroute_id, order_routeless.dayroute_id)
        self.assertEqual(order_routed.dayroute_id.route_id, self.fsm_route_id)
        self.assertFalse(order_routeless.dayroute_id.route_id)

        with self.assertRaises(ValidationError):
            self.fsm_dayroute_obj.create(
                {
                    "date": self.date.date(),
                    "person_id": self.test_person.id,
                    "route_id": False,
                }
            )

    def test_domain_route_matching_and_routeless_orders(self):
        """Test that Day Route order selection domain allows matching route orders
        and route-less orders, but hides orders from different routes or closed orders.
        """
        order_matching = self._create_order()
        dayroute = order_matching.dayroute_id

        order_routeless = self.fsm_order_obj.create(
            {
                "location_id": self.location_no_route.id,
                "scheduled_date_start": self.date,
            }
        )

        route2 = self.fsm_route_obj.create({"name": "Route 2"})
        location_route2 = self.env["fsm.location"].create(
            {
                "name": "Route 2 Location",
                "owner_id": self.test_location.owner_id.id,
                "fsm_route_id": route2.id,
            }
        )
        order_diff_route = self.fsm_order_obj.create(
            {
                "location_id": location_route2.id,
                "scheduled_date_start": self.date,
            }
        )

        domain = [
            ("dayroute_id", "=", False),
            ("is_closed", "=", False),
            "|",
            ("fsm_route_id", "=", dayroute.route_id.id),
            ("fsm_route_id", "=", False),
        ]
        eligible_orders = self.fsm_order_obj.search(domain)

        self.assertIn(order_routeless, eligible_orders)
        self.assertNotIn(order_matching, eligible_orders)
        self.assertNotIn(order_diff_route, eligible_orders)

    def test_domain_excludes_closed_orders(self):
        """Test that closed/completed orders are strictly excluded by the domain."""
        order_closed = self.fsm_order_obj.create(
            {
                "location_id": self.location_no_route.id,
                "scheduled_date_start": self.date,
            }
        )
        closed_stage = self.env["fsm.stage"].search([("is_closed", "=", True)], limit=1)
        if not closed_stage:
            closed_stage = self.env["fsm.stage"].create(
                {
                    "name": "Closed Stage",
                    "is_closed": True,
                    "stage_type": "route",
                }
            )
        order_closed.stage_id = closed_stage.id

        domain = [
            ("dayroute_id", "=", False),
            ("is_closed", "=", False),
            "|",
            ("fsm_route_id", "=", self.fsm_route_id.id),
            ("fsm_route_id", "=", False),
        ]
        eligible_orders = self.fsm_order_obj.search(domain)
        self.assertNotIn(order_closed, eligible_orders)

    def test_dayroute_write_date_preserves_order_times(self):
        """Changing Day Route date top-down must update orders' YYYY-MM-DD
        while strictly preserving each order's specific HH:MM:SS time.
        """
        time1 = self.date.replace(hour=8, minute=15, second=0)
        time2 = self.date.replace(hour=14, minute=45, second=0)

        order1 = self._create_order(date=time1)
        order2 = self._create_order(date=time2)
        dayroute = order1.dayroute_id

        new_date = (self.date + timedelta(days=2)).date()
        dayroute.write({"date": new_date})

        self.assertEqual(order1.scheduled_date_start.date(), new_date)
        self.assertEqual(order1.scheduled_date_start.time(), time1.time())
        self.assertEqual(order2.scheduled_date_start.date(), new_date)
        self.assertEqual(order2.scheduled_date_start.time(), time2.time())

    def test_manual_order_assignment_adopts_dayroute_person_and_date(self):
        """Explicitly assigning an order to a Day Route (write dayroute_id)
        must top-down adopt the Day Route's person and synchronize the scheduled date.
        """
        order_unassigned = self.fsm_order_obj.create(
            {
                "location_id": self.location_no_route.id,
                "scheduled_date_start": self.date,
            }
        )
        self.assertFalse(order_unassigned.person_id)
        self.assertFalse(order_unassigned.dayroute_id)

        target_date = (self.date + timedelta(days=3)).date()
        dayroute = self.fsm_dayroute_obj.create(
            {
                "date": target_date,
                "person_id": self.test_person.id,
                "route_id": self.fsm_route_id.id,
            }
        )

        order_unassigned.write({"dayroute_id": dayroute.id})

        self.assertEqual(order_unassigned.person_id, self.test_person)
        self.assertEqual(order_unassigned.scheduled_date_start.date(), target_date)
