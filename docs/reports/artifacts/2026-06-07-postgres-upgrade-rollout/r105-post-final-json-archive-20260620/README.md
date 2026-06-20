# R105 Post-Final JSON Archive

## Summary

- Run ID: `r105-post-final-json-archive-20260620`
- Result: `passed`
- Completion gate: R103 `postgres_only_complete`
- Archived tracked JSON files: `70`
- Moved files: `70`

## Scope

This archived tracked business-state JSON that already had PostgreSQL migration coverage. Counts by domain were `projects=9`, `sessions=1`, `studio=12`, `user_config=42`, and `video_studio=6`.

The server created `validation-artifacts/r105-post-final-json-archive-20260620/tracked-json-before-archive.r105-post-final-json-archive-20260620.tar.gz` before moving files into `backend/data/_postgres_final_json_archive/r105-post-final-json-archive-20260620/`.

## Repository Safety

The tarball contains historical user/business JSON and intentionally remains on the server. The repository only stores summary files and the manifest.
