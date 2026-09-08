# Excel workspace contract

- SQLite is authoritative. The workbook imports service exports and sends explicit user actions through the local API.
- `更新岗位` opens the loopback control page. `刷新结果` imports the latest export. Failure must leave the current workbook intact.
- Only one row may be selected for `生成简历方案`.
- `hidden` applies to one exact job. `applied` is hidden from the default view but remains filterable.
- Never place identity documents, credentials, API keys, passwords, or raw private files in Excel.
