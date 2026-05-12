from __future__ import annotations

import csv
from pathlib import Path

try:
    from openpyxl import Workbook
except Exception:  # pragma: no cover
    Workbook = None


OUT_DIR = Path(__file__).resolve().parents[1] / "mock_data" / "institute_level"
PASSWORD = "Demo@123"
YEAR = "2026-27"


HEADERS = {
    "academic-years": ["label", "start_date", "end_date", "is_current", "is_active"],
    "courses": ["code", "name", "level", "duration_years", "is_active"],
    "branches": ["course_code", "code", "name", "is_active"],
    "classes": ["course_code", "branch_code", "academic_year_label", "name", "year_no", "semester", "intake_capacity"],
    "sections": ["course_code", "branch_code", "class_name", "name", "max_strength"],
    "subjects": ["course_code", "class_name", "branch_code", "academic_year_label", "semester", "code", "name", "credits", "is_active"],
    "teachers": ["full_name", "email", "username", "password", "phone", "employee_code", "designation", "joined_at"],
    "students": ["full_name", "email", "username", "password", "phone", "roll_number", "date_of_birth", "gender", "guardian_name", "guardian_phone", "guardian_email", "academic_year_label", "course_code", "branch_code", "class_name", "section_name"],
    "fee-types": ["name", "description"],
    "fee-structures": ["fee_type_name", "course_code", "academic_year_label", "amount", "frequency"],
    "student-fees": ["roll_number", "fee_type_name", "course_code", "academic_year_label", "amount_due", "due_date"],
    "student-documents": ["roll_number", "document_type", "title", "file_name", "file_url", "status", "remarks"],
    "exams": ["academic_year_label", "name", "exam_type", "workflow_status"],
    "exam-subjects": ["exam_name", "academic_year_label", "subject_code", "max_marks", "pass_marks", "exam_date"],
    "marks": ["exam_name", "academic_year_label", "subject_code", "roll_number", "marks_obtained", "is_absent", "is_locked"],
    "library-books": ["isbn", "barcode", "title", "author", "publisher", "total_copies", "available_copies"],
}


COURSES = [
    ("BTECH", "Bachelor of Technology", "UG", 4),
    ("BCA", "Bachelor of Computer Applications", "UG", 3),
    ("BBA", "Bachelor of Business Administration", "UG", 3),
    ("BCOM", "Bachelor of Commerce", "UG", 3),
    ("MCA", "Master of Computer Applications", "PG", 2),
]

BRANCHES = [
    ("BTECH", "CSE", "Computer Science Engineering"),
    ("BTECH", "AIML", "Artificial Intelligence and Machine Learning"),
    ("BTECH", "ECE", "Electronics and Communication Engineering"),
    ("BTECH", "MECH", "Mechanical Engineering"),
    ("BCA", "CA", "Computer Applications"),
    ("BBA", "BA", "Business Analytics"),
    ("BCOM", "AT", "Accounting and Taxation"),
    ("MCA", "SE", "Software Engineering"),
]

SUBJECT_BANK = {
    "CSE": ["Engineering Mathematics I", "Python Programming", "Digital Logic Design", "Computer Organization", "Professional Communication"],
    "AIML": ["Linear Algebra for AI", "Python for AI", "Data Visualization", "Statistics for Data Science", "AI Workshop"],
    "ECE": ["Engineering Mathematics I", "Basic Electronics", "Network Analysis", "Signals and Systems", "Electronic Workshop"],
    "MECH": ["Engineering Mechanics", "Engineering Graphics", "Manufacturing Process", "Material Science", "Workshop Practice"],
    "CA": ["Programming in C", "Digital Computer Fundamentals", "Mathematics for Computing", "Office Automation", "Web Fundamentals"],
    "BA": ["Principles of Management", "Business Economics", "Business Mathematics", "Organizational Behaviour", "Business Communication"],
    "AT": ["Financial Accounting", "Business Law", "Corporate Accounting", "Taxation Basics", "Cost Accounting"],
    "SE": ["Advanced Database Systems", "Software Engineering", "Cloud Computing", "Machine Learning", "Research Methodology"],
}

