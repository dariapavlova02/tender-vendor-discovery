#!/usr/bin/env python3
import os
import sys

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


def create_database(
    host: str = "localhost",
    port: int = 5432,
    user: str = "postgres",
    password: str = "postgres",
    dbname: str = "vendor_ai"
):
    print(f"Connecting to PostgreSQL at {host}:{port}...")
    
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database="postgres"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        cursor = conn.cursor()
        
        cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{dbname}'")
        exists = cursor.fetchone()
        
        if exists:
            print(f"Database '{dbname}' already exists.")
        else:
            cursor.execute(f"CREATE DATABASE {dbname}")
            print(f"Database '{dbname}' created successfully.")
        
        cursor.close()
        conn.close()
        
        return True
        
    except psycopg2.Error as e:
        print(f"Error: {e}")
        return False


def run_migrations():
    print("\nRunning Alembic migrations...")
    
    import subprocess
    
    try:
        result = subprocess.run(
            ["poetry", "run", "alembic", "upgrade", "head"],
            check=True,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        print("✓ Migrations completed successfully.")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Error running migrations: {e}")
        print(e.stderr)
        return False


def verify_setup():
    print("\nVerifying database setup...")
    
    from src.vendor_ai_agent.database import get_session
    from src.vendor_ai_agent.database.models import Vendor
    
    try:
        with get_session() as session:
            count = session.query(Vendor).count()
            print(f"✓ Database connection successful. Current vendor count: {count}")
        return True
        
    except Exception as e:
        print(f"Error verifying setup: {e}")
        return False


def main():
    print("=" * 60)
    print("Vendor AI Agent - Database Setup")
    print("=" * 60)
    
    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/vendor_ai")
    print(f"\nUsing DATABASE_URL: {db_url}")
    
    print("\nStep 1: Creating database...")
    if not create_database():
        print("Failed to create database. Please check your PostgreSQL connection.")
        sys.exit(1)
    
    print("\nStep 2: Running migrations...")
    if not run_migrations():
        print("Failed to run migrations.")
        sys.exit(1)
    
    print("\nStep 3: Verifying setup...")
    if not verify_setup():
        print("Failed to verify setup.")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✓ Database setup completed successfully!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Set your SAM_API_KEY in .env")
    print("2. Run: python -m src.vendor_ai_agent.sources.sam_entity (to test)")
    print("3. Integrate with your pipeline")


if __name__ == "__main__":
    main()
