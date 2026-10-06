# Copyright 2025 Patryk Pyczko (APSL-Nagarro)<ppyczko@apsl.net>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import datetime

from odoo.tests import common


class FSMOrderRouteVehicleCase(common.TransactionCase):
    def setUp(self):
        super().setUp()
        self.fsm_order_obj = self.env["fsm.order"]
        self.fsm_dayroute_obj = self.env["fsm.route.dayroute"]
        self.fsm_vehicle_obj = self.env["fsm.vehicle"]
        self.test_person = self.env.ref("fieldservice.test_person")
        self.test_location = self.env.ref("fieldservice.test_location")
        self.date = datetime.now().replace(microsecond=0)

        self.vehicle1 = self.fsm_vehicle_obj.create({"name": "Van 1"})
        self.vehicle2 = self.fsm_vehicle_obj.create({"name": "Van 2"})

    def test_order_without_vehicle_does_not_create_dayroute(self):
        """Model 2: An order created without a vehicle must NOT create a Day Route."""
        order = self.fsm_order_obj.create(
            {
                "location_id": self.test_location.id,
                "person_id": self.test_person.id,
                "scheduled_date_start": self.date,
            }
        )
        self.assertFalse(order.dayroute_id)

    def test_vehicle_separation_and_fusion(self):
        """Test that assigning a vehicle creates a Day Route, different vehicles
        produce separate Day Routes, and updating vehicle_id triggers fusion.
        """
        # 1. Create order 1 with Vehicle 1
        order1 = self.fsm_order_obj.create(
            {
                "location_id": self.test_location.id,
                "person_id": self.test_person.id,
                "vehicle_id": self.vehicle1.id,
                "scheduled_date_start": self.date,
            }
        )

        # 2. Create order 2 with Vehicle 2 for the same person & date
        order2 = self.fsm_order_obj.create(
            {
                "location_id": self.test_location.id,
                "person_id": self.test_person.id,
                "vehicle_id": self.vehicle2.id,
                "scheduled_date_start": self.date,
            }
        )

        # They must land on two distinct Day Routes
        self.assertTrue(order1.dayroute_id)
        self.assertTrue(order2.dayroute_id)
        self.assertNotEqual(order1.dayroute_id, order2.dayroute_id)
        self.assertEqual(order1.dayroute_id.vehicle_id, self.vehicle1)
        self.assertEqual(order2.dayroute_id.vehicle_id, self.vehicle2)

        # 3. Update order2's vehicle to Vehicle 1 -> should fuse into order1's Day Route
        dayroute2 = order2.dayroute_id
        order2.write({"vehicle_id": self.vehicle1.id})

        self.assertEqual(order1.dayroute_id, order2.dayroute_id)
        self.assertFalse(dayroute2.exists())

    def test_dayroute_vehicle_change_pushes_to_orders(self):
        """Top-down sync: Changing vehicle_id on Day Route header pushes
        down to orders."""
        order = self.fsm_order_obj.create(
            {
                "location_id": self.test_location.id,
                "person_id": self.test_person.id,
                "vehicle_id": self.vehicle1.id,
                "scheduled_date_start": self.date,
            }
        )
        dayroute = order.dayroute_id
        dayroute.write({"vehicle_id": self.vehicle2.id})

        self.assertEqual(order.vehicle_id, self.vehicle2)

    def test_unassign_vehicle_detaches_and_cleans_dayroute(self):
        """Model 2: Removing vehicle_id from an order detaches dayroute_id
        and auto-deletes the empty Day Route.
        """
        order = self.fsm_order_obj.create(
            {
                "location_id": self.test_location.id,
                "person_id": self.test_person.id,
                "vehicle_id": self.vehicle1.id,
                "scheduled_date_start": self.date,
            }
        )
        dayroute = order.dayroute_id
        self.assertTrue(dayroute.exists())

        # Clear vehicle_id on order
        order.write({"vehicle_id": False})

        self.assertFalse(order.dayroute_id)
        self.assertFalse(dayroute.exists())

    def test_assign_vehicle_to_existing_vehicle_dayroute(self):
        """Bottom-up attach: Adding a vehicle to an unassigned order attaches it
        to an existing Day Route for that vehicle if one already exists.
        """
        order1 = self.fsm_order_obj.create(
            {
                "location_id": self.test_location.id,
                "person_id": self.test_person.id,
                "vehicle_id": self.vehicle1.id,
                "scheduled_date_start": self.date,
            }
        )

        # Order 2 starts without a vehicle (no Day Route)
        order2 = self.fsm_order_obj.create(
            {
                "location_id": self.test_location.id,
                "person_id": self.test_person.id,
                "scheduled_date_start": self.date,
            }
        )
        self.assertFalse(order2.dayroute_id)

        # Assign Vehicle 1 to Order 2 -> attaches to Order 1's Day Route
        order2.write({"vehicle_id": self.vehicle1.id})

        self.assertEqual(order2.dayroute_id, order1.dayroute_id)