FIRST_NAMES = [
    "Ananya", "Rohan", "Meera", "Karthik", "Diya", "Arjun", "Nisha", "Dev", "Sara", "Ishan",
    "Aarav", "Kiara", "Vivaan", "Saanvi", "Aditya", "Ira", "Kabir", "Tara", "Reyansh", "Myra",
    "Aisha", "Nikhil", "Pranav", "Ritika", "Varun", "Sneha", "Yash", "Pooja", "Harsh", "Neha",
]
LAST_NAMES = [
    "Sharma", "Kumar", "Nair", "Rao", "Patel", "Reddy", "Jain", "Malhotra", "Thomas", "Verma",
    "Iyer", "Menon", "Bhat", "Kulkarni", "Shetty", "Gupta", "Joshi", "Khan", "Das", "Ali",
]
TEACHERS = [
    "Rahul Iyer", "Neha Kulkarni", "Kavitha Nair", "Deepak Rao", "Sana Khan", "Priya Bhat",
    "Amit Varma", "Farah Ali", "Joseph Thomas", "Leela Krishnan", "Ritika Desai", "Manoj Pillai",
    "Suresh Nambiar", "Pallavi Shah", "Imran Qureshi", "Vandana Hegde", "Rakesh Sinha", "Anita Dsouza",
    "Girish Prabhu", "Swati Mehra", "Naveen Chandra", "Meghna Rao", "Arvind Shetty", "Shalini Gupta",
    "Harini Subramanian", "Kiran Babu", "Pavan Raj", "Maya George", "Rohit Bansal", "Divya Shenoy",
    "Nandita Bose", "Sameer Kulkarni", "Bhavana Murthy", "Vijay Narayan", "Asha Rao", "Vikram Menon",
]


def slug(value: str) -> str:
    return value.lower().replace(" ", ".").replace("-", ".")


