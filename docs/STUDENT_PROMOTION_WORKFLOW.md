# Student Promotion Workflow

This workflow handles semester/year movement without overwriting old student data.

## How BCA Sem 1 moves to Sem 2

1. Admin creates the next academic year/class/section in Academic Masters if it does not already exist.
2. Admin opens `Students > Promotions`.
3. In `From`, select the current academic year, course, branch, class/semester, and section.
4. In `To`, select the target academic year, course, branch, class/semester, and section.
5. Click `Preview Students`.
6. For each student choose:
   - `Promote`: close current record and create a new active record in the target section.
   - `Detain`: keep the student in the same active record with detained status.
   - `Drop`: close the active record as dropped.
   - `Transfer out`: close the active record as transferred.
   - `Graduate`: close the active record as graduated.
7. Click `Execute Promotion`.

## Data rule

The system keeps one open academic record for the student's current placement. Historical records remain available under `Students > Academic Records`.

## Backend APIs

- `POST /api/v1/students/promotions/preview`
- `POST /api/v1/students/promotions/execute`

Both endpoints validate that source and target sections belong to the current institution.
