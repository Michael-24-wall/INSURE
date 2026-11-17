import pyotp
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import EmailVerificationToken, PasswordResetToken, User
from apps.common.tests_utils import DEFAULT_PASSWORD, auth_client, make_user


class RegistrationTests(TestCase):
    def test_customer_registration_creates_profile(self):
        resp = self.client.post(
            "/api/v1/auth/register/customer/",
            {
                "email": "new@example.com",
                "password": "Strong@12345",
                "first_name": "New",
                "last_name": "User",
                "phone": "+254700111222",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        user = User.objects.get(email="new@example.com")
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertTrue(hasattr(user, "customer_profile"))
        self.assertNotIn("password", resp.json()["user"])

    def test_duplicate_email_rejected(self):
        make_user("existing@example.com")
        resp = self.client.post(
            "/api/v1/auth/register/customer/",
            {"email": "existing@example.com", "password": "Strong@12345", "first_name": "A", "last_name": "B"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["success"])

    def test_weak_password_rejected(self):
        resp = self.client.post(
            "/api/v1/auth/register/customer/",
            {"email": "weak@example.com", "password": "123", "first_name": "A", "last_name": "B"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_email_verification(self):
        user = make_user("verify@example.com")
        token = EmailVerificationToken.objects.create(
            user=user, expires_at=timezone.now() + timezone.timedelta(days=1)
        )
        resp = self.client.post(
            "/api/v1/auth/verify-email/", {"token": str(token.token)}, content_type="application/json"
        )
        self.assertEqual(resp.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.email_verified)

    def test_expired_verification_token_rejected(self):
        user = make_user("expired@example.com")
        token = EmailVerificationToken.objects.create(
            user=user, expires_at=timezone.now() - timezone.timedelta(hours=1)
        )
        resp = self.client.post(
            "/api/v1/auth/verify-email/", {"token": str(token.token)}, content_type="application/json"
        )
        self.assertEqual(resp.status_code, 400)


class AuthFlowTests(TestCase):
    def test_login_returns_token_and_me(self):
        user = make_user("login@example.com")
        resp = self.client.post(
            "/api/v1/auth/login/", {"email": user.email, "password": DEFAULT_PASSWORD}, content_type="application/json"
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        access = resp.json()["access"]
        me = self.client.get("/api/v1/auth/me/", HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["email"], user.email)

    def test_invalid_login(self):
        make_user("bad@example.com")
        resp = self.client.post(
            "/api/v1/auth/login/", {"email": "bad@example.com", "password": "wrong"}, content_type="application/json"
        )
        self.assertEqual(resp.status_code, 401)

    def test_me_requires_auth(self):
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 401)

    def test_profile_update(self):
        user = make_user("profile@example.com")
        client = auth_client(user)
        resp = client.patch(
            "/api/v1/auth/me/",
            {"first_name": "Updated", "city": "Nairobi"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Updated")
        self.assertEqual(user.customer_profile.city, "Nairobi")

    def test_password_change_revokes_token(self):
        user = make_user("pwd@example.com")
        client = auth_client(user)
        resp = client.post(
            "/api/v1/auth/password/change/",
            {"current_password": DEFAULT_PASSWORD, "new_password": "NewStrong@12345"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(client.get("/api/v1/auth/me/").status_code, 401)

    def test_password_reset_flow(self):
        user = make_user("reset@example.com")
        resp = self.client.post(
            "/api/v1/auth/password/reset/", {"email": user.email}, content_type="application/json"
        )
        self.assertEqual(resp.status_code, 200)
        token = PasswordResetToken.objects.filter(user=user).latest("created_at")
        resp = self.client.post(
            "/api/v1/auth/password/reset/confirm/",
            {"token": str(token.token), "new_password": "ResetStrong@12345"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password("ResetStrong@12345"))


class UserPermissionTests(TestCase):
    def test_customer_cannot_list_users(self):
        customer = make_user("cust@example.com")
        client = auth_client(customer)
        self.assertEqual(client.get("/api/v1/auth/users/").status_code, 403)

    def test_admin_can_list_users(self):
        admin = make_user("admin2@example.com", role=User.Role.ADMIN)
        make_user("someone@example.com")
        client = auth_client(admin)
        resp = client.get("/api/v1/auth/users/")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.json()["count"], 2)


class TwoFactorTests(TestCase):
    def test_login_requires_otp_and_verify(self):
        user = make_user("2fa@example.com")
        secret = pyotp.random_base32()
        user.totp_secret = secret
        user.totp_enabled = True
        user.save(update_fields=["totp_secret", "totp_enabled"])

        resp = self.client.post(
            "/api/v1/auth/login/", {"email": user.email, "password": DEFAULT_PASSWORD}, content_type="application/json"
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.json()["otp_required"])
        self.assertIn("challenge", resp.json())

        code = pyotp.TOTP(secret).now()
        verify = self.client.post(
            "/api/v1/auth/2fa/verify/",
            {"challenge": resp.json()["challenge"], "code": code},
            content_type="application/json",
        )
        self.assertEqual(verify.status_code, 200, verify.content)
        self.assertIn("access", verify.json())

    def test_2fa_setup_and_confirm(self):
        user = make_user("2fasetup@example.com")
        client = auth_client(user)
        setup = client.post("/api/v1/auth/2fa/setup/")
        self.assertEqual(setup.status_code, 200, setup.content)
        secret = setup.json()["secret"]
        confirm = client.post(
            "/api/v1/auth/2fa/confirm/", {"code": pyotp.TOTP(secret).now()}, content_type="application/json"
        )
        self.assertEqual(confirm.status_code, 200, confirm.content)
        user.refresh_from_db()
        self.assertTrue(user.totp_enabled)

    def test_enabled_2fa_cannot_be_reset_without_password(self):
        user = make_user("2fareset@example.com")
        secret = pyotp.random_base32()
        user.totp_secret = secret
        user.totp_enabled = True
        user.save(update_fields=["totp_secret", "totp_enabled"])
        client = auth_client(user)

        setup = client.post("/api/v1/auth/2fa/setup/")

        self.assertEqual(setup.status_code, 400)
        user.refresh_from_db()
        self.assertEqual(user.totp_secret, secret)
        self.assertTrue(user.totp_enabled)


class KycTests(TestCase):
    def setUp(self):
        self.customer = make_user("kycuser@example.com")
        self.admin = make_user("kycadmin@example.com", role=User.Role.ADMIN)
        self.client_auth = auth_client(self.customer)
        self.admin_client = auth_client(self.admin)

    def test_kyc_submit_and_admin_review(self):
        submit = self.client_auth.post(
            "/api/v1/auth/kyc/",
            {"national_id": "12345678", "date_of_birth": "1990-01-01", "city": "Nairobi"},
            content_type="application/json",
        )
        self.assertEqual(submit.status_code, 200, submit.content)
        self.assertEqual(submit.json()["kyc_status"], "pending")

        approve = self.admin_client.post(
            f"/api/v1/auth/users/{self.customer.id}/kyc-review/",
            {"action": "approve", "notes": "Documents match"},
            content_type="application/json",
        )
        self.assertEqual(approve.status_code, 200, approve.content)
        self.assertEqual(approve.json()["kyc_status"], "verified")

    def test_kyc_review_requires_admin(self):
        self.client_auth.post("/api/v1/auth/kyc/", {}, content_type="application/json")
        resp = self.client_auth.post(
            f"/api/v1/auth/users/{self.customer.id}/kyc-review/",
            {"action": "approve"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_kyc_submit_requires_customer_role(self):
        admin = auth_client(self.admin)
        resp = admin.post("/api/v1/auth/kyc/", {}, content_type="application/json")
        self.assertEqual(resp.status_code, 403)
