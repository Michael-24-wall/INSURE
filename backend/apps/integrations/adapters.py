"""Standardised provider adapter framework.

Each insurer integration can be exercised through these adapters. Real calls are
only made when the integration is enabled and has a base URL and credentials;
otherwise a clear error is raised and logged. No fake success is produced.
"""
import http.client
import ipaddress
import json
import logging
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

from .models import Integration, IntegrationLog

logger = logging.getLogger(__name__)

_BLOCKED_HOST_SUFFIXES = (".localhost", ".local", ".internal", ".home", ".lan")


def outbound_url_error(url):
    """Return a human-readable reason when a URL could reach local/private networks."""
    if not url:
        return None
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return "Only http and https URLs are allowed."
    if parsed.username or parsed.password:
        return "Credentials in the URL are not allowed."
    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        return "A hostname is required."
    if host == "localhost" or host.endswith(_BLOCKED_HOST_SUFFIXES):
        return "Local and internal hostnames are not allowed."
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        # Hostname: resolve it and reject any address that resolves to a
        # local/private/reserved range. Unresolvable names are allowed here and
        # surface as a connection error at request time.
        try:
            infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        except OSError:
            return None
        for info in infos:
            ip_str = (info[4][0] or "").split("%")[0]
            try:
                resolved = ipaddress.ip_address(ip_str)
            except ValueError:
                continue
            if not resolved.is_global or resolved.is_multicast:
                return "Local, private and reserved IP addresses are not allowed."
        return None
    if not address.is_global or address.is_multicast:
        return "Local, private and reserved IP addresses are not allowed."
    return None


def _resolve_public_address(host, port):
    """Resolve ``host`` and return the first validated public address.

    Raises IntegrationCallError if any resolved address is not globally routable.
    This is the connection-time guard that closes the DNS-rebinding window left
    by the static ``outbound_url_error`` check: the address actually dialed is
    resolved here and rejected if it points at a private/reserved range.
    """
    try:
        infos = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
    except OSError as exc:
        raise IntegrationCallError(f"Hostname '{host}' could not be resolved: {exc}") from exc
    if not infos:
        raise IntegrationCallError(f"Hostname '{host}' has no resolvable address.")
    first = None
    for family, socktype, proto, canonname, sa in infos:
        ip_str = (sa[0] or "").split("%")[0]
        try:
            address = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if not address.is_global or address.is_multicast:
            raise IntegrationCallError("Local, private and reserved IP addresses are not allowed.")
        if first is None:
            first = (family, socktype, proto, canonname, (ip_str, sa[1]))
    return first


class _ValidatingHTTPConnection(http.client.HTTPConnection):
    def connect(self):
        resolved = _resolve_public_address(self.host, self.port)
        self.sock = socket.create_connection(resolved[4], self.timeout, self.source_address)


class _ValidatingHTTPSConnection(http.client.HTTPSConnection):
    def connect(self):
        resolved = _resolve_public_address(self.host, self.port)
        sock = socket.create_connection(resolved[4], self.timeout, self.source_address)
        if self._tunnel_host:
            self.sock = sock
            self._tunnel()
        # Preserve SNI and certificate hostname verification against the
        # original hostname while connecting to the validated IP address.
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


class _ValidatingHTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, req):
        return self.do_open(_ValidatingHTTPConnection, req)


class _ValidatingHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(
            _ValidatingHTTPSConnection, req, context=self._context, check_hostname=self._check_hostname
        )


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects instead of following them (which could reach an
    internal address). Every outbound connection is already validated, but
    redirects are disabled defensively and to keep behaviour predictable."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise IntegrationCallError(f"Redirects are not allowed for outbound integration requests (HTTP {code}).")


def _validating_opener():
    # The custom redirect handler overrides the default one so redirects are
    # rejected rather than followed.
    return urllib.request.build_opener(
        _ValidatingHTTPHandler, _ValidatingHTTPSHandler, _NoRedirectHandler
    )


class IntegrationNotConfigured(Exception):
    pass


class IntegrationCallError(Exception):
    pass


