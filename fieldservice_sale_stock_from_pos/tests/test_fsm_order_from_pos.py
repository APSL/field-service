from odoo.tests import tagged
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon


@tagged("post_install", "-at_install")
class TestUi(TestPointOfSaleHttpCommon):
    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)
        cls.stage_id = cls.env["fsm.stage"].create({
                "name": "Test default",
                "is_default": True,
                "company_id": cls.env.company.id
            })
        
        cls.team_id = cls.env["fsm.team"].create({
                "name": "Test Team",
                "company_id": cls.env.company.id
            })
    
    def test_pos_order_to_sale_order_with_fsm(self):
        self.main_pos_config.open_ui()
        # Add tracking to whiteboard pen to create fsm_order
        whiteboard_pen = self.env["product.product"].search(
            [("name", "=", "Whiteboard Pen")], limit=1
        )
        whiteboard_pen.write({"field_service_tracking": "sale"})
        
        # Make the test compatible with pos_minimize_menu
        if "iface_important_buttons" in self.main_pos_config._fields:
            self.main_pos_config.iface_important_buttons = ",".join(
                [
                    "CreateOrderButton",
                    "OrderlineCustomerNoteButton",
                ]
            )

        before_orders = self.env["sale.order"].search(
            [("partner_id", "=", self.env.ref("base.res_partner_address_31").id)],
            order="id",
        )

        self.start_tour(
            f"/pos/ui?config_id={self.main_pos_config.id}",
            "PosOrderToSaleOrderTour",
            login="accountman",
        )

        after_orders = self.env["sale.order"].search(
            [("partner_id", "=", self.env.ref("base.res_partner_address_31").id)],
            order="id",
        )
        

        self.assertEqual(len(before_orders) + 1, len(after_orders))
        
        order = after_orders[-1]
        self.assertEqual(order.amount_total, 5.18, "Total Amount must be equal to 5.18")
        self.assertEqual(order.state, "sale", "Order state must be equal to 'sale'")
        self.assertEqual(
            order.delivery_status, "full", "Delivery status must be equal to 'full'"
        )
        self.assertEqual(
            order.invoice_status,
            "invoiced",
            "Invoice status must be equal to 'invoiced'",
        )
        self.assertNotIn(
            "Product Note",
            order.order_line[0].name,
            "'Product Note' must contains in sale order line description",
        )
        self.assertIn(
            "Product Note",
            order.order_line[1].name,
            "'Product Note' must not contains in sale order line description",
        )
        
        self.assertTrue(order.fsm_order_ids, "Sale Order must have a FSM Order linked")
        self.assertTrue(
            order.fsm_order_ids.picking_ids
        )
        self.assertTrue(
            len(order.fsm_order_ids.picking_ids) == 2
        )
        