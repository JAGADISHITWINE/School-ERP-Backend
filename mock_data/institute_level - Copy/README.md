# Scholaris Institute-Level Mock Dataset

Professional mock data for screen-wise ERP testing. CSV files matching bulk import resources are import-ready.

## Import Order

1. `academic-years.csv` - 3 rows
2. `courses.csv` - 5 rows
3. `branches.csv` - 8 rows
4. `classes.csv` - 16 rows
5. `sections.csv` - 32 rows
6. `subjects.csv` - 80 rows
7. `teachers.csv` - 36 rows
8. `students.csv` - 180 rows
9. `fee-types.csv` - 10 rows
10. `fee-structures.csv` - 30 rows
11. `student-fees.csv` - 360 rows
12. `exams.csv` - 4 rows
13. `exam-subjects.csv` - 128 rows
14. `marks.csv` - 864 rows
15. `student-documents.csv` - 450 rows
16. `library-books.csv` - 120 rows

## Screen-Testing CSVs

- `class-mentors-screen.csv` - 32 rows
- `teacher-linking-screen.csv` - 160 rows
- `timetable-screen.csv` - 80 rows
- `attendance-screen.csv` - 750 rows
- `teacher-content-screen.csv` - 60 rows
- `library-issues-screen.csv` - 120 rows
- `notifications-screen.csv` - 100 rows
- `reports-screen.csv` - 5 rows

## Screen To File Map

| ERP Screen | Use File | Purpose |
|---|---|---|
| Academic > Years | `academic-years.csv` | Academic year setup and current-year selection |
| Academic > Courses | `courses.csv` | Course master testing |
| Academic > Branches | `branches.csv` | Branch/department master testing |
| Academic > Classes | `classes.csv` | Semester/class creation testing |
| Academic > Sections | `sections.csv` | Section capacity and dropdown testing |
| Academic > Subjects | `subjects.csv` | Subject master and class mapping testing |
| Teachers | `teachers.csv` | Faculty profile creation testing |
| HOD Linking / Teacher Linking | `teacher-linking-screen.csv` | Teacher-subject-section mapping reference |
| Class Mentor Management | `class-mentors-screen.csv` | Mentor assignment screen testing |
| Timetable | `timetable-screen.csv` | Teacher period/hour schedule testing |
| Students > Admissions / Registry | `students.csv` | 180 realistic student admissions |
| Students > Documents | `student-documents.csv` | Student document verification testing |
| Attendance | `attendance-screen.csv` | 750 attendance marking rows for UI testing |
| Materials & Assignments | `teacher-content-screen.csv` | Material, assessment and assignment screen testing |
| Fees > Types | `fee-types.csv` | Fee type master testing |
| Fees | `fee-structures.csv` | Course-wise fee setup testing |
| Fees > Collect | `student-fees.csv` | 360 student fee dues for collection testing |
| Exams | `exams.csv` | Exam creation workflow testing |
| Exams > Subjects | `exam-subjects.csv` | Subject mapping for exams |
| Exams > Marks | `marks.csv` | 864 marks upload rows |
| Library | `library-books.csv` | 120 book catalog records |
| Library > Issue Book | `library-issues-screen.csv` | Book issue/return workflow reference |
| Notifications | `notifications-screen.csv` | Student/parent notification test data |
| Reports | `reports-screen.csv` | Filter scenarios for report testing |

## Notes

- Academic year: `2026-27`
- Default password: `Demo@123`
- Use CSV files for direct backend bulk import.
- Use `scholaris_institute_mock_dataset.xlsx` when you want one Excel workbook with all sheets.
- Screen-testing CSVs are reference data for screens that do not yet have a direct bulk import endpoint.
