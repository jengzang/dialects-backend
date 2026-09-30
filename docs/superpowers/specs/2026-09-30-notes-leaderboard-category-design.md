# `/api/notes` Leaderboard Category Design

## Goal

Include the existing `GET /api/notes` endpoint in the user leaderboard category
`category_字調查詢`.

## Scope

- Add the exact path `/api/notes` to the category's `paths` list in
  `app/service/user/leaderboard_service.py`.
- Add a regression test that verifies the exact path is included in
  `category_字調查詢`.
- Do not add a prefix rule for `/api/notes/`; no such subpath is currently part
  of the endpoint contract.

## Verification

Run the focused leaderboard/category tests and the full relevant test file if
available. Confirm the existing category rules remain unchanged apart from the
new exact path.