def write_csv(name: str, rows: list[dict[str, object]], headers: list[str] | None = None) -> None:
    path = OUT_DIR / f"{name}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = headers or list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def build_dataset() -> dict[str, list[dict[str, object]]]:
    academic_years = [
        {"label": "2025-26", "start_date": "2025-06-01", "end_date": "2026-05-31", "is_current": "false", "is_active": "true"},
        {"label": YEAR, "start_date": "2026-06-01", "end_date": "2027-05-31", "is_current": "true", "is_active": "true"},
        {"label": "2027-28", "start_date": "2027-06-01", "end_date": "2028-05-31", "is_current": "false", "is_active": "true"},
    ]
    courses = [{"code": c, "name": n, "level": level, "duration_years": years, "is_active": "true"} for c, n, level, years in COURSES]
    branches = [{"course_code": c, "code": b, "name": n, "is_active": "true"} for c, b, n in BRANCHES]

    classes = []
    sections = []
    for course_code, branch_code, _branch_name in BRANCHES:
        for semester in (1, 2):
            year_no = 1 if semester <= 2 else (semester + 1) // 2
            class_name = f"{branch_code} Semester {semester}"
            classes.append({
                "course_code": course_code,
                "branch_code": branch_code,
                "academic_year_label": YEAR,
                "name": class_name,
                "year_no": year_no,
                "semester": semester,
                "intake_capacity": 60 if course_code != "MCA" else 50,
            })
            for section_name in ("A", "B"):
                sections.append({
                    "course_code": course_code,
                    "branch_code": branch_code,
                    "class_name": class_name,
                    "name": section_name,
                    "max_strength": 60 if course_code != "MCA" else 50,
                })

    subjects = []
    for course_code, branch_code, _branch_name in BRANCHES:
        names = SUBJECT_BANK[branch_code]
        for semester in (1, 2):
            for index, subject_name in enumerate(names, start=1):
                subjects.append({
                    "course_code": course_code,
                    "class_name": f"{branch_code} Semester {semester}",
                    "branch_code": branch_code,
                    "academic_year_label": YEAR,
                    "semester": semester,
                    "code": f"{branch_code}{semester}{index:02d}",
                    "name": subject_name if semester == 1 else f"{subject_name} II",
                    "credits": 4 if index <= 3 else 3,
                    "is_active": "true",
                })

    teachers = []
    for index, full_name in enumerate(TEACHERS, start=1):
        username = slug(full_name)
        teachers.append({
            "full_name": full_name,
            "email": f"{username}@scholaris.demo.edu",
            "username": username,
            "password": PASSWORD,
            "phone": f"98765{index:05d}",
            "employee_code": f"FAC{index:03d}",
            "designation": "Head of Department" if index in (3, 8, 13, 18, 23) else "Assistant Professor",
            "joined_at": f"2024-06-{(index % 24) + 1:02d}",
        })

    students = []
    class_sections = [(row["course_code"], row["branch_code"], row["name"], sec) for row in classes for sec in ("A", "B")]
    for index in range(1, 181):
        first = FIRST_NAMES[(index - 1) % len(FIRST_NAMES)]
        last = LAST_NAMES[((index - 1) // len(FIRST_NAMES)) % len(LAST_NAMES)]
        full_name = f"{first} {last}"
        course_code, branch_code, class_name, section_name = class_sections[(index - 1) % len(class_sections)]
        username = f"{slug(full_name)}.{index:03d}"
        roll_number = f"{branch_code}26{section_name}{index:03d}"
        guardian_first = FIRST_NAMES[(index + 7) % len(FIRST_NAMES)]
        guardian_name = f"{guardian_first} {last}"
        gender = "female" if index % 2 else "male"
        students.append({
            "full_name": full_name,
            "email": f"{username}@student.scholaris.demo.edu",
            "username": username,
            "password": PASSWORD,
            "phone": f"90000{index:05d}",
            "roll_number": roll_number,
            "date_of_birth": f"{2007 if course_code != 'MCA' else 2004}-{(index % 12) + 1:02d}-{(index % 27) + 1:02d}",
            "gender": gender,
            "guardian_name": guardian_name,
            "guardian_phone": f"91000{index:05d}",
            "guardian_email": f"parent.{username}@scholaris.demo.edu",
            "academic_year_label": YEAR,
            "course_code": course_code,
            "branch_code": branch_code,
            "class_name": class_name,
            "section_name": section_name,
        })

    fee_types = [
        ("Tuition Fee", "Semester tuition fee"),
        ("Library Fee", "Library and digital repository access"),
        ("Laboratory Fee", "Lab consumables and maintenance"),
        ("Examination Fee", "Internal and semester examination fee"),
        ("Sports Fee", "Sports and fitness facilities"),
        ("Development Fee", "Campus development contribution"),
        ("Transport Fee", "College bus service"),
        ("ID Card Fee", "Smart identity card printing"),
        ("Placement Training Fee", "Career readiness and aptitude training"),
        ("Alumni Fee", "Alumni association membership"),
    ]
    fee_types_rows = [{"name": n, "description": d} for n, d in fee_types]
    fee_amounts = {
        "BTECH": 85000,
        "BCA": 45000,
        "BBA": 42000,
        "BCOM": 38000,
        "MCA": 65000,
    }
    fee_structures = []
    for course_code, _name, _level, _years in COURSES:
        base = fee_amounts[course_code]
        for fee_name, amount in [
            ("Tuition Fee", base),
            ("Library Fee", 3000),
            ("Laboratory Fee", 8000 if course_code in ("BTECH", "BCA", "MCA") else 2500),
            ("Examination Fee", 2500),
            ("Development Fee", 10000),
            ("Placement Training Fee", 6000),
        ]:
            fee_structures.append({
                "fee_type_name": fee_name,
                "course_code": course_code,
                "academic_year_label": YEAR,
                "amount": amount,
                "frequency": "semester" if fee_name in ("Tuition Fee", "Laboratory Fee", "Examination Fee") else "annual",
            })

    student_fees = []
    for student in students:
        course_code = str(student["course_code"])
        for fee_name, due_offset in [("Tuition Fee", 15), ("Examination Fee", 25)]:
            amount = fee_amounts[course_code] if fee_name == "Tuition Fee" else 2500
            student_fees.append({
                "roll_number": student["roll_number"],
                "fee_type_name": fee_name,
                "course_code": course_code,
                "academic_year_label": YEAR,
                "amount_due": amount,
                "due_date": f"2026-08-{due_offset:02d}",
            })

    documents = []
    doc_types = [("identity", "Aadhaar Card"), ("marks_card", "Class 12 Marks Card"), ("transfer_certificate", "Transfer Certificate")]
    for index, student in enumerate(students, start=1):
        for doc_type, title in doc_types[: 2 + (index % 2)]:
            file_stub = str(student["roll_number"]).lower()
            documents.append({
                "roll_number": student["roll_number"],
                "document_type": doc_type,
                "title": title,
                "file_name": f"{file_stub}-{doc_type}.pdf",
                "file_url": f"https://files.scholaris.demo.edu/students/{file_stub}-{doc_type}.pdf",
                "status": "verified" if index % 5 else "pending",
                "remarks": "Clear copy verified" if index % 5 else "Verification pending",
            })

    exams = [
        {"academic_year_label": YEAR, "name": "Unit Test 1", "exam_type": "unit_test", "workflow_status": "draft"},
        {"academic_year_label": YEAR, "name": "Mid Semester Examination", "exam_type": "midterm", "workflow_status": "draft"},
        {"academic_year_label": YEAR, "name": "Practical Assessment 1", "exam_type": "practical", "workflow_status": "draft"},
        {"academic_year_label": YEAR, "name": "Semester End Examination", "exam_type": "final", "workflow_status": "draft"},
    ]
    exam_subjects = []
    for exam_index, exam in enumerate(exams, start=1):
        for subject in subjects[:32]:
            exam_subjects.append({
                "exam_name": exam["name"],
                "academic_year_label": YEAR,
                "subject_code": subject["code"],
                "max_marks": 50 if exam_index < 4 else 100,
                "pass_marks": 20 if exam_index < 4 else 40,
                "exam_date": f"2026-0{7 + exam_index}-{(len(exam_subjects) % 24) + 1:02d}",
            })

    subject_to_branch = {str(row["code"]): str(row["branch_code"]) for row in subjects}
    marks = []
    for exam_subject in exam_subjects[:48]:
        branch_code = subject_to_branch[str(exam_subject["subject_code"])]
        matching_students = [s for s in students if s["branch_code"] == branch_code][:18]
        for idx, student in enumerate(matching_students, start=1):
            absent = (idx + len(marks)) % 29 == 0
            max_marks = int(exam_subject["max_marks"])
            score = "" if absent else max(18, min(max_marks, 30 + ((idx * 7 + len(marks)) % (max_marks - 28))))
            marks.append({
                "exam_name": exam_subject["exam_name"],
                "academic_year_label": YEAR,
                "subject_code": exam_subject["subject_code"],
                "roll_number": student["roll_number"],
                "marks_obtained": score,
                "is_absent": "true" if absent else "false",
                "is_locked": "false",
            })

    library_books = []
    publishers = ["Pearson", "McGraw Hill", "Oxford University Press", "S Chand", "Wiley", "O'Reilly", "BPB Publications"]
    topics = [
        "Programming", "Data Structures", "Database Systems", "Operating Systems", "Computer Networks",
        "Artificial Intelligence", "Machine Learning", "Cloud Computing", "Digital Electronics", "Engineering Mathematics",
        "Business Management", "Financial Accounting", "Marketing Management", "Business Law", "Research Methodology",
    ]
    for index in range(1, 121):
        topic = topics[(index - 1) % len(topics)]
        library_books.append({
            "isbn": f"97893{50000000 + index:08d}",
            "barcode": f"LIB{index:05d}",
            "title": f"{topic}: Concepts and Applications Vol {((index - 1) // len(topics)) + 1}",
            "author": f"{FIRST_NAMES[index % len(FIRST_NAMES)]} {LAST_NAMES[index % len(LAST_NAMES)]}",
            "publisher": publishers[index % len(publishers)],
            "total_copies": 3 + (index % 6),
            "available_copies": 2 + (index % 5),
        })

    return {
        "academic-years": academic_years,
        "courses": courses,
        "branches": branches,
        "classes": classes,
        "sections": sections,
        "subjects": subjects,
        "teachers": teachers,
        "students": students,
        "fee-types": fee_types_rows,
        "fee-structures": fee_structures,
        "student-fees": student_fees,
        "student-documents": documents,
        "exams": exams,
        "exam-subjects": exam_subjects,
        "marks": marks,
        "library-books": library_books,
        "class-mentors-screen": build_class_mentors(sections, teachers),
        "teacher-linking-screen": build_teacher_links(subjects, sections, teachers),
        "timetable-screen": build_timetable(subjects, teachers),
        "attendance-screen": build_attendance(students, subjects, teachers),
        "teacher-content-screen": build_teacher_content(subjects, teachers),
        "library-issues-screen": build_library_issues(students, library_books),
        "notifications-screen": build_notifications(students),
        "reports-screen": build_reports(),
    }


def build_class_mentors(sections, teachers):
    rows = []
    for index, section in enumerate(sections, start=1):
        teacher = teachers[(index - 1) % len(teachers)]
        rows.append({
            "academic_year_label": YEAR,
            "course_code": section["course_code"],
            "branch_code": section["branch_code"],
            "class_name": section["class_name"],
            "section_name": section["name"],
            "mentor_employee_code": teacher["employee_code"],
            "mentor_name": teacher["full_name"],
        })
    return rows


def build_teacher_links(subjects, sections, teachers):
    rows = []
    for index, subject in enumerate(subjects, start=1):
        teacher = teachers[(index - 1) % len(teachers)]
        section_names = [s["name"] for s in sections if s["class_name"] == subject["class_name"] and s["branch_code"] == subject["branch_code"]]
        for section_name in section_names:
            rows.append({
                "academic_year_label": YEAR,
                "teacher_employee_code": teacher["employee_code"],
                "teacher_name": teacher["full_name"],
                "course_code": subject["course_code"],
                "branch_code": subject["branch_code"],
                "class_name": subject["class_name"],
                "section_name": section_name,
                "subject_code": subject["code"],
                "subject_name": subject["name"],
            })
    return rows


def build_timetable(subjects, teachers):
    days = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    rows = []
    for index, subject in enumerate(subjects[:80], start=1):
        teacher = teachers[(index - 1) % len(teachers)]
        rows.append({
            "academic_year_label": YEAR,
            "teacher_employee_code": teacher["employee_code"],
            "class_name": subject["class_name"],
            "section_name": "A" if index % 2 else "B",
            "subject_code": subject["code"],
            "day_of_week": days[index % len(days)],
            "start_time": f"{8 + (index % 6):02d}:00",
            "end_time": f"{9 + (index % 6):02d}:00",
            "room_no": f"R-{100 + index}",
            "is_active": "true",
        })
    return rows


def build_attendance(students, subjects, teachers):
    rows = []
    for index in range(1, 151):
        subject = subjects[(index - 1) % len(subjects)]
        teacher = teachers[(index - 1) % len(teachers)]
        matching_students = [s for s in students if s["branch_code"] == subject["branch_code"]][:5]
        for student_index, student in enumerate(matching_students, start=1):
            status = "late" if student_index == 5 else "absent" if (index + student_index) % 17 == 0 else "present"
            rows.append({
                "attendance_date": f"2026-07-{(index % 24) + 1:02d}",
                "session": "Forenoon" if index % 2 else "Afternoon",
                "period": (index % 6) + 1,
                "teacher_employee_code": teacher["employee_code"],
                "class_name": subject["class_name"],
                "section_name": "A" if index % 2 else "B",
                "subject_code": subject["code"],
                "roll_number": student["roll_number"],
                "status": status,
                "remarks": "" if status == "present" else "Marked during mock attendance test",
            })
    return rows


def build_teacher_content(subjects, teachers):
    rows = []
    for index, subject in enumerate(subjects[:60], start=1):
        teacher = teachers[(index - 1) % len(teachers)]
        rows.append({
            "content_type": "material" if index % 3 == 1 else "assessment" if index % 3 == 2 else "assignment",
            "academic_year_label": YEAR,
            "teacher_employee_code": teacher["employee_code"],
            "class_name": subject["class_name"],
            "section_name": "A" if index % 2 else "B",
            "subject_code": subject["code"],
            "title": f"{subject['name']} - Week {((index - 1) % 8) + 1}",
            "description": f"Professional mock content for {subject['name']}",
            "type": "PDF" if index % 3 == 1 else "Quiz" if index % 3 == 2 else "Assignment",
            "total_marks": "" if index % 3 == 1 else 25 + (index % 4) * 5,
            "due_date": "" if index % 3 == 1 else f"2026-09-{(index % 20) + 1:02d}",
            "file_or_url": f"https://files.scholaris.demo.edu/content/{subject['code'].lower()}-{index}.pdf",
        })
    return rows


def build_library_issues(students, books):
    return [
        {
            "barcode": books[index % len(books)]["barcode"],
            "book_title": books[index % len(books)]["title"],
            "roll_number": student["roll_number"],
            "issued_on": f"2026-07-{(index % 20) + 1:02d}",
            "due_date": f"2026-08-{(index % 20) + 1:02d}",
            "status": "issued" if index % 7 else "returned",
        }
        for index, student in enumerate(students[:120], start=1)
    ]


def build_notifications(students):
    subjects = ["Fee Reminder", "Attendance Alert", "Document Verification", "Exam Schedule", "Library Notice"]
    return [
        {
            "channel": "both" if index % 5 == 0 else "email" if index % 2 else "sms",
            "audience": "parent" if index % 3 == 0 else "student",
            "roll_number": student["roll_number"],
            "subject": subjects[index % len(subjects)],
            "body": f"Mock notification for {student['full_name']} - {subjects[index % len(subjects)]}.",
            "status": "sent" if index % 9 else "draft",
        }
        for index, student in enumerate(students[:100], start=1)
    ]


def build_reports():
    return [
        {"report_name": "Student Complete Report", "filter_1": "academic_year=2026-27", "filter_2": "roll_number=CSE26A008", "expected_result": "Admission, academics, fees, attendance and performance sections visible"},
        {"report_name": "Class Attendance Report", "filter_1": "class=CSE Semester 1", "filter_2": "section=A", "expected_result": "Daily present/absent/late summary"},
        {"report_name": "Subject Attendance Report", "filter_1": "subject=CSE101", "filter_2": "month=July 2026", "expected_result": "Subject-wise percentage and low attendance list"},
        {"report_name": "Fee Due Report", "filter_1": "academic_year=2026-27", "filter_2": "status=unpaid/partial", "expected_result": "Pending tuition and exam fee rows"},
        {"report_name": "Marks Report", "filter_1": "exam=Unit Test 1", "filter_2": "branch=CSE", "expected_result": "Marks and absent flags for selected subject mappings"},
    ]


def write_workbook(dataset: dict[str, list[dict[str, object]]]) -> None:
    if Workbook is None:
        return
    workbook = Workbook()
    default = workbook.active
    workbook.remove(default)
    for name, rows in dataset.items():
        sheet = workbook.create_sheet(title=name[:31])
        headers = HEADERS.get(name) or list(rows[0].keys())
        sheet.append(headers)
        for row in rows:
            sheet.append([row.get(header, "") for header in headers])
    workbook.save(OUT_DIR / "scholaris_institute_mock_dataset.xlsx")


def write_readme(dataset: dict[str, list[dict[str, object]]]) -> None:
    import_order = [
        "academic-years", "courses", "branches", "classes", "sections", "subjects", "teachers",
        "students", "fee-types", "fee-structures", "student-fees", "exams", "exam-subjects",
        "marks", "student-documents", "library-books",
    ]
    extra = [name for name in dataset if name not in import_order]
    lines = [
        "# Scholaris Institute-Level Mock Dataset",
        "",
        "Professional mock data for screen-wise ERP testing. CSV files matching bulk import resources are import-ready.",
        "",
        "## Import Order",
        "",
    ]
    for index, name in enumerate(import_order, start=1):
        lines.append(f"{index}. `{name}.csv` - {len(dataset[name])} rows")
    lines.extend(["", "## Screen-Testing CSVs", ""])
    for name in extra:
        lines.append(f"- `{name}.csv` - {len(dataset[name])} rows")
    lines.extend([
        "",
        "## Screen To File Map",
        "",
        "| ERP Screen | Use File | Purpose |",
        "|---|---|---|",
        "| Academic > Years | `academic-years.csv` | Academic year setup and current-year selection |",
        "| Academic > Courses | `courses.csv` | Course master testing |",
        "| Academic > Branches | `branches.csv` | Branch/department master testing |",
        "| Academic > Classes | `classes.csv` | Semester/class creation testing |",
        "| Academic > Sections | `sections.csv` | Section capacity and dropdown testing |",
        "| Academic > Subjects | `subjects.csv` | Subject master and class mapping testing |",
        "| Teachers | `teachers.csv` | Faculty profile creation testing |",
        "| HOD Linking / Teacher Linking | `teacher-linking-screen.csv` | Teacher-subject-section mapping reference |",
        "| Class Mentor Management | `class-mentors-screen.csv` | Mentor assignment screen testing |",
        "| Timetable | `timetable-screen.csv` | Teacher period/hour schedule testing |",
        "| Students > Admissions / Registry | `students.csv` | 180 realistic student admissions |",
        "| Students > Documents | `student-documents.csv` | Student document verification testing |",
        "| Attendance | `attendance-screen.csv` | 750 attendance marking rows for UI testing |",
        "| Materials & Assignments | `teacher-content-screen.csv` | Material, assessment and assignment screen testing |",
        "| Fees > Types | `fee-types.csv` | Fee type master testing |",
        "| Fees | `fee-structures.csv` | Course-wise fee setup testing |",
        "| Fees > Collect | `student-fees.csv` | 360 student fee dues for collection testing |",
        "| Exams | `exams.csv` | Exam creation workflow testing |",
        "| Exams > Subjects | `exam-subjects.csv` | Subject mapping for exams |",
        "| Exams > Marks | `marks.csv` | 864 marks upload rows |",
        "| Library | `library-books.csv` | 120 book catalog records |",
        "| Library > Issue Book | `library-issues-screen.csv` | Book issue/return workflow reference |",
        "| Notifications | `notifications-screen.csv` | Student/parent notification test data |",
        "| Reports | `reports-screen.csv` | Filter scenarios for report testing |",
    ])
    lines.extend([
        "",
        "## Notes",
        "",
        f"- Academic year: `{YEAR}`",
        f"- Default password: `{PASSWORD}`",
        "- Use CSV files for direct backend bulk import.",
        "- Use `scholaris_institute_mock_dataset.xlsx` when you want one Excel workbook with all sheets.",
        "- Screen-testing CSVs are reference data for screens that do not yet have a direct bulk import endpoint.",
    ])
    (OUT_DIR / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    dataset = build_dataset()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, rows in dataset.items():
        write_csv(name, rows, HEADERS.get(name))
    write_workbook(dataset)
    write_readme(dataset)
    print(f"Mock dataset generated at: {OUT_DIR}")
    for name, rows in dataset.items():
        print(f"{name}: {len(rows)}")


if __name__ == "__main__":
    main()
