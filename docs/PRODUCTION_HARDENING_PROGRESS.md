# Production Hardening Progress

## Completed in this pass

- Student document upload now uses a backend-controlled storage folder.
- Student document downloads now go through an authenticated, permission-protected backend endpoint.
- Document uploads are restricted to PDF/image files and capped by `DOCUMENT_MAX_UPLOAD_MB`.
- Student document create, upload, update, download and delete actions are written to activity logs.
- Student update, deactivation, status change, academic record creation and bulk promotion actions are written to activity logs.
- Exam creation and exam-subject assignment are written to activity logs.
- Fee type, fee structure, student fee assignment and fee collection are written to activity logs.
- Fee APIs no longer trust frontend-supplied institution IDs for listing and creation.
- Fee payments now reject zero/negative amounts, unsupported modes, overpayment and missing transaction reference for non-cash modes.

## New environment settings

```env
DOCUMENT_STORAGE_DIR=storage/student-documents
DOCUMENT_MAX_UPLOAD_MB=10
```

## Still recommended before live deployment

- Rotate any secrets that were used during local development.
- Move document storage to S3/Azure Blob or another managed object store for production.
- Add automated API tests for role isolation, promotion, marks locking, fee payments and document downloads.
- Run Alembic migrations in staging before touching production data.
