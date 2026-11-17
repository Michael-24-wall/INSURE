import shutil
import tempfile
from urllib.parse import urlparse

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.common.tests_utils import auth_client, make_user, make_vehicle
from apps.inspections.models import Inspection


class InspectionWorkflowTests(TestCase):
    def setUp(self):
        self.customer = make_user("inspcustomer@example.com")
        self.admin = make_user("inspadmin@example.com", role=User.Role.ADMIN)
        self.inspector = make_user("inspector1@example.com", role=User.Role.INSPECTOR)
        self.inspector2 = make_user("inspector2@example.com", role=User.Role.INSPECTOR)
        self.vehicle = make_vehicle(self.customer)
        self.client_auth = auth_client(self.customer)
        self.inspector_client = auth_client(self.inspector)
        self.admin_client = auth_client(self.admin)

    def create_inspection(self):
        return self.client_auth.post(
            "/api/v1/inspections/",
            {
                "vehicle": str(self.vehicle.id),
                "inspection_type": "pre_insurance",
                "location": "Nairobi",
                "notes": "Pre-cover inspection",
            },
            content_type="application/json",
        )

    def test_full_inspection_workflow(self):
        resp = self.create_inspection()
        self.assertEqual(resp.status_code, 201, resp.content)
        inspection_id = resp.json()["id"]
        self.assertEqual(resp.json()["status"], "requested")

        scheduled = self.admin_client.post(
            f"/api/v1/inspections/{inspection_id}/schedule/",
            {
                "inspector": str(self.inspector.id),
                "scheduled_at": (timezone.now() + timezone.timedelta(days=1)).isoformat(),
                "location": "Westlands",
            },
            content_type="application/json",
        )
        self.assertEqual(scheduled.status_code, 200, scheduled.content)
        self.assertEqual(scheduled.json()["status"], "scheduled")

        not_my_job = auth_client(self.inspector2).post(f"/api/v1/inspections/{inspection_id}/start/")
        self.assertIn(not_my_job.status_code, (403, 404))

        started = self.inspector_client.post(f"/api/v1/inspections/{inspection_id}/start/")
        self.assertEqual(started.status_code, 200)
        self.assertEqual(started.json()["status"], "in_progress")

        damage = self.inspector_client.post(
            f"/api/v1/inspections/{inspection_id}/damages/",
            {
                "zone": "front_bumper",
                "severity": "moderate",
                "description": "Scratch and dent on front bumper",
                "estimated_repair_cost": "15000.00",
            },
            content_type="application/json",
        )
        self.assertEqual(damage.status_code, 201, damage.content)

        invalid_zone = self.inspector_client.post(
            f"/api/v1/inspections/{inspection_id}/damages/",
            {"zone": "warp_drive", "severity": "minor"},
            content_type="application/json",
        )
        self.assertEqual(invalid_zone.status_code, 400)

        completed = self.inspector_client.post(
            f"/api/v1/inspections/{inspection_id}/complete/",
            {
                "report_summary": "Vehicle inspected. Front bumper damage noted.",
                "overall_condition": "good",
            },
            content_type="application/json",
        )
        self.assertEqual(completed.status_code, 200, completed.content)
        self.assertEqual(completed.json()["status"], "completed")
        self.assertEqual(completed.json()["damage_count"], 1)

    def test_customer_cannot_schedule(self):
        inspection = self.create_inspection().json()
        resp = self.client_auth.post(
            f"/api/v1/inspections/{inspection['id']}/schedule/",
            {
                "inspector": str(self.inspector.id),
                "scheduled_at": (timezone.now() + timezone.timedelta(days=1)).isoformat(),
                "location": "CBD",
            },
            content_type="application/json",
        )
        self.assertIn(resp.status_code, (403, 404))

    def test_customer_isolation(self):
        inspection = self.create_inspection().json()
        other = auth_client(make_user("otherinsp@example.com"))
        self.assertEqual(other.get(f"/api/v1/inspections/{inspection['id']}/").status_code, 404)

    def test_zones_catalogue(self):
        resp = self.client_auth.get("/api/v1/inspections/zones/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(any(z["key"] == "front_bumper" for z in resp.json()))

    def test_unassigned_inspection_not_visible_to_other_org(self):
        from apps.common.tests_utils import add_member, make_org
        from apps.organizations.models import Membership

        inspection = self.create_inspection().json()
        provider = make_user("otherinsporg@example.com", role=User.Role.PROVIDER_ADMIN)
        org = make_org("Other Inspection Org")
        add_member(provider, org, Membership.Role.OWNER)
        provider_client = auth_client(provider)

        listing = provider_client.get("/api/v1/inspections/")
        self.assertEqual(listing.status_code, 200, listing.content)
        ids = {item["id"] for item in listing.json()["results"]}
        self.assertNotIn(inspection["id"], ids)
        self.assertEqual(provider_client.get(f"/api/v1/inspections/{inspection['id']}/").status_code, 404)


class InspectionDocumentAccessTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, True)
        self.customer = make_user("inspdoc@example.com")
        self.other = make_user("otherinspdoc@example.com")
        self.inspector = make_user("inspdocinspector@example.com", role=User.Role.INSPECTOR)
        self.vehicle = make_vehicle(self.customer)
        self.client_auth = auth_client(self.customer)
        self.inspector_client = auth_client(self.inspector)

    def test_inspection_report_and_damage_photo_are_protected(self):
        created = self.client_auth.post(
            "/api/v1/inspections/",
            {"vehicle": str(self.vehicle.id), "inspection_type": "pre_insurance"},
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201, created.content)
        inspection = Inspection.objects.get(pk=created.json()["id"])
        inspection.inspector = self.inspector
        inspection.status = Inspection.Status.IN_PROGRESS
        inspection.save(update_fields=["inspector", "status"])

        damage = self.inspector_client.post(
            f"/api/v1/inspections/{inspection.id}/damages/",
            {
                "zone": "front_bumper",
                "severity": "minor",
                "photo": SimpleUploadedFile("damage.jpg", b"image-bytes", content_type="image/jpeg"),
            },
            format="multipart",
        )
        self.assertEqual(damage.status_code, 201, damage.content)
        damage_body = damage.json()
        self.assertNotIn("photo", damage_body)
        photo_path = urlparse(damage_body["photo_download_url"]).path
        self.assertEqual(self.client_auth.get(photo_path).status_code, 200)
        self.assertEqual(auth_client(self.other).get(photo_path).status_code, 404)

        completed = self.inspector_client.post(
            f"/api/v1/inspections/{inspection.id}/complete/",
            {
                "report_summary": "Completed with photo evidence.",
                "overall_condition": "good",
                "report_file": SimpleUploadedFile("report.pdf", b"%PDF-1.4 report", content_type="application/pdf"),
            },
            format="multipart",
        )
        self.assertEqual(completed.status_code, 200, completed.content)
        report_body = completed.json()
        self.assertNotIn("report_file", report_body)
        report_path = urlparse(report_body["report_download_url"]).path
        self.assertEqual(self.client_auth.get(report_path).status_code, 200)
        self.assertEqual(auth_client(self.other).get(report_path).status_code, 404)
        self.assertTrue(AuditLog.objects.filter(action="inspection.report_downloaded").exists())
        self.assertTrue(AuditLog.objects.filter(action="inspection.damage_photo_downloaded").exists())
