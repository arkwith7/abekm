"""Text-to-SQL feature-pack.

This feature provides a Supervisor worker that can translate natural language
questions into safe, read-only SQL and execute it against a configured
read-only database connection.

Current implementation defaults to using the application DB session
(`get_db_session_context`) for execution, and is designed to be extended to
external connections later.
"""

__all__ = []
