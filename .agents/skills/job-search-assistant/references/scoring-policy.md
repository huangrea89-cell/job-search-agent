# Filtering and scoring policy

Read `config/scoring.yaml` as the executable rule source.

- Hard-filter confirmed non-target cities, non-full-time roles, PhD-required or PhD-preferred roles, sales, pure project management, required 1+ years full-time experience, confirmed micro companies, outsourcing, dispatch, unknown-employer agency postings, and closed roles.
- Keep ambiguous requirements and mark them `needs_confirmation`; do not infer a negative fact from missing text.
- Do not hard-filter a job solely because it explicitly targets 2027 graduates. Keep its match score and mark `校招资格不符合` in the Excel qualification/risk column when the candidate's June 2026 graduation does not satisfy the posting.
- Score expectations out of 50 and resume fit out of 50. Preserve 2-5 stars; filter totals below 40.
- Company quality and published salary affect ordering only within a star band.
- Store evidence, gaps, rule version, and confidence with every score. Star rating is not an employment probability.
