from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import CustomerProfile, User
from apps.insurance.models import Application, Insurer, Policy, Product, Quotation, QuotationRequest
from apps.organizations.models import Membership, Organization
from apps.vehicles.models import Vehicle

DEFAULT_PASSWORD = "Test@12345"


def make_user(email, role=User.Role.CUSTOMER, password=DEFAULT_PASSWORD, **kwargs):
    user = User.objects.create_user(email=email, password=password, role=role, **kwargs)
    if role == User.Role.CUSTOMER:
        CustomerProfile.objects.get_or_create(user=user)
    return user


def make_org(name="Test Insurer", status=Organization.Status.VERIFIED, org_type=Organization.Type.INSURER):
    return Organization.objects.create(
        name=name, organization_type=org_type, registration_number=f"REG-{name[:6].upper()}", status=status
    )


def make_insurer(org=None, name="Test Insurer"):
    org = org or make_org(name)
    insurer, _ = Insurer.objects.get_or_create(
        organization=org,
        defaults={"display_name": name, "license_number": "LIC-001"},
    )
    return insurer


def add_member(user, org, role=Membership.Role.STAFF):
    return Membership.objects.create(user=user, organization=org, role=role)


def make_product(insurer, code="TEST-COMP", category=Product.Category.COMPREHENSIVE, rate="5.0000"):
    return Product.objects.create(
        insurer=insurer,
        name=f"Product {code}",
        code=code,
        category=category,
        base_premium_rate=Decimal(rate),
        minimum_premium=Decimal("5000.00"),
        excess_amount=Decimal("10000.00"),
        benefits=["Own damage", "Third party liability"],
        exclusions=["Racing"],
    )


def make_vehicle(owner, reg="KDA 001A", value="2000000.00"):
    return Vehicle.objects.create(
        owner=owner,
        registration_number=reg,
        make="Toyota",
        model="Corolla",
        manufacturing_year=2019,
        chassis_number="CHASSIS123456",
        engine_cc=1800,
        category=Vehicle.Category.SALOON,
        fuel_type=Vehicle.Fuel.PETROL,
        usage=Vehicle.Usage.PRIVATE,
        estimated_value=Decimal(value),
    )


def auth_client(user):
    access = RefreshToken.for_user(user).access_token
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


def create_policy(customer, insurer=None, product=None, vehicle=None, start=None, end=None, issued_by=None):
    from apps.insurance.services import generate_quotes, issue_policy, select_quotation

    insurer = insurer or make_insurer()
    product = product or make_product(insurer)
    vehicle = vehicle or make_vehicle(customer)
    start = start or (timezone.now().date() - timedelta(days=10))
    end = end or (timezone.now().date() + timedelta(days=355))
    req = QuotationRequest.objects.create(
        request_number=f"QR-{customer.email[:4]}-{vehicle.registration_number.replace(' ', '')}-{QuotationRequest.objects.count()}",
        customer=customer,
        vehicle=vehicle,
        coverage_type=product.category,
        sum_insured=vehicle.estimated_value,
        desired_start_date=timezone.now().date(),
        expires_at=timezone.now() + timedelta(days=14),
    )
    generate_quotes(req)
    quote = req.quotations.filter(product=product).first()
    select_quotation(quote)
    app = Application.objects.create(
        application_number=f"APP-{customer.email[:4]}-{Application.objects.count()}",
        customer=customer,
        quotation=quote,
        vehicle=vehicle,
        status=Application.Status.SUBMITTED,
        submitted_at=timezone.now(),
    )
    policy = issue_policy(app, issued_by or customer, start, end, "TEST-REF", generate_document=False)
    return policy


def create_submitted_application(customer, insurer=None, product=None, vehicle=None):
    from apps.insurance.services import generate_quotes, select_quotation

    insurer = insurer or make_insurer()
    product = product or make_product(insurer)
    vehicle = vehicle or make_vehicle(customer)
    req = QuotationRequest.objects.create(
        request_number=f"QR-APP-{customer.email[:4]}-{QuotationRequest.objects.count()}",
        customer=customer,
        vehicle=vehicle,
        coverage_type=product.category,
        sum_insured=vehicle.estimated_value,
        desired_start_date=timezone.now().date(),
        expires_at=timezone.now() + timedelta(days=14),
    )
    generate_quotes(req)
    quote = req.quotations.filter(product=product).first()
    select_quotation(quote)
    return Application.objects.create(
        application_number=f"APP-{customer.email[:4]}-{Application.objects.count()}",
        customer=customer,
        quotation=quote,
        vehicle=vehicle,
        status=Application.Status.SUBMITTED,
        submitted_at=timezone.now(),
    )
