"""AI service abstractions.

Every result is advisory. Consequential decisions require human verification,
which is why confidence is returned and no business state is changed by these
functions. A remote provider can be plugged in by implementing the protocols
below without changing callers.
"""
import base64
import io
import json
import logging
import urllib.error
import urllib.request
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from .models import AIServiceLog

logger = logging.getLogger(__name__)


class DamageAnalysisProvider:
    name = "base"

    def analyze(self, image) -> dict:
        raise NotImplementedError


class HeuristicDamageAnalysisProvider(DamageAnalysisProvider):
    """Local image analysis used when no external vision provider is configured.

    Confidence is intentionally conservative. The output is a prompt for the
    inspector, never an automatic damage assessment.
    """

    name = "heuristic"

    def analyze(self, image) -> dict:
        try:
            from PIL import Image

            image.seek(0)
            img = Image.open(image)
            img = img.convert("RGB")
            img.thumbnail((256, 256))
            pixels = list(img.getdata())
            n = max(len(pixels), 1)
            avg_r = sum(p[0] for p in pixels) / n
            avg_g = sum(p[1] for p in pixels) / n
            avg_b = sum(p[2] for p in pixels) / n
            brightness = (avg_r + avg_g + avg_b) / 3
            dark_ratio = sum(1 for p in pixels if sum(p) / 3 < 45) / n
            redness = avg_r / max(avg_g + avg_b, 1) * 100
            if dark_ratio > 0.45:
                severity = "severe"
                confidence = Decimal("0.58")
            elif dark_ratio > 0.25:
                severity = "moderate"
                confidence = Decimal("0.52")
            else:
                severity = "minor"
                confidence = Decimal("0.45")
            explanation = (
                "Heuristic analysis of image brightness and dark-pixel ratio. "
                "This is a preliminary hint only; an inspector must verify all damage."
            )
            return {
                "provider": self.name,
                "suggested_severity": severity,
                "confidence": float(confidence),
                "explanation": explanation,
                "metrics": {
                    "brightness": round(brightness, 2),
                    "dark_pixel_ratio": round(dark_ratio, 4),
                    "redness_index": round(redness, 2),
                },
                "requires_human_review": True,
            }
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Damage analysis failed: %s", exc)
            return {
                "provider": self.name,
                "suggested_severity": "unknown",
                "confidence": 0.0,
                "explanation": "Unable to analyse the image automatically. Manual inspection required.",
                "requires_human_review": True,
            }


