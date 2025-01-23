from odoo.tests.common import TransactionCase


class TestFSMOrder(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.demo_user = cls.env.ref("base.demo_user0")
        # Create test FSM Person
        cls.test_person = cls.env.ref("fieldservice.test_person")

        # Create test FSM Route linked to the test person
        cls.day_monday = cls.env.ref("fieldservice_route.fsm_route_day_0")
        cls.day_wednesday = cls.env.ref("fieldservice_route.fsm_route_day_2")
        cls.test_route = cls.env["fsm.route"].create(
            {
                "name": "Test Route",
                "fsm_person_id": cls.test_person.id,
                "day_ids": [cls.day_monday.id, cls.day_wednesday.id],
                "max_order": 100,
            }
        )

        # Create test FSM Location linked to the test route
        cls.partner_demo = cls.demo_user.partner_id
        fsm_wizard = cls.env["fsm.wizard"].create({})
        fsm_wizard.with_context(active_ids=[cls.partner_demo.id])
        fsm_wizard.action_convert_location(cls.partner_demo)

        cls.test_location = cls.env["fsm.location"].search(
            [("partner_id", "=", cls.partner_demo.id)]
        )

        cls.test_location.write({"fsm_route_id": cls.test_route.id})

    def test_fsm_order_create(self):
        # Create FSM Order without specifying person_id
        fsm_order = self.env["fsm.order"].create(
            {"location_id": self.test_location.id, "name": "Test Order"}
        )

        # Assert that the person_id is assigned from the FSM route's fsm_person_id
        self.assertEqual(
            fsm_order.person_id.id,
            self.test_person.id,
            "The person_id should be automatically assigned from the FSM route.",
        )

        # Create FSM Order with a specific person_id
        another_person = self.env.ref("fieldservice.person_1")
        fsm_order_with_person = self.env["fsm.order"].create(
            {
                "location_id": self.test_location.id,
                "person_id": another_person.id,
                "name": "Test Order With Person",
            }
        )

        # Assert that the specified person_id is respected
        self.assertEqual(
            fsm_order_with_person.person_id.id,
            another_person.id,
            "The person_id should not be overwritten if explicitly provided.",
        )

        # Create FSM Order with no route linked to the location
        self.test_location.fsm_route_id = False
        fsm_order_no_route = self.env["fsm.order"].create(
            {"location_id": self.test_location.id, "name": "Test Order No Route"}
        )

        # Assert that the person_id is not assigned when no route exists
        self.assertFalse(
            fsm_order_no_route.person_id,
            "The person_id should remain empty if no route is linked to the location.",
        )
