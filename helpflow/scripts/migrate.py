"""Idempotent local schema migration. Preserves existing rows."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import migrate_schema, Base, engine
Base.metadata.create_all(engine)
migrate_schema()
print('HelpFlow database migration complete; existing data preserved.')