class RemoteAIProvider(DamageAnalysisProvider):
    """OpenAI-compatible vision/LLM provider.

    Used only when ``AI_API_KEY`` and ``AI_API_URL`` are configured. Every
    result remains advisory and requires human review.
    """

    name = "remote"

    @property
    def configured(self):
        return bool(settings.AI_API_KEY and settings.AI_API_URL)

    def _chat(self, messages, max_tokens=700):
        if not self.configured:
            return None
        payload = {
            "model": settings.AI_MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        req = urllib.request.Request(
            settings.AI_API_URL,
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {settings.AI_API_KEY}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
            return data["choices"][0]["message"]["content"]
        except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError) as exc:
            logger.warning("Remote AI call failed: %s", exc)
            return None

    def _image_message(self, image, prompt):
        image.seek(0)
        b64 = base64.b64encode(image.read()).decode()
        return {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        }

    def analyze(self, image):
        prompt = (
            "Assess the vehicle damage in this image. Reply with JSON only: "
            '{"severity": "minor|moderate|severe", "explanation": "..."}'
        )
        text = self._chat(
            [
                {"role": "system", "content": "You are a vehicle damage assessor."},
                self._image_message(image, prompt),
            ]
        )
        if not text:
            return {
                "provider": self.name,
                "suggested_severity": "unknown",
                "confidence": 0.0,
                "explanation": "Remote provider unavailable; manual inspection required.",
                "requires_human_review": True,
            }
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            parsed = json.loads(text[start:end]) if start != -1 else {}
            severity = parsed.get("severity", "unknown")
            explanation = parsed.get("explanation", text)
        except ValueError:
            severity, explanation = "unknown", text
        return {
            "provider": self.name,
            "suggested_severity": severity,
            "confidence": 0.7,
            "explanation": explanation,
            "requires_human_review": True,
        }


def get_damage_provider() -> DamageAnalysisProvider:
    if settings.AI_PROVIDER != "heuristic" and settings.AI_API_KEY and settings.AI_API_URL:
        return RemoteAIProvider()
    return HeuristicDamageAnalysisProvider()


def analyze_damage_image(image, user=None):
    result = get_damage_provider().analyze(image)
    AIServiceLog.objects.create(
        user=user,
        task="damage_image",
        provider=result.get("provider", "heuristic"),
        input_summary=getattr(image, "name", "")[:255],
        output=result,
        confidence=Decimal(str(result.get("confidence", 0))),
    )
    return result


def classify_document(file, user=None):
    name = (getattr(file, "name", "") or "").lower()
    rules = [
        (["police", "ob"], "police_report", 0.7),
        (["invoice", "receipt"], "invoice", 0.65),
        (["estimate", "quote"], "estimate", 0.62),
        (["license", "licence", "logbook"], "vehicle_document", 0.6),
        (["id", "passport", "national"], "identification", 0.55),
        (["medical", "hospital"], "medical_report", 0.6),
        (["jpg", "jpeg", "png", "photo", "img"], "photograph", 0.5),
        (["pdf"], "document", 0.45),
    ]
    category, confidence = "other", 0.3
    for tokens, cat, conf in rules:
        if any(t in name for t in tokens):
            category, confidence = cat, conf
            break
    result = {
        "category": category,
        "confidence": confidence,
        "explanation": (
            "Classification inferred from the file name and type using deterministic rules. "
            "A human reviewer must confirm document classification."
        ),
        "requires_human_review": True,
    }
    AIServiceLog.objects.create(
        user=user,
        task="document_classification",
        provider="heuristic",
        input_summary=name[:255],
        output=result,
        confidence=Decimal(str(confidence)),
    )
    return result


def extract_document_data(file, user=None):
    provider_name = "none"
    if settings.AI_PROVIDER != "heuristic" and settings.AI_API_KEY and settings.AI_API_URL:
        remote = RemoteAIProvider()
        text = remote._chat(
            [
                {
                    "role": "system",
                    "content": "Extract structured fields from the document. Reply with JSON only.",
                },
                {
                    "role": "user",
                    "content": f"Extract key fields from this document (filename: {getattr(file, 'name', '')}).",
                },
            ]
        )
        if text:
            try:
                start = text.find("{")
                end = text.rfind("}") + 1
                extracted = json.loads(text[start:end]) if start != -1 else {}
            except ValueError:
                extracted = {"raw": text[:1000]}
            result = {
                "extracted": extracted,
                "confidence": 0.7,
                "explanation": "Extraction produced by the configured AI provider. Verify before use.",
                "requires_human_review": True,
            }
            provider_name = remote.name
        else:
            result = {
                "extracted": {},
                "confidence": 0.0,
                "explanation": "Remote extraction provider unavailable; manual review required.",
                "requires_human_review": True,
            }
            provider_name = "remote"
    else:
        result = {
            "extracted": {},
            "confidence": 0.0,
            "explanation": (
                "No OCR/extraction provider is configured. Upload the document for human review or "
                "configure an extraction provider via AI_PROVIDER settings."
            ),
            "requires_human_review": True,
        }
    AIServiceLog.objects.create(
        user=user,
        task="document_extraction",
        provider=provider_name,
        input_summary=getattr(file, "name", "")[:255],
        output=result,
        confidence=Decimal(str(result["confidence"])),
    )
    return result


def detect_duplicate_documents(claim):
    from apps.claims.models import ClaimDocument

    docs = ClaimDocument.objects.filter(claim=claim).exclude(checksum="")
    seen = {}
    duplicates = []
    for doc in docs:
        if doc.checksum in seen:
            duplicates.append(
                {
                    "document_id": str(doc.id),
                    "duplicate_of": str(seen[doc.checksum]),
                    "checksum": doc.checksum,
                }
            )
        else:
            seen[doc.checksum] = doc.id
    return {
        "duplicates": duplicates,
        "checked": docs.count(),
        "explanation": "Exact duplicates are detected using SHA-256 checksums of uploaded files.",
        "requires_human_review": True,
    }


def suspicious_payment_indicators(user=None, insurer_ids=None):
    from django.db.models import Count, Q

    from apps.payments.models import Payment

    qs = Payment.objects.all()
    if insurer_ids is not None:
        qs = qs.filter(
            Q(application__quotation__insurer_id__in=insurer_ids)
            | Q(policy__insurer_id__in=insurer_ids)
            | Q(claim__policy__insurer_id__in=insurer_ids)
        ).distinct()
    elif user is not None and user.role not in {"admin", "super_admin"}:
        qs = qs.filter(user=user)
    repeated = (
        qs.values("provider_reference")
        .annotate(c=Count("id"))
        .filter(c__gt=1)
        .exclude(provider_reference="")
    )
    failed = qs.filter(status=Payment.Status.FAILED).count()
    pending_old = qs.filter(status=Payment.Status.PENDING).count()
    flags = []
    for row in repeated:
        flags.append({"type": "duplicate_reference", "reference": row["provider_reference"], "count": row["c"]})
    if failed >= 3:
        flags.append({"type": "repeated_failures", "count": failed})
    if pending_old >= 10:
        flags.append({"type": "pending_backlog", "count": pending_old})
    return {
        "flags": flags,
        "failed_payments": failed,
        "pending_payments": pending_old,
        "explanation": "Rule-based monitoring for duplicate references, repeated failures and pending backlog.",
        "requires_human_review": True,
    }


def suspicious_claim_indicators(insurer_ids=None):
    from datetime import timedelta

    from django.db.models import Count, F

    from apps.claims.models import Claim

    qs = Claim.objects.all()
    if insurer_ids is not None:
        qs = qs.filter(policy__insurer_id__in=insurer_ids)

    flags = []
    now = timezone.now()

    multiple_vehicle = (
        qs.values("policy__vehicle_id").annotate(c=Count("id")).filter(c__gt=1)
    )
    for row in multiple_vehicle:
        flags.append(
            {
                "type": "multiple_claims_same_vehicle",
                "vehicle_id": str(row["policy__vehicle_id"]),
                "count": row["c"],
            }
        )

    recent_cutoff = now - timedelta(days=30)
    high_frequency = (
        qs.filter(created_at__gte=recent_cutoff)
        .values("customer_id")
        .annotate(c=Count("id"))
        .filter(c__gt=2)
    )
    for row in high_frequency:
        flags.append(
            {"type": "high_frequency_claims", "customer_id": str(row["customer_id"]), "count": row["c"]}
        )

    near_sum_insured = qs.filter(amount_claimed__gte=F("policy__sum_insured") * Decimal("0.9"))
    for claim in near_sum_insured[:50]:
        flags.append(
            {
                "type": "claim_near_sum_insured",
                "claim_id": str(claim.id),
                "amount_claimed": str(claim.amount_claimed),
            }
        )

    return {
        "flags": flags,
        "checked": qs.count(),
        "explanation": "Rule-based claim fraud screening; all results require human review.",
        "requires_human_review": True,
    }


def insurance_assistant(question, user=None):
    from apps.insurance.models import Product
    from apps.organizations.models import Organization

    q = (question or "").lower().strip()
    if not q:
        answer = "Ask about motor insurance products, quotations, payments, claims or inspections."
        products = []
    elif any(k in q for k in ["claim", "accident", "damage"]):
        answer = (
            "To file a claim, open Claims, choose the policy covering the incident, describe what happened "
            "and upload evidence. A claims officer reviews it and may assign a vehicle inspector."
        )
        products = []
    elif any(k in q for k in ["pay", "mpesa", "premium"]):
        answer = (
            "Premiums can be paid via M-Pesa or bank transfer. A payment is only marked successful after "
            "gateway verification or authorised manual reconciliation."
        )
        products = []
    elif any(k in q for k in ["quote", "quotation", "compare", "price"]):
        answer = (
            "Add a vehicle to your garage, then request a quotation. The marketplace computes offers from "
            "each participating insurer's published product rates so you can compare premiums and benefits."
        )
        products = list(
            Product.objects.alive().filter(
                is_active=True, insurer__organization__status=Organization.Status.VERIFIED
            )[:5]
        )
    elif any(k in q for k in ["product", "cover", "comprehensive", "third party"]):
        products = list(
            Product.objects.alive().filter(
                is_active=True, insurer__organization__status=Organization.Status.VERIFIED
            )[:8]
        )
        answer = "Here are the currently published products in the marketplace."
    else:
        answer = (
            "I can help with quotations, products, payments, policies, inspections and claims. "
            "Tell me which part of your insurance journey you need help with."
        )
        products = []
    return {
        "answer": answer,
        "products": [
            {
                "id": str(p.id),
                "name": p.name,
                "insurer": p.insurer.display_name,
                "category": p.category,
                "minimum_premium": str(p.minimum_premium),
                "base_premium_rate": str(p.base_premium_rate),
            }
            for p in products
        ],
        "provider": "rules-based",
        "disclaimer": "Automated guidance is informational and does not constitute an insurance contract.",
    }