class GenericRESTAdapter:
    def __init__(self, integration: Integration):
        self.integration = integration

    @property
    def configured(self):
        return bool(self.integration.is_enabled and self.integration.base_url)

    def _headers(self):
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        credentials = self.integration.get_credentials()
        if self.integration.auth_type == "bearer" and credentials:
            headers["Authorization"] = f"Bearer {credentials}"
        elif self.integration.auth_type == "api_key" and credentials:
            key_name = self.integration.config.get("api_key_header", "X-API-Key")
            headers[key_name] = credentials
        elif self.integration.auth_type == "basic" and credentials:
            import base64

            headers["Authorization"] = "Basic " + base64.b64encode(credentials.encode()).decode()
        return headers

    def request(self, method, path, payload=None, attempt=1):
        if not self.configured:
            raise IntegrationNotConfigured("Integration is not enabled or has no base URL.")
        url = self.integration.base_url.rstrip("/") + "/" + path.lstrip("/")
        url_error = outbound_url_error(url)
        if url_error:
            raise IntegrationCallError(url_error)
        data = json.dumps(payload).encode() if payload is not None else None
        started = time.monotonic()
        req = urllib.request.Request(url, data=data, headers=self._headers(), method=method)
        try:
            with _validating_opener().open(req, timeout=self.integration.timeout_seconds) as resp:
                body = resp.read().decode(errors="ignore")
                status_code = resp.status
                try:
                    parsed = json.loads(body) if body else {}
                except ValueError:
                    parsed = {"raw": body[:2000]}
                duration = int((time.monotonic() - started) * 1000)
                IntegrationLog.objects.create(
                    integration=self.integration,
                    direction="outbound",
                    endpoint=path,
                    method=method,
                    request_payload=payload or {},
                    response_payload=parsed,
                    status_code=status_code,
                    success=200 <= status_code < 300,
                    duration_ms=duration,
                    attempt=attempt,
                )
                if status_code >= 400:
                    raise IntegrationCallError(f"Provider responded with HTTP {status_code}.")
                return parsed
        except urllib.error.HTTPError as exc:
            duration = int((time.monotonic() - started) * 1000)
            IntegrationLog.objects.create(
                integration=self.integration,
                direction="outbound",
                endpoint=path,
                method=method,
                request_payload=payload or {},
                status_code=exc.code,
                success=False,
                duration_ms=duration,
                error=str(exc),
                attempt=attempt,
            )
            if attempt < self.integration.retry_limit and exc.code >= 500:
                return self.request(method, path, payload, attempt + 1)
            raise IntegrationCallError(f"Provider responded with HTTP {exc.code}.")
        except IntegrationCallError as exc:
            IntegrationLog.objects.create(
                integration=self.integration,
                direction="outbound",
                endpoint=path,
                method=method,
                request_payload=payload or {},
                success=False,
                duration_ms=int((time.monotonic() - started) * 1000),
                error=str(exc),
                attempt=attempt,
            )
            raise
        except urllib.error.URLError as exc:
            duration = int((time.monotonic() - started) * 1000)
            IntegrationLog.objects.create(
                integration=self.integration,
                direction="outbound",
                endpoint=path,
                method=method,
                request_payload=payload or {},
                success=False,
                duration_ms=duration,
                error=str(exc),
                attempt=attempt,
            )
            if attempt < self.integration.retry_limit:
                return self.request(method, path, payload, attempt + 1)
            raise IntegrationCallError(f"Provider unreachable: {exc.reason}")

    def test_connection(self):
        return self.request("GET", self.integration.config.get("health_path", "/"))

    def push_quotation_request(self, payload):
        return self.request("POST", self.integration.config.get("quotation_path", "/quotations"), payload)

    def push_application(self, payload):
        return self.request("POST", self.integration.config.get("application_path", "/applications"), payload)

    def fetch_application_status(self, provider_reference):
        path = self.integration.config.get("application_status_path", "/applications/{ref}")
        return self.request("GET", path.format(ref=provider_reference))


def get_adapter(integration):
    if integration.provider_type in {Integration.ProviderType.REST, Integration.ProviderType.WEBHOOK}:
        return GenericRESTAdapter(integration)
    raise IntegrationNotConfigured("Only REST/webhook integrations support automated calls.")


def safe_test(integration):
    from django.utils import timezone

    try:
        response = get_adapter(integration).test_connection()
        integration.status = Integration.Status.ACTIVE
        integration.last_error = ""
        integration.last_tested_at = timezone.now()
        integration.save(update_fields=["status", "last_error", "last_tested_at"])
        return True, response
    except (IntegrationNotConfigured, IntegrationCallError) as exc:
        integration.status = Integration.Status.ERROR
        integration.last_error = str(exc)
        integration.last_tested_at = timezone.now()
        integration.save(update_fields=["status", "last_error", "last_tested_at"])
        return False, {"error": str(exc)}
