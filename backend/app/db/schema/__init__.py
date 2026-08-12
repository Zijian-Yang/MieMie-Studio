"""SQLAlchemy schema metadata for PostgreSQL-backed domains."""

from sqlalchemy import MetaData


metadata = MetaData()

from app.db.schema.video_studio_tasks import video_studio_tasks  # noqa: E402,F401
from app.db.schema.studio_tasks import studio_tasks  # noqa: E402,F401
from app.db.schema.projects import projects  # noqa: E402,F401
from app.db.schema.media_assets import media_assets, text_items  # noqa: E402,F401
from app.db.schema.project_entities import project_entities  # noqa: E402,F401
from app.db.schema.benchmark_records import benchmark_records  # noqa: E402,F401
from app.db.schema.user_config import user_configs, users  # noqa: E402,F401
from app.db.schema.sessions import sessions  # noqa: E402,F401
from app.db.schema.audio_studio import audio_studio_tasks, voice_profiles  # noqa: E402,F401
from app.db.schema.platform_admin import admin_audit_logs, platform_settings  # noqa: E402,F401
