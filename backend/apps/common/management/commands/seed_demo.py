"""Seed development data. Safe to run repeatedly (idempotent)."""
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import AgentProfile, CustomerProfile, InspectorProfile, User
from apps.common.models import PlatformSetting
from apps.insurance.models import CoverageOption, Insurer, Product
from apps.insurance.services import generate_quotes, select_quotation
from apps.organizations.models import Membership, Organization
from apps.vehicles.models import Vehicle


class Command(BaseCommand):
    help = "Seed demo users, insurers, products and vehicles."

    @transaction.atomic
    def handle(self, *args, **options):
        admin = self._user("admin@autoinssure.local", "Admin@12345", "Platform", "Admin", User.Role.ADMIN, is_staff=True)
        customer = self._user("customer@example.com", "Customer@12345", "Jane", "Wanjiru", User.Role.CUSTOMER)
        customer2 = self._user("customer2@example.com", "Customer@12345", "Peter", "Otieno", User.Role.CUSTOMER)
        CustomerProfile.objects.get_or_create(user=customer)
        CustomerProfile.objects.get_or_create(user=customer2)

        provider_admin = self._user("insurer@example.com", "Insurer@12345", "Amina", "Hassan", User.Role.PROVIDER_ADMIN)
        provider_staff = self._user("staff@example.com", "Staff@12345", "Brian", "Kip", User.Role.PROVIDER_STAFF)
        officer = self._user("claims@example.com", "Claims@12345", "Grace", "Muthoni", User.Role.CLAIMS_OFFICER)
        inspector = self._user("inspector@example.com", "Inspector@12345", "Daniel", "Owino", User.Role.INSPECTOR)
        agent = self._user("agent@example.com", "Agent@12345", "Mercy", "Achieng", User.Role.AGENT)
        InspectorProfile.objects.get_or_create(user=inspector)
        AgentProfile.objects.get_or_create(user=agent)

        insurer_a = self._organization(
            "Savannah Insurance Ltd", "INS-SAV-001", Organization.Status.VERIFIED
        )
        insurer_b = self._organization(
            "Highland Assurance Group", "INS-HIG-002", Organization.Status.VERIFIED
        )
        pending_org = self._organization(
            "Coastal Mutual Insurance", "INS-COA-003", Organization.Status.PENDING
        )

        Membership.objects.get_or_create(user=provider_admin, organization=insurer_a, defaults={"role": Membership.Role.OWNER})
        Membership.objects.get_or_create(user=provider_staff, organization=insurer_a, defaults={"role": Membership.Role.STAFF})
        Membership.objects.get_or_create(user=officer, organization=insurer_a, defaults={"role": Membership.Role.CLAIMS})
        Membership.objects.get_or_create(user=inspector, organization=insurer_a, defaults={"role": Membership.Role.INSPECTOR})
        Membership.objects.get_or_create(user=agent, organization=insurer_a, defaults={"role": Membership.Role.AGENT})

        ins_a = self._insurer(insurer_a, "Savannah Insurance", "IRA/INS/001")
        ins_b = self._insurer(insurer_b, "Highland Assurance", "IRA/INS/002")

        self._product(
            ins_a,
            "Savannah Comprehensive Plus",
            "SAV-COMP-PLUS",
            Product.Category.COMPREHENSIVE,
            "5.5000",
            "12000.00",
            "15000.00",
            ["Own damage cover", "Third party liability", "Theft and fire", "Courtesy car for 7 days", "Political violence and terrorism"],
            ["Racing or speed testing", "Driving without a valid licence", "Wear and tear"],
        )
        self._product(
            ins_a,
            "Savannah Third Party",
            "SAV-TP",
            Product.Category.THIRD_PARTY,
            "2.0000",
            "6000.00",
            "10000.00",
            ["Third party bodily injury", "Third party property damage", "Passenger liability"],
            ["Own vehicle damage", "Theft of own vehicle"],
        )
        self._product(
            ins_b,
            "Highland Motor Shield",
            "HIG-MOTOR-SHIELD",
            Product.Category.COMPREHENSIVE,
            "5.2000",
            "11000.00",
            "12500.00",
            ["Own damage", "Third party liability", "Windscreen cover", "Excess protector"],
            ["Commercial use without endorsement", "Unlicensed drivers"],
        )
        self._product(
            ins_b,
            "Highland Third Party Fire & Theft",
            "HIG-TPFT",
            Product.Category.THIRD_PARTY_FIRE_THEFT,
            "3.0000",
            "8000.00",
            "12000.00",
            ["Third party liability", "Fire damage", "Theft of vehicle"],
            ["Own damage not caused by fire or theft"],
        )
        self._product(
            ins_b,
            "Highland Commercial Fleet",
            "HIG-FLEET",
            Product.Category.COMMERCIAL,
            "6.5000",
            "25000.00",
            "20000.00",
            ["Fleet coverage", "Third party liability", "Goods in transit", "Driver personal accident"],
            ["Vehicles outside declared fleet", "Undeclared modifications"],
        )

        v1 = self._vehicle(customer, "KDA 123A", "Toyota", "Corolla", 2018, "JTDBR32E090123456", 1800, Vehicle.Category.SALOON, Vehicle.Fuel.PETROL, Vehicle.Usage.PRIVATE, "1850000.00")
        self._vehicle(customer, "KCX 456B", "Nissan", "X-Trail", 2020, "JN1TBNT32Z0001234", 2000, Vehicle.Category.SUV, Vehicle.Fuel.PETROL, Vehicle.Usage.PRIVATE, "3200000.00")
        self._vehicle(customer2, "KBS 789C", "Isuzu", "D-Max", 2019, "MPATFS85JJT012345", 3000, Vehicle.Category.PICKUP, Vehicle.Fuel.DIESEL, Vehicle.Usage.COMMERCIAL, "2800000.00")

        self._demo_marketplace(customer, v1)
        self._demo_inspection(customer, v1)

        PlatformSetting.objects.get_or_create(
            key="platform_name", defaults={"value": "AutoInsure Connect", "description": "Public platform name"}
        )
        PlatformSetting.objects.get_or_create(
            key="marketplace_open", defaults={"value": True, "description": "Whether new quotations are accepted"}
        )

        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write("admin@autoinssure.local / Admin@12345 (platform admin)")
        self.stdout.write("customer@example.com / Customer@12345 (customer)")
        self.stdout.write("insurer@example.com / Insurer@12345 (provider admin)")
        self.stdout.write("claims@example.com / Claims@12345 (claims officer)")
        self.stdout.write("inspector@example.com / Inspector@12345 (inspector)")
        self.stdout.write("agent@example.com / Agent@12345 (agent)")
        self.stdout.write(f"Pending organization for verification: {pending_org.name}")

    def _user(self, email, password, first, last, role, is_staff=False):
        user, created = User.objects.get_or_create(
            email=email,
            defaults={"first_name": first, "last_name": last, "role": role, "is_staff": is_staff},
        )
        if created:
            user.set_password(password)
            user.email_verified = True
            user.save()
        return user

    def _organization(self, name, reg, status):
        org, _ = Organization.objects.get_or_create(
            name=name,
            defaults={
                "organization_type": Organization.Type.INSURER,
                "registration_number": reg,
                "email": f"info@{name.split()[0].lower()}.co.ke",
                "phone": "+254700000000",
                "status": status,
            },
        )
        if org.status != status:
            org.status = status
            org.save(update_fields=["status"])
        return org

    def _insurer(self, org, display_name, license_number):
        insurer, _ = Insurer.objects.get_or_create(
            organization=org,
            defaults={"display_name": display_name, "license_number": license_number, "description": f"{display_name} motor insurance."},
        )
        return insurer

    def _product(self, insurer, name, code, category, rate, minimum, excess, benefits, exclusions):
        product, created = Product.objects.get_or_create(
            insurer=insurer,
            code=code,
            deleted_at=None,
            defaults={
                "name": name,
                "category": category,
                "base_premium_rate": Decimal(rate),
                "minimum_premium": Decimal(minimum),
                "excess_amount": Decimal(excess),
                "benefits": benefits,
                "exclusions": exclusions,
                "terms": "Cover is subject to the policy schedule and the insurer's standard motor policy wording.",
            },
        )
        if created:
            CoverageOption.objects.create(
                product=product,
                name="Courtesy car",
                description="Replacement vehicle for up to 7 days after an insured event.",
                premium_rate=Decimal("0.2000"),
                limit_amount=Decimal("50000.00"),
            )
            CoverageOption.objects.create(
                product=product,
                name="Excess protector",
                description="Reduces the policy excess payable on own damage claims.",
                premium_rate=Decimal("0.5000"),
                limit_amount=Decimal("15000.00"),
            )
        return product

    def _vehicle(self, owner, reg, make, model, year, chassis, cc, category, fuel, usage, value):
        vehicle, _ = Vehicle.objects.get_or_create(
            owner=owner,
            registration_number=reg,
            defaults={
                "make": make,
                "model": model,
                "manufacturing_year": year,
                "chassis_number": chassis,
                "engine_cc": cc,
                "category": category,
                "fuel_type": fuel,
                "usage": usage,
                "estimated_value": Decimal(value),
            },
        )
        return vehicle

    def _demo_marketplace(self, customer, vehicle):
        from apps.insurance.models import Application, QuotationRequest
        from apps.payments.services import initiate_premium_payment

        if QuotationRequest.objects.filter(customer=customer, vehicle=vehicle).exists():
            return
        req = QuotationRequest.objects.create(
            request_number=f"QR-DEMO-{vehicle.registration_number.replace(' ', '')}",
            customer=customer,
            vehicle=vehicle,
            coverage_type=Product.Category.COMPREHENSIVE,
            sum_insured=vehicle.estimated_value,
            desired_start_date=timezone.now().date() + timedelta(days=3),
            expires_at=timezone.now() + timedelta(days=14),
            notes="Demo quotation request seeded for local development.",
        )
        generate_quotes(req)
        quote = req.quotations.order_by("premium").first()
        if quote:
            select_quotation(quote)
            app = Application.objects.create(
                application_number=f"APP-DEMO-{vehicle.registration_number.replace(' ', '')}",
                customer=customer,
                quotation=quote,
                vehicle=vehicle,
                status=Application.Status.SUBMITTED,
                submitted_at=timezone.now(),
            )
            initiate_premium_payment(customer, app, "bank", "", f"seed-{app.id}")

    def _demo_inspection(self, customer, vehicle):
        from apps.inspections.models import Inspection

        Inspection.objects.get_or_create(
            inspection_number=f"INS-DEMO-{vehicle.registration_number.replace(' ', '')}",
            defaults={
                "requested_by": customer,
                "vehicle": vehicle,
                "inspection_type": Inspection.Type.PRE_INSURANCE,
                "status": Inspection.Status.REQUESTED,
                "location": "Nairobi CBD",
                "notes": "Demo inspection request seeded for local development.",
            },
        )
