# Admin Bulk Uploads

## What Was Added

Admin screens now have Excel-friendly bulk tools:

- **Format** downloads a CSV template with the exact columns.
- **Export** downloads current data where export is available.
- **Import** uploads a filled `.csv` or `.xlsx` file.

`.csv` files open directly in Microsoft Excel and Google Sheets. `.xlsx` uploads are supported when `openpyxl` is installed in the backend environment.

## Backend APIs

Base URL:

```text
http://localhost:8000/api/v1
```

Endpoints:

```text
GET  /admin-bulk/resources
GET  /admin-bulk/templates/{resource}.csv
GET  /admin-bulk/exports/{resource}.csv
POST /admin-bulk/imports/{resource}
```

Upload field name:

```text
file
```

Permission required:

```text
admin_bulk_manage
```

Seed assigns this permission to Super Admin and Admin.

## Frontend Screens

Bulk buttons are now visible in:

- Academic masters
- Student registry
- Student documents
- Teachers
- Fees
- Exams and marks
- Library books

## Supported Resources

```text
academic-years
courses
branches
classes
sections
subjects
students
teachers
fee-types
fee-structures
student-fees
student-documents
exams
exam-subjects
marks
library-books
```

## Upload Formats

### academic-years

```csv
label,start_date,end_date,is_current,is_active
2027-28,2027-07-01,2028-06-30,false,true
```

### courses

```csv
code,name,level,duration_years,is_active
BCA,Bachelor of Computer Applications,UG,3,true
```

### branches

```csv
course_code,code,name,is_active
BTECH,AIML,Artificial Intelligence and Machine Learning,true
```

### classes

```csv
course_code,branch_code,academic_year_label,name,year_no,semester,intake_capacity
BTECH,CSE,2026-27,CSE Fourth Year - Semester 7,4,7,60
```

### sections

```csv
class_name,name,max_strength
CSE Second Year - Semester 3,C,60
```

### subjects

```csv
course_code,class_name,branch_code,academic_year_label,semester,code,name,credits,is_active
BTECH,CSE Second Year - Semester 3,CSE,2026-27,3,CS2309,Design and Analysis of Algorithms,4,true
```

### students

```csv
full_name,email,username,password,phone,roll_number,date_of_birth,gender,guardian_name,guardian_phone,guardian_email,academic_year_label,branch_code,class_name,section_name
New Student,new.student@student.demo.edu,new.student,Demo@123,9000099999,DEC27CSEA099,2007-05-20,female,Demo Parent,9000099998,demo.parent@parent.demo.edu,2026-27,CSE,CSE Second Year - Semester 3,A
```

### teachers

```csv
full_name,email,username,password,phone,employee_code,designation,joined_at
Demo Faculty,demo.faculty@demo.edu,demo.faculty,Demo@123,9000088888,FAC-DEMO-01,Assistant Professor,2026-06-01
```

### fee-types

```csv
name,description
Development Fee,Annual development fee
```

### fee-structures

```csv
fee_type_name,course_code,academic_year_label,amount,frequency
Development Fee,BTECH,2026-27,12000,annual
```

### student-fees

```csv
roll_number,fee_type_name,course_code,academic_year_label,amount_due,due_date
DEC26CSEA001,Development Fee,BTECH,2026-27,12000,2026-08-15
```

### student-documents

```csv
roll_number,document_type,title,file_name,file_url,status,remarks
DEC26CSEA001,identity,Aadhaar,aadhaar.pdf,,verified,Verified
```

### exams

```csv
academic_year_label,name,exam_type,workflow_status
2026-27,Unit Test 1,unit_test,draft
```

### exam-subjects

```csv
exam_name,academic_year_label,subject_code,max_marks,pass_marks,exam_date
Unit Test 1,2026-27,CS2301,50,20,2026-08-20
```

### marks

```csv
exam_name,academic_year_label,subject_code,roll_number,marks_obtained,is_absent,is_locked
Unit Test 1,2026-27,CS2301,DEC26CSEA001,42,false,false
```

### library-books

```csv
isbn,barcode,title,author,publisher,total_copies,available_copies
9789355420669,9789355420669,Database System Concepts,"Abraham Silberschatz, Henry F. Korth, S. Sudarshan",McGraw Hill,6,6
```

## Import Behavior

Imports are idempotent where possible:

- `code` updates existing courses/branches/subjects.
- `roll_number` updates existing students.
- `employee_code` updates existing teachers.
- `academic_year_label` maps to existing academic years.
- `guardian_email` creates/updates parent login automatically.
- Natural keys are used so admins do not need UUIDs.
- `library-books` uses `isbn` as the barcode and update key.

## Recommended Order

For a fresh institution, import in this order:

1. Academic years
2. Courses
3. Branches
4. Classes
5. Sections
6. Subjects
7. Teachers
8. Students
9. Fee types
10. Fee structures
11. Student fees
12. Exams
13. Exam subjects
14. Marks
15. Student documents
16. Library books
