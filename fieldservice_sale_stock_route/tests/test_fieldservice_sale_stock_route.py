# Copyright 2025 Patryk Pyczko (APSL-Nagarro)<ppyczko@apsl.net>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import datetime, timedelta

import pytz
from freezegun import freeze_time

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestFieldServiceSaleStockRoute(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.SaleOrder = cls.env["sale.order"]
        cls.Picking = cls.env["stock.picking"]
        cls.FSMOrder = cls.env["fsm.order"]
        cls.TimeRange = cls.env["fsm.delivery.time.range"]

        cls.product_10 = cls.env.ref("product.product_product_10")
        cls.product_10.write({"field_service_tracking": "sale"})

        cls.fsm_day_monday = cls.env.ref("fieldservice_route.fsm_route_day_0")
        cls.fsm_day_thursday = cls.env.ref("fieldservice_route.fsm_route_day_3")

        cls.test_partner = cls.env.ref("fieldservice.test_loc_partner")
        cls.test_location = cls.env.ref("fieldservice.test_location")
        cls.test_person = cls.env.ref("fieldservice.test_person")
        cls.test_route = cls.env["fsm.route"].create(
            {
                "name": "Test Route",
                "fsm_person_id": cls.test_person.id,
                "day_ids": [(6, 0, [cls.fsm_day_monday.id, cls.fsm_day_thursday.id])],
                "max_order": 1000,
            }
        )
        cls.test_location.write({"fsm_route_id": cls.test_route.id})
        cls.sale_order = cls.SaleOrder.create(
            {
                "partner_id": cls.test_partner.id,
                "fsm_location_id": cls.test_location.id,
                "order_line": [
                    (0, 0, {"product_id": cls.product_10.id, "product_uom_qty": 1})
                ],
                "state": "draft",
            }
        )

    def _create_sale_order(
        self, location=None, commitment_date=None, commitment_date_end=None
    ):
        """Helper to create sale orders in draft state for test scenarios."""
        vals = {
            "partner_id": self.test_partner.id,
            "fsm_location_id": (location or self.test_location).id,
            "order_line": [
                (0, 0, {"product_id": self.product_10.id, "product_uom_qty": 1})
            ],
            "state": "draft",
        }
        if commitment_date:
            vals["commitment_date"] = commitment_date
        if commitment_date_end:
            vals["commitment_date_end"] = commitment_date_end
        return self.SaleOrder.create(vals)

    def _assert_order_local_hours(
        self,
        order,
        expected_start_hour,
        expected_end_hour,
        expected_start_date=None,
        expected_end_date=None,
    ):
        """Helper to assert local start and end dates/hours on SO and FSM order."""
        tz_name = self.env.user.tz or "UTC"
        local_tz = pytz.timezone(tz_name)
        start_local = pytz.utc.localize(order.commitment_date).astimezone(local_tz)
        end_local = pytz.utc.localize(order.commitment_date_end).astimezone(local_tz)

        self.assertEqual(start_local.hour, expected_start_hour)
        self.assertEqual(end_local.hour, expected_end_hour)

        if expected_start_date:
            self.assertEqual(start_local.date(), expected_start_date)
        if expected_end_date:
            self.assertEqual(end_local.date(), expected_end_date)

        # Verify generated FSM order receives the exact dates
        fsm_order = self.FSMOrder.search([("sale_id", "=", order.id)], limit=1)
        if fsm_order:
            self.assertEqual(fsm_order.scheduled_date_start, order.commitment_date)
            self.assertEqual(fsm_order.scheduled_date_end, order.commitment_date_end)

    @freeze_time("2025-05-15")
    def test_commitment_dates_on_confirmation(self):
        """
        Test that commitment_date and commitment_date_end are correctly
        computed when the sale order is confirmed.
        """
        tomorrow = fields.Datetime.now() + timedelta(days=1)
        next_route_day = self.sale_order._get_next_route_day(from_date=tomorrow)
        expected_start, expected_end = self.sale_order._apply_time_range_to_dates(
            next_route_day, next_route_day
        )
        self.sale_order.action_confirm()

        self.assertTrue(
            self.sale_order.commitment_date,
            "Commitment date should be set after confirmation.",
        )

        self.assertEqual(
            self.sale_order.commitment_date,
            expected_start,
            "Commitment date should match next route day start time.",
        )

        self.assertEqual(
            self.sale_order.commitment_date_end,
            expected_end,
            "Commitment date end should match next route day end time.",
        )

    @freeze_time("2025-05-15")
    def test_commitment_date_end_before_commitment_date(self):
        """
        Test that commitment_date_end is set to commitment_date if
        commitment_date_end is set before commitment_date.
        """
        self.sale_order.commitment_date = datetime.now()
        self.sale_order.commitment_date_end = (
            self.sale_order.commitment_date - timedelta(days=1)
        )
        self.assertEqual(
            self.sale_order.commitment_date,
            self.sale_order.commitment_date_end,
            "Commitment date should match commitment date end.",
        )

    def test_validation_on_confirmation(self):
        """Test flexible confirmation and FSM route validation on sale order confirm."""
        # Flexible confirmation allows confirming even without route or person
        no_route_so = self._create_sale_order()
        no_route_so.fsm_location_id.write({"fsm_route_id": False})
        no_route_so.action_confirm()
        self.assertEqual(no_route_so.state, "sale")

        # Test that a ValidationError is raised if the commitment_date
        # is set to a day not in the route days.
        invalid_so = self._create_sale_order()
        invalid_so.fsm_location_id.write({"fsm_route_id": self.test_route.id})
        invalid_commitment_date = invalid_so._get_next_route_day() - timedelta(days=1)
        invalid_so.commitment_date = invalid_commitment_date
        with self.assertRaises(ValidationError):
            invalid_so.action_confirm()

    @freeze_time("2025-05-15")
    def test_write_commitment_dates_to_related_records(self):
        """Test that commitment_date is written to related pickings and FSM orders."""
        next_route_day = self.sale_order._get_next_route_day()
        self.sale_order.action_confirm()
        related_picking = self.sale_order.picking_ids.filtered(
            lambda r: r.state not in ["done", "cancel"]
        )
        related_fsm_order = self.env["fsm.order"].search(
            [
                ("sale_id", "=", self.sale_order.id),
                ("sale_line_id", "=", False),
                ("is_closed", "=", False),
            ]
        )

        self.assertEqual(
            self.sale_order.commitment_date,
            related_picking.scheduled_date,
            "Scheduled date on pickings should match commitment date.",
        )

        self.assertEqual(
            self.sale_order.commitment_date,
            related_fsm_order.scheduled_date_start,
            "Scheduled start date on FSM orders should match commitment date.",
        )

        self.assertEqual(
            self.sale_order.commitment_date_end,
            related_fsm_order.scheduled_date_end,
            "Scheduled end date on FSM orders should match commitment date.",
        )

        next_route_day = self.sale_order._get_next_route_day()
        self.sale_order.write(
            {
                "commitment_date": next_route_day,
                "commitment_date_end": next_route_day + timedelta(hours=1),
            }
        )

        self.assertEqual(
            next_route_day,
            related_picking.scheduled_date,
            "Scheduled date on pickings should match new commitment date.",
        )

        self.assertEqual(
            next_route_day,
            related_fsm_order.scheduled_date_start,
            "Scheduled start date on FSM orders should match new commitment date.",
        )

        self.assertEqual(
            next_route_day + timedelta(hours=1),
            related_fsm_order.scheduled_date_end,
            "Scheduled end date on FSM orders should match new commitment date.",
        )

        related_fsm_order._compute_postpone_button_visibility()
        self.assertTrue(
            related_fsm_order.show_postpone_button,
            "Postpone button should be visible after confirmation.",
        )

        next_route_day = self.sale_order._get_next_route_day(
            from_date=self.sale_order.commitment_date + timedelta(days=1)
        )
        related_fsm_order.action_postpone_delivery()

        self.assertEqual(
            next_route_day,
            related_picking.scheduled_date,
            "Scheduled date on pickings should match new commitment date.",
        )

        self.assertEqual(
            next_route_day,
            related_fsm_order.scheduled_date_start,
            "Scheduled start date on FSM orders should match new commitment date.",
        )

        self.assertEqual(
            next_route_day + timedelta(hours=1),
            related_fsm_order.scheduled_date_end,
            "Scheduled end date on FSM orders should match new commitment date "
            "and preserve the time.",
        )

    @freeze_time("2025-05-15")
    def test_force_schedule_override(self):
        """
        Test that force_schedule on FSM route allows scheduling on any day.
        """
        # Set route to NOT allow force scheduling
        self.test_route.write({"force_schedule": False})

        # Set an invalid commitment date (not in allowed days)
        invalid_commitment_date = self.sale_order._get_next_route_day() - timedelta(
            days=2
        )
        self.sale_order.commitment_date = invalid_commitment_date

        # Expect validation error because the date is not allowed
        with self.assertRaises(ValidationError):
            self.sale_order.action_confirm()

        # Enable force_schedule on the route
        self.test_route.write({"force_schedule": True})

        # Try confirming the sale order again with the same invalid date
        # This time, no error should be raised
        try:
            self.sale_order.action_confirm()
        except ValidationError:
            self.fail(
                "ValidationError was raised even though force_schedule is enabled."
            )

    @freeze_time("2025-05-15")
    def test_commitment_date_updated_on_fsm_write(self):
        FSMOrder = self.env["fsm.order"]

        fsm_order = FSMOrder.create(
            {
                "location_id": self.test_location.id,
                "sale_id": self.sale_order.id,
            }
        )

        new_start = datetime.now()
        new_end = new_start + timedelta(hours=1)

        fsm_order.write(
            {
                "scheduled_date_start": new_start,
                "scheduled_date_end": new_end,
            }
        )

        self.sale_order.invalidate_recordset()
        self.assertEqual(self.sale_order.commitment_date, new_start)
        self.assertEqual(self.sale_order.commitment_date_end, new_end)

        messages = self.sale_order.message_ids.filtered(
            lambda m: "Updated Delivery Dates" in m.body
        )
        self.assertTrue(messages)
        message = messages[0]
        self.assertIn("- Delivery Date:", message.body)
        self.assertIn("- Delivery End Date:", message.body)

    # -------------------------------------------------------------------------
    # End-User Workflow Tests: Fieldservice Availability 5-Level Hierarchy
    # -------------------------------------------------------------------------

    @freeze_time("2025-05-15")
    def test_user_confirm_hierarchy_level1_location_seasonal(self):
        """User Flow Level 1: Location Seasonal Schedule overrides Location Default & Route schedules on SO confirm."""
        loc_seasonal = self.TimeRange.create(
            {
                "start_time": 7.0,
                "end_time": 11.0,
                "month_start": "5",
                "day_start": 1,
                "month_end": "5",
                "day_end": 31,
            }
        )
        loc_default = self.TimeRange.create({"start_time": 8.0, "end_time": 14.0})
        route_seasonal = self.TimeRange.create(
            {
                "start_time": 6.0,
                "end_time": 10.0,
                "month_start": "5",
                "day_start": 1,
                "month_end": "5",
                "day_end": 31,
            }
        )
        route_default = self.TimeRange.create({"start_time": 9.0, "end_time": 17.0})

        self.test_location.write(
            {"delivery_time_range_ids": [(6, 0, [loc_seasonal.id, loc_default.id])]}
        )
        self.test_route.write(
            {"delivery_time_range_ids": [(6, 0, [route_seasonal.id, route_default.id])]}
        )

        so = self._create_sale_order()
        so.action_confirm()
        self._assert_order_local_hours(so, 7, 11)

    @freeze_time("2025-05-15")
    def test_user_confirm_hierarchy_level2_location_default(self):
        """User Flow Level 2: Location Default Schedule applies on SO confirm when no seasonal range matches."""
        loc_default = self.TimeRange.create({"start_time": 8.0, "end_time": 14.0})
        route_default = self.TimeRange.create({"start_time": 9.0, "end_time": 17.0})

        self.test_location.write(
            {"delivery_time_range_ids": [(6, 0, [loc_default.id])]}
        )
        self.test_route.write({"delivery_time_range_ids": [(6, 0, [route_default.id])]})

        so = self._create_sale_order()
        so.action_confirm()
        self._assert_order_local_hours(so, 8, 14)

    @freeze_time("2025-05-15")
    def test_user_confirm_hierarchy_level3_route_seasonal(self):
        """User Flow Level 3: Route Seasonal Schedule applies on SO confirm when Location has no time ranges."""
        self.test_location.write({"delivery_time_range_ids": [(5, 0, 0)]})
        route_seasonal = self.TimeRange.create(
            {
                "start_time": 6.0,
                "end_time": 10.0,
                "month_start": "5",
                "day_start": 1,
                "month_end": "5",
                "day_end": 31,
            }
        )
        route_default = self.TimeRange.create({"start_time": 9.0, "end_time": 17.0})
        self.test_route.write(
            {"delivery_time_range_ids": [(6, 0, [route_seasonal.id, route_default.id])]}
        )

        so = self._create_sale_order()
        so.action_confirm()
        self._assert_order_local_hours(so, 6, 10)

    @freeze_time("2025-05-15")
    def test_user_confirm_hierarchy_level4_route_default(self):
        """User Flow Level 4: Route Default Schedule applies on SO confirm when Location has no ranges & Route has no seasonal match."""
        self.test_location.write({"delivery_time_range_ids": [(5, 0, 0)]})
        route_default = self.TimeRange.create({"start_time": 9.0, "end_time": 17.0})
        self.test_route.write({"delivery_time_range_ids": [(6, 0, [route_default.id])]})

        so = self._create_sale_order()
        so.action_confirm()
        self._assert_order_local_hours(so, 9, 17)

    @freeze_time("2025-05-15")
    def test_user_confirm_hierarchy_level5_global_fallback(self):
        """User Flow Level 5: Global Fallback Schedule applies on SO confirm when neither Location nor Route specify ranges."""
        self.test_location.write({"delivery_time_range_ids": [(5, 0, 0)]})
        self.test_route.write({"delivery_time_range_ids": [(5, 0, 0)]})
        self.TimeRange.create({"start_time": 10.0, "end_time": 12.0, "sequence": 1})

        so = self._create_sale_order()
        so.action_confirm()
        self._assert_order_local_hours(so, 10, 12)

    @freeze_time("2025-05-15")
    def test_user_confirm_manual_dates_and_custom_hours(self):
        """User Flow: User manually picks start (May 19 14:30) and end (May 22 17:15) dates. SO confirm keeps days & applies schedule hours."""
        loc_range = self.TimeRange.create({"start_time": 8.0, "end_time": 16.0})
        self.test_location.write({"delivery_time_range_ids": [(6, 0, [loc_range.id])]})

        manual_start = datetime(2025, 5, 19, 14, 30, 0)
        manual_end = datetime(2025, 5, 22, 17, 15, 0)

        so = self._create_sale_order(
            commitment_date=manual_start, commitment_date_end=manual_end
        )
        so.action_confirm()

        self._assert_order_local_hours(
            so,
            expected_start_hour=8,
            expected_end_hour=16,
            expected_start_date=manual_start.date(),
            expected_end_date=manual_end.date(),
        )
