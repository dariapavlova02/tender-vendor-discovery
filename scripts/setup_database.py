"""Apply schema migrations to DATABASE_URL (SQLite by default)."""
from alembic import command
from alembic.config import Config


def main():
    command.upgrade(Config("alembic.ini"), "head")
    print("Database migrations applied.")


if __name__ == "__main__":
    main()
