# Parent Portal Backend Mapping

## What Was Done

The separate `parent-connect-portal` frontend is now connected to the existing ERP backend. No second backend project was created.

Parent identity is created from the guardian data already stored on students:

- `students.guardian_name`
- `students.guardian_phone`
- `students.guardian_email`

The backend creates a login user for each guardian email during seed. A `parent` role is still required for security, so the backend can allow parent portal access while preventing parents from using admin/teacher/student APIs.

## Backend Changes

Added parent portal API module:

- `app/modules/parents/router.py`
- `app/modules/parents/service.py`

Registered the router in:

- `app/main.py`

Added permission:

- `parent_read`

Updated seed:

- Creates `Parent` role.
- Creates `parent_read` permission.
- Creates parent users from each seeded student's guardian email.
- Links parent access by matching logged-in parent email with `students.guardian_email`.

No new database table was needed because parent-child mapping already exists through `guardian_email`.

## Parent APIs

Base URL:

```text
http://localhost:8000/api/v1
```

Endpoints:

```text
POST /auth/login
GET  /auth/me
GET  /parents/self/portal
GET  /parents/self/children
GET  /parents/self/children/{student_id}/attendance
GET  /parents/self/children/{student_id}/fees
GET  /parents/self/children/{student_id}/exams
GET  /parents/self/children/{student_id}/timetable
```

Main frontend endpoint:

```text
GET /parents/self/portal
```

It returns:

- Parent profile
- Linked children
- Attendance
- Performance
- Fees
- Exams
- Timetable
- Behavior/remarks
- Notifications/messages

## Frontend Changes

Updated separate parent frontend:

- `parent-connect-portal/src/services/api.ts`
- `parent-connect-portal/src/services/mockData.ts`
- `parent-connect-portal/src/context/PortalContext.tsx`
- `parent-connect-portal/src/routes/login.tsx`
- `parent-connect-portal/src/routes/timetable.tsx`
- `parent-connect-portal/.env`

The UI screens still keep their design, but after login the data comes from the backend instead of hard-coded mock data.

## Test Credentials

Example parent login:

```text
Email: rajesh.sharma@parent.demo.edu
Password: Demo@123
Child: Ananya Sharma
```

All seeded parent accounts use:

```text
Password: Demo@123
```

The parent email format comes from guardian name:

```text
<guardian.name>@parent.demo.edu
```

Examples:

```text
neeta.verma@parent.demo.edu
kiran.patel@parent.demo.edu
suresh.nair@parent.demo.edu
farah.khan@parent.demo.edu
```

## Verification Done

Backend compile:

```text
python -m compileall app
```

Parent frontend build:

```text
npm.cmd run build
```

Seed:

```text
DEBUG=false python seed.py
```

Smoke check confirmed:

- Parent login works.
- Parent role is enforced.
- Parent sees only linked child records.
- Portal payload returns attendance, behavior, exams, fees, performance, and timetable.

## Note

The frontend build succeeds, but Wrangler still prints a local Windows permission warning while trying to write logs under:

```text
C:\Users\Lenovo\AppData\Roaming\xdg.config
```

This does not stop the Vite build from completing.
