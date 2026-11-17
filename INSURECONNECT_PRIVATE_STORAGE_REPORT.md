# INSURECONNECT — Private Document Storage Report

Date: 2026-11-17

## Current state (IMPLEMENTED AND VERIFIED)

- `apps/common/files.py` `protected_file_response` streams authenticated downloads with
  `Cache-Control: private, no-store` and `X-Content-Type-Options: nosniff`.
- Object-level authorization on all document endpoints: policy, claim, vehicle,
  organisation, inspection, and receipt downloads (verified by 174 backend tests +
  real-browser negative tests: cross-tenant/unauthorised → 403/404).
- `apps/common/fields.py` `ValidatedFileField` enforces extension + size + declared MIME
  and rejects executable magic bytes (ELF/PE/Mach-O/shebang).
- Media is served directly by Django only when `DEBUG=true` (`config/urls.py`); in
  production it is reachable only through the authenticated endpoints.

## Gap (BLOCKED BY CREDENTIALS / APPROVAL)

Files are stored on the local filesystem (`FileSystemStorage`). For production this
should be an S3-compatible **private** bucket via `django-storages`.

## Proposed implementation (NOT IMPLEMENTED)

1. Add `django-storages` + `boto3` (dependency addition — requires approval).
2. Configure `STORAGES["default"] = {"BACKEND": "storages.backends.s3.S3Storage"}` with a
   **private** bucket (`AWS_QUERYSTRING_AUTH=False`, no public read ACL).
3. Keep `protected_file_response` streaming through the application — **no public object
   URLs, no signed URLs** for confidential documents.
4. Keep storage credentials in `backend/.env` only (backend-side).

## Migration strategy (no data loss)

1. Snapshot the existing `MEDIA_ROOT` directory.
2. Enable S3 storage behind the flag; on first access, `django-storages` reads from the
   bucket (empty initially).
3. Copy existing files from `MEDIA_ROOT` to the bucket with the same keys (idempotent,
   preserving the `FileField.name` keys already stored in the DB — **no DB changes**).
4. Verify a sample of downloads end-to-end, then remove the local copy only after backup.
5. Rollback: point `STORAGES["default"]` back to `FileSystemStorage` and restore the
   snapshot.

Do **not** migrate or delete existing files until this procedure is approved and rehearsed.

## Test plan (once implemented)

Authorized download, unauthorized download, cross-tenant download, invalid/oversized
document, missing object, storage outage (fail safely, no partial record), file
replacement, deletion + audit trail.

## File-content validation follow-up

Extension↔magic consistency for images/PDF/DOCX is a documented follow-up (the current
executable-magic check already blocks the highest-risk payloads). Full sniffing will be
added conservatively to avoid rejecting legitimate documents.
