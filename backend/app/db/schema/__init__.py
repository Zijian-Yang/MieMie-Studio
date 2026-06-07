"""SQLAlchemy schema metadata for PostgreSQL-backed domains."""

from sqlalchemy import MetaData


metadata = MetaData()

from app.db.schema.video_studio_tasks import video_studio_tasks  # noqa: E402,F401
from app.db.schema.studio_tasks import studio_tasks  # noqa: E402,F401
from app.db.schema.projects import projects  # noqa: E402,F401
