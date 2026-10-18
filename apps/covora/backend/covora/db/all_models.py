"""Import every ORM model so SQLAlchemy knows all tables (and can resolve foreign keys) in any process."""

import covora.campaigns.models
import covora.discovery.models
import covora.icp.models
import covora.jobs.models
import covora.memory.models
import covora.observability.models
import covora.qualification.models
import covora.research.models
import covora.workspace.models  # noqa: F401
