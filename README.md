# School ERP — Backend

Production-grade FastAPI backend for a School & College ERP platform.

---

## Quick Start

### 1. Prerequisites
- Python 3.11+
- PostgreSQL 15+
- Redis (optional)

### 2. Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — set DATABASE_URL and SECRET_KEY
```

### 3. Database

```bash
# Create DB
createdb school_erp
alembic revision --autogenerate -m "initial tables"
# Run migrations
alembic upgrade head

# Seed initial data (superadmin + permissions + menus)
python seed.py
```

### 4. Run

```bash
uvicorn app.main:app --reload --port 8000
```

### 5. Swagger UI

Open → http://localhost:8000/docs

---

## Default Login (after seed)

| Field    | Value           |
|----------|-----------------|
| Email    | admin@erp.com   |
| Password | Admin@123       |

---

## API Overview

| Method | Endpoint                              | Description                     |
|--------|---------------------------------------|---------------------------------|
| POST   | /api/v1/auth/login                    | Login, get tokens               |
| POST   | /api/v1/auth/refresh                  | Refresh access token            |
| GET    | /api/v1/auth/me                       | Current user profile            |
| GET    | /api/v1/menus/me                      | Role-based menu tree            |
| GET    | /api/v1/roles/permissions             | All permission codes            |
| PUT    | /api/v1/roles/{id}/permissions        | Assign permissions to role      |
| PUT    | /api/v1/roles/users/{id}/roles        | Assign roles to user            |
| POST   | /api/v1/organizations                 | Create organization             |
| POST   | /api/v1/institutions                  | Create institution              |
| POST   | /api/v1/academic-years                | Create academic year            |
| POST   | /api/v1/courses                       | Create course                   |
| POST   | /api/v1/branches                      | Create branch                   |
| POST   | /api/v1/subjects                      | Create subject                  |
| POST   | /api/v1/classes                       | Create class                    |
| POST   | /api/v1/sections                      | Create section                  |
| POST   | /api/v1/students                      | Create student (+ user account) |
| POST   | /api/v1/students/{id}/academic-record | Branch change / new year        |
| POST   | /api/v1/teachers                      | Create teacher                  |
| POST   | /api/v1/teachers/{id}/subjects        | Assign subject to teacher       |
| POST   | /api/v1/attendance/sessions           | Create attendance session       |
| POST   | /api/v1/attendance/mark               | Mark attendance                 |
| PATCH  | /api/v1/attendance/sessions/{id}/close| Close session                   |
| POST   | /api/v1/exams                         | Create exam                     |
| POST   | /api/v1/exams/{id}/subjects           | Add subject to exam             |
| PATCH  | /api/v1/exams/{id}/workflow/{action}  | submit / lock exam              |
| POST   | /api/v1/exams/marks                   | Upload marks                    |
| POST   | /api/v1/fees/types                    | Create fee type                 |
| POST   | /api/v1/fees/structures               | Create fee structure            |
| POST   | /api/v1/fees/student-fees             | Assign fee to student           |
| POST   | /api/v1/fees/payments                 | Collect payment                 |
| POST   | /api/v1/library/books                 | Add book                        |
| POST   | /api/v1/library/issue                 | Issue book                      |
| POST   | /api/v1/library/return                | Return book (auto fine)         |

---

## Architecture

```
app/
├── main.py               ← FastAPI app, router registration, CORS
├── core/
│   ├── config.py         ← Pydantic Settings (reads .env)
│   ├── security.py       ← JWT create/decode, bcrypt hash/verify
│   ├── dependencies.py   ← get_current_user, require_permission()
│   └── exceptions.py     ← HTTP exception classes
├── db/
│   ├── base.py           ← DeclarativeBase, UUIDPrimaryKey, TimestampMixin
│   └── session.py        ← Async engine, session factory, get_db()
├── modules/
│   └── <module>/
│       ├── model.py      ← SQLAlchemy ORM model
│       ├── schema.py     ← Pydantic request/response schemas
│       ├── service.py    ← Business logic (async, uses db session)
│       └── router.py     ← FastAPI router with permission guards
├── utils/
│   ├── response.py       ← ok(), paginated() helpers
│   └── pagination.py     ← PaginationParams dependency
└── constants/
    └── permissions.py    ← Permission code strings
```

---

## RBAC Permission Flow

```
Request
  └─→ Bearer token decoded → user_id extracted
        └─→ require_permission("student_create") dependency runs
              └─→ SQL: user_roles → role_permissions → permissions.code
                    ├─ Found  → proceed
                    └─ Not found → 403 Forbidden
```

Permission codes follow `<module>_<action>` convention.
Superusers bypass all permission checks.

---

## Response Format

All endpoints return:

```json
{
  "success": true,
  "data": { ... },
  "message": "OK"
}
```

Paginated lists:

```json
{
  "success": true,
  "data": {
    "items": [...],
    "total": 120,
    "page": 1,
    "page_size": 20,
    "total_pages": 6
  },
  "message": "OK"
}
```
