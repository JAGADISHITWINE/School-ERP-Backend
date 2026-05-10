# Security Hardening Report

Date: 2026-05-10

This document records the security loopholes found in the ERP backend and the fixes applied in this hardening pass.

## Executive Summary

The project had strong RBAC foundations, but several high-risk routes and production settings were still too open for a real college environment. The biggest risks were public read access to marks/fees/library data, anonymous password reset, wildcard CORS, detailed production errors, and weak marks workflow validation.

These items have now been tightened in code. Before a real deployment, rotate secrets and configure production origins.

## Fixed Loopholes

### 1. Public sensitive read APIs

Risk:

Students or unauthenticated users could query sensitive records if they knew IDs.

Fixed:

- Exam listing/detail/subjects/marks now require exam or marks permissions.
- Fee records and payment logs now require fee permissions.
- Library books/issues now require library permissions.
- Role listing now requires role read permission.

Files:

- `app/modules/exams/router.py`
- `app/modules/fees/router.py`
- `app/modules/library/router.py`
- `app/modules/roles/router.py`

### 2. Anonymous password reset

Risk:

The old `/auth/reset-password` accepted email + new password without OTP/token/current password. That was an account takeover path.

Fixed:

- `/auth/reset-password` now requires authentication.
- A user can reset only their own password unless super admin.
- Added `/auth/change-password`, which requires current password.

Files:

- `app/modules/auth/router.py`
- `app/modules/auth/service.py`
- `app/modules/auth/schema.py`

### 3. Wildcard CORS

Risk:

`allow_origins=["*"]` was too open for production.

Fixed:

- Added `ALLOWED_ORIGINS` setting.
- CORS now uses explicit origins from environment.

Files:

- `app/core/config.py`
- `app/core/hardening.py`
- `app/main.py`
- `.env`

### 4. Production error leakage

Risk:

The global exception handler returned raw exception strings. This can expose SQL details, internal paths, or implementation details.

Fixed:

- In `DEBUG=false`, internal errors now return a generic message.
- Validation errors hide details unless debug is enabled.

File:

- `app/main.py`

### 5. Public API docs in non-debug mode

Risk:

Swagger/ReDoc can reveal endpoint structure publicly.

Fixed:

- `/docs` and `/redoc` are enabled only when `DEBUG=true`.

File:

- `app/main.py`

### 6. Brute-force protection

Risk:

Login and token endpoints had no request throttling.

Fixed:

- Added in-memory rate limiting middleware.
- Auth endpoints use a stricter limit than general APIs.

Files:

- `app/core/hardening.py`
- `app/main.py`

Environment:

```env
RATE_LIMIT_PER_MINUTE=300
AUTH_RATE_LIMIT_PER_MINUTE=10
```

### 7. Security headers

Risk:

Missing browser security headers.

Fixed:

- Added `X-Content-Type-Options`
- Added `X-Frame-Options`
- Added `Referrer-Policy`
- Added `Permissions-Policy`
- Adds HSTS in production

Files:

- `app/core/hardening.py`
- `app/main.py`

### 8. JWT institution trust

Risk:

The current user dependency trusted `institution_id` from the token payload.

Fixed:

- Current institution is now read from the database user record, not from the token payload.

File:

- `app/core/dependencies.py`

### 9. Marks workflow validation

Risk:

Marks could be changed until exam lock only, and validation was too loose.

Fixed:

- Marks can be uploaded only while exam is `draft`.
- Upload checks exam belongs to the actor institution.
- Student must belong to the same institution.
- Marks must be between `0` and subject `max_marks`.
- Absent students store marks as `null`.
- Existing locked mark rows cannot be changed.
- Locking an exam also marks existing mark rows as locked.

File:

- `app/modules/exams/service.py`

### 10. Bulk marks import bypass

Risk:

Excel/CSV marks import could bypass normal marks validation.

Fixed:

- Bulk marks import now enforces draft exam status.
- It validates student institution.
- It validates marks range.
- It refuses to overwrite locked marks.
- It does not allow imported rows to force `is_locked=true`.

File:

- `app/modules/admin_bulk/service.py`

## Current Required Production Settings

Before real deployment, set these:

```env
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=<strong random 64+ character secret>
ALLOWED_ORIGINS=https://admin.yourcollege.edu,https://parents.yourcollege.edu
RATE_LIMIT_PER_MINUTE=300
AUTH_RATE_LIMIT_PER_MINUTE=10
```

Do not use the demo value:

```env
SECRET_KEY=change-me-to-a-secure-random-64-char-string
```

In production, the app now refuses to start if the secret is weak or wildcard CORS is used.

## Remaining Deployment-Level Security Work

These are not loopholes left open in normal app code, but they should be completed before public launch:

- Use HTTPS only.
- Put the API behind Nginx/Cloudflare or another gateway with IP-based rate limiting.
- Move from in-memory rate limiting to Redis-backed rate limiting for multi-server deployments.
- Store refresh tokens in a database table with rotation, logout, and revoke-all-on-password-change.
- Add MFA/OTP for admins, HODs, and exam/fee users.
- Use managed secrets, not plain `.env`, on production servers.
- Back up the database and test restore.
- Add database audit triggers for `marks`, `student_fees`, `fee_payments`, `attendance_records`, and `user_roles`.
- Restrict database user permissions so the app user cannot drop schemas/tables.

## Security Status After This Pass

Approximate backend security readiness:

```text
Before hardening: 45-55%
After hardening: 75-82%
```

The remaining gap is mainly production infrastructure, refresh-token revocation, MFA, and immutable database-level audit controls.
