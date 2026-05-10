from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.hardening import (
    InMemoryRateLimitMiddleware,
    SecurityHeadersMiddleware,
    allowed_origins,
    assert_secure_runtime_config,
)

# ─── Routers ───────────────────────────────────────────────────────────────
from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router
from app.modules.roles.router import router as roles_router
from app.modules.menus.router import router as menus_router
from app.modules.organizations.router import router as org_router
from app.modules.academic.router import router as academic_router
from app.modules.students.router import router as students_router
from app.modules.teachers.router import router as teachers_router
from app.modules.attendance.router import router as attendance_router, teacher_router
from app.modules.exams.router import router as exams_router
from app.modules.fees.router import router as fees_router
from app.modules.library.router import router as library_router
from app.modules.logs.router import router as logs_router
from app.modules.notifications.router import router as notifications_router
from app.modules.reports.router import router as reports_router
from app.modules.parents.router import router as parents_router
from app.modules.admin_bulk.router import router as admin_bulk_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    assert_secure_runtime_config()
    yield
    # Shutdown


app = FastAPI(
    title="School ERP API",
    description="""
## School & College ERP Backend

Production-grade multi-tenant ERP with:
- **JWT Authentication** (access + refresh tokens)
- **Role-Based Access Control** (RBAC) with per-API permission enforcement
- **Hierarchical Menu System**
- **Academic Masters**: Organizations → Institutions → Courses → Branches → Classes → Sections
- **Student & Teacher Management**
- **Attendance** (session-based, teacher-driven)
- **Exams & Marks** (draft → submitted → locked workflow)
- **Fees** (partial payments, status tracking)
- **Library** (issue/return with auto fine calculation)

### Auth Flow
1. `POST /auth/login` → get `access_token` + `refresh_token`
2. Set header: `Authorization: Bearer <access_token>`
3. Use `POST /auth/refresh` when access token expires
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# ─── CORS ──────────────────────────────────────────────────────────────────
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(InMemoryRateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Global exception handler ──────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    message = str(exc) if settings.DEBUG else "Internal server error"
    return JSONResponse(
        status_code=500,
        content={"success": False, "data": None, "message": message},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "data": None,
            "message": "Invalid request payload",
            "errors": exc.errors() if settings.DEBUG else [],
        },
    )


# ─── Register routers ──────────────────────────────────────────────────────
API = "/api/v1"
app.include_router(auth_router,       prefix=API)
app.include_router(users_router,      prefix=API)
app.include_router(roles_router,      prefix=API)
app.include_router(menus_router,      prefix=API)
app.include_router(org_router,        prefix=API)
app.include_router(academic_router,   prefix=API)
app.include_router(students_router,   prefix=API)
app.include_router(teachers_router,   prefix=API)
app.include_router(attendance_router, prefix=API)
app.include_router(teacher_router,    prefix=API)
app.include_router(exams_router,      prefix=API)
app.include_router(fees_router,       prefix=API)
app.include_router(library_router,    prefix=API)
app.include_router(logs_router,       prefix=API)
app.include_router(notifications_router, prefix=API)
app.include_router(reports_router,    prefix=API)
app.include_router(parents_router,    prefix=API)
app.include_router(admin_bulk_router, prefix=API)


@app.get("/", tags=["Health"])
async def health():
    return {"success": True, "data": {"service": "School ERP API", "version": "1.0.0"}, "message": "OK"}
