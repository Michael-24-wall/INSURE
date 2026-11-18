"""Seed isolated browser E2E data. Refuses to run against a non-E2E database."""
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.models import CustomerProfile, User
from apps.business_network.models import DealerBranch, DealerVehicle
from apps.business_network.services import create_partnership_request
from apps.insurance.models import (
    Application,
    Insurer,
    Product,
    QuotationRequest,
)
from apps.insurance.services import generate_quotes, select_quotation
from apps.organizations.models import Membership, Organization
from apps.common.test_accounts import TEST_ACCOUNT_EMAILS, TEST_ACCOUNT_ORG_NAMES
from apps.vehicles.models import Vehicle

E2E_EMAILS = [
    "e2e.admin@example.com",
    "e2e.customer@example.com",
    "e2e.customer2@example.com",
    "e2e.provider@example.com",
    "e2e.dealer@example.com",
    *TEST_ACCOUNT_EMAILS,
]
E2E_ORGS = ["E2E Alpha Insurance", "E2E Metro Motors", *TEST_ACCOUNT_ORG_NAMES]


class Command(BaseCommand):
    help = "Seed repeatable data for the Playwright browser suite."

    @transaction.atomic
    def handle(self, *args, **options):
        database_name = str(connection.settings_dict.get("NAME", "") or "")
        if "e2e" not in database_name.lower():
            raise CommandError(
                "seed_e2e only runs against an isolated E2E database "
                f"(current database: {database_name or 'unknown'})."
            )

        self._clear_e2e_data()

        admin = self._user(
            "e2e.admin@example.com", "E2eAdmin@12345", "E2E", "Admin", User.Role.ADMIN, is_staff=True
        )
        customer = self._user(
            "e2e.customer@example.com", "E2eCustomer@12345", "E2E", "Customer", User.Role.CUSTOMER
        )
        customer2 = self._user(
            "e2e.customer2@example.com", "E2eCustomer@12345", "E2E", "Other", User.Role.CUSTOMER
        )
        provider_user = self._user(
            "e2e.provider@example.com", "E2eProvider@12345", "E2E", "Provider", User.Role.PROVIDER_ADMIN
        )
        dealer_user = self._user(
            "e2e.dealer@example.com", "E2eDealer@12345", "E2E", "Dealer", User.Role.DEALER_ADMIN
        )

        CustomerProfile.objects.update_or_create(
            user=customer, defaults={"kyc_status": "verified"}
        )
        CustomerProfile.objects.update_or_create(
            user=customer2, defaults={"kyc_status": "verified"}
        )

        insurer_org = self._organization(
            "E2E Alpha Insurance",
            Organization.Type.INSURER,
            "E2E-INS-001",
            admin,
        )
        dealer_org = self._organization(
            "E2E Metro Motors",
            Organization.Type.DEALER,
            "E2E-DLR-001",
            admin,
        )
        Membership.objects.create(user=provider_user, organization=insurer_org, role=Membership.Role.OWNER)
        Membership.objects.create(user=dealer_user, organization=dealer_org, role=Membership.Role.OWNER)

        insurer = Insurer.objects.create(
            organization=insurer_org,
            display_name="E2E Alpha Insurance",
            license_number="E2E-IRA-001",
            description="Isolated insurer used by the browser E2E suite.",
        )
        product = Product.objects.create(
            insurer=insurer,
            name="E2E Comprehensive Cover",
            code="E2E-COMP",
            category=Product.Category.COMPREHENSIVE,
            base_premium_rate=Decimal("5.0000"),
            minimum_premium=Decimal("5000.00"),
            excess_amount=Decimal("10000.00"),
            benefits=["Own damage", "Third party liability", "Theft and fire"],
            exclusions=["Racing", "Unlicensed drivers"],
            terms="E2E product terms.",
        )

        vehicle = Vehicle.objects.create(
            owner=customer,
            registration_number="KDE 100E",
            make="Toyota",
            model="Corolla",
            manufacturing_year=2020,
            chassis_number="E2ECHASSIS1000001",
            engine_cc=1800,
            category=Vehicle.Category.SALOON,
            fuel_type=Vehicle.Fuel.PETROL,
            usage=Vehicle.Usage.PRIVATE,
            estimated_value=Decimal("1500000.00"),
        )
        other_vehicle = Vehicle.objects.create(
            owner=customer2,
            registration_number="KDE 200F",
            make="Nissan",
            model="X-Trail",
            manufacturing_year=2021,
            chassis_number="E2ECHASSIS2000002",
            engine_cc=2000,
            category=Vehicle.Category.SUV,
            fuel_type=Vehicle.Fuel.PETROL,
            usage=Vehicle.Usage.PRIVATE,
            estimated_value=Decimal("2000000.00"),
        )

        request = QuotationRequest.objects.create(
            request_number="QR-E2E-CUSTOMER",
            customer=customer,
            vehicle=vehicle,
            coverage_type=Product.Category.COMPREHENSIVE,
            sum_insured=vehicle.estimated_value,
            desired_start_date=timezone.now().date() + timedelta(days=2),
            expires_at=timezone.now() + timedelta(days=14),
            notes="Isolated E2E customer quotation.",
        )
        generate_quotes(request, insurer_ids=[insurer.id])

        other_request = QuotationRequest.objects.create(
            request_number="QR-E2E-CUSTOMER2",
            customer=customer2,
            vehicle=other_vehicle,
            coverage_type=Product.Category.COMPREHENSIVE,
            sum_insured=other_vehicle.estimated_value,
            desired_start_date=timezone.now().date() + timedelta(days=3),
            expires_at=timezone.now() + timedelta(days=14),
            notes="Isolated E2E tenant-isolation quotation.",
        )
        generate_quotes(other_request, insurer_ids=[insurer.id])
        other_quote = other_request.quotations.first()
        select_quotation(other_quote)
        other_application = Application.objects.create(
            application_number="APP-E2E-CUSTOMER2",
            customer=customer2,
            quotation=other_quote,
            vehicle=other_vehicle,
            status=Application.Status.SUBMITTED,
            submitted_at=timezone.now(),
        )

        branch = DealerBranch.objects.create(
            dealership=dealer_org,
            name="E2E Nairobi Branch",
            address="E2E Test Avenue",
            county="Nairobi",
            phone="+254700000001",
        )
        DealerVehicle.objects.create(
            dealership=dealer_org,
            branch=branch,
            registration_number="KDE 300G",
            vin="E2EVIN30000000003",
            make="Mazda",
            model="CX-5",
            year=2021,
            category=Vehicle.Category.SUV,
            fuel_type=Vehicle.Fuel.PETROL,
            transmission=DealerVehicle.Transmission.AUTOMATIC,
            mileage=42000,
            condition="used",
            asking_price=Decimal("2200000.00"),
            description="Isolated E2E dealership inventory.",
        )
        create_partnership_request(
            dealer_org,
            insurer_org,
            "E2E pending dealership partnership request.",
            dealer_user,
        )

        self.stdout.write(self.style.SUCCESS("E2E seed ready."))
        self.stdout.write(f"insurer={insurer.id} product={product.id} customer_request={request.id}")
        self.stdout.write(f"other_request={other_request.id} other_application={other_application.id}")
        self.stdout.write(f"dealer_org={dealer_org.id} other_vehicle={other_vehicle.id}")

    def _clear_e2e_data(self):
        User.objects.filter(email__in=E2E_EMAILS).delete()
        Organization.objects.filter(name__in=E2E_ORGS).delete()
        QuotationRequest.objects.filter(request_number__startswith="QR-E2E-").delete()
        Application.objects.filter(application_number__startswith="APP-E2E-").delete()
        DealerVehicle.objects.filter(vin__startswith="E2EVIN").delete()

    def _user(self, email, password, first_name, last_name, role, is_staff=False):
        return User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=role,
            email_verified=True,
            is_staff=is_staff,
        )

    def _organization(self, name, organization_type, registration_number, admin):
        return Organization.objects.create(
            name=name,
            organization_type=organization_type,
            registration_number=registration_number,
            email=f"{registration_number.lower()}@example.com",
            phone="+254700000000",
            status=Organization.Status.VERIFIED,
            verified_at=timezone.now(),
            verified_by=admin,
        )
