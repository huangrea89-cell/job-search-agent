# Job pipeline

- Run updates only after a user action; there is no background scheduler in MVP.
- For browser-assisted BOSS discovery, use the fixed city order `上海 → 苏州 → 杭州`. In each city, search the broad keyword `AI` first, review the returned jobs one by one, and then combine all matching jobs from the three cities into the same SQLite-backed Excel workspace.
- Do not stop after reviewing only one city or a small first-screen sample when the user asks for a three-city search. Record suitable jobs and low-confidence review candidates; exclude only according to the scoring policy.
- Prefer the employer's official posting as the canonical source. Keep all alternate source URLs.
- Official public pages may be fetched only when access rules permit it. BOSS and 牛客 require browser-assisted discovery or explicit URL/text import.
- Normalize source records before deduplication. Merge on official job ID, then platform ID, then normalized company/title/accepted city/employment type.
- Similarity-only matches are review candidates, never automatic merges.
- A missing page becomes `unknown` first and `closed` only after two consecutive failed checks. Preserve applied jobs forever.
- Isolate source failures. Finish other enabled sources, then report skipped, failed, and login-required sources together.
