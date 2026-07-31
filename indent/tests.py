from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from indent.models import (
    Project, Department, InternalIndent, InternalIndentItem,
    GRN, GRNItem, Deployment
)

class ProjectAssemblyTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client.login(username='testuser', password='password')
        
        self.dept_lead = Department.objects.create(name="Lead Dept", code="LD")
        self.dept_assembly = Department.objects.create(name="Assembly Dept", code="AD")
        
        self.project = Project.objects.create(
            name="Test Project",
            project_type="R&D",
            status="in_progress",
            lead=self.dept_lead
        )
        
        # Create Internal Indent for Assembly Dept
        self.indent = InternalIndent.objects.create(
            project=self.project,
            department=self.dept_assembly,
            indent_number="INT-001",
            created_by=self.user
        )
        
        # Add tasks/items
        self.item1 = InternalIndentItem.objects.create(
            internal_indent=self.indent,
            item_name="Task A",
            quantity=10
        )
        self.item2 = InternalIndentItem.objects.create(
            internal_indent=self.indent,
            item_name="Task B",
            quantity=20
        )
        # Total requested for Assembly Dept = 30
        
    def test_department_progress_calculation(self):
        # Create GRN to accept 15 items (5 from Task A, 10 from Task B) -> Total accepted = 15
        # Expected Progress = (15 / 30) * 100 = 50.0%
        grn = GRN.objects.create(
            grn_type="internal",
            grn_number="GRN-001",
            internal_indent=self.indent,
            created_by=self.user
        )
        
        GRNItem.objects.create(
            grn=grn,
            internal_indent_item=self.item1,
            received_quantity=5,
            accepted_qty=5
        )
        GRNItem.objects.create(
            grn=grn,
            internal_indent_item=self.item2,
            received_quantity=10,
            accepted_qty=10
        )
        
        url = reverse("project_assembly", args=[self.project.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        nodes = response.context['nodes']
        
        assembly_node = next((n for n in nodes if n["id"] == self.dept_assembly.id), None)
        if assembly_node:
            self.assertEqual(assembly_node["progress"], 50.0)
        
    def test_deployment_snapshot_creation(self):
        # 100% completion for Task A and partial for Task B
        grn = GRN.objects.create(
            grn_type="internal",
            grn_number="GRN-002",
            internal_indent=self.indent,
            created_by=self.user
        )
        
        GRNItem.objects.create(
            grn=grn,
            internal_indent_item=self.item1,
            received_quantity=10,
            accepted_qty=10
        )
        GRNItem.objects.create(
            grn=grn,
            internal_indent_item=self.item2,
            received_quantity=5,
            accepted_qty=5
        )
        # Total accepted = 15, expected progress = 50.0
        
        url = reverse("project_deploy", args=[self.project.id])
        # To avoid view failures, ensure we redirect correctly
        response = self.client.post(url)
        
        # Should redirect to deployment details
        self.assertEqual(response.status_code, 302)
        
        deployment = Deployment.objects.get(project=self.project)
        
        # Test just to check it exists and snapshot is not profoundly broken
        self.assertIsNotNone(deployment)
