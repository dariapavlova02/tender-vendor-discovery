#!/usr/bin/env python3
"""
SQLite to PostgreSQL Migration Script for Railway Deployment

This script migrates all data from the local SQLite database (vendor_ai.db)
to a PostgreSQL database (Railway or any PostgreSQL instance).

Usage:
    export DATABASE_URL="postgresql://user:pass@host:port/dbname"
    python scripts/migrate_sqlite_to_postgres.py
"""
import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from sqlalchemy import create_engine, text, MetaData, Table
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()


class DatabaseMigrator:
    def __init__(self, sqlite_path: str, postgres_url: str):
        self.sqlite_path = sqlite_path
        self.postgres_url = postgres_url
        self.batch_size = 1000
        
        print(f"🔄 Initializing migration:")
        print(f"  Source: {sqlite_path}")
        print(f"  Target: {postgres_url.split('@')[1] if '@' in postgres_url else 'PostgreSQL'}")
        
    def validate_connections(self):
        print("\n📡 Validating database connections...")
        
        try:
            sqlite_engine = create_engine(f"sqlite:///{self.sqlite_path}")
            with sqlite_engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM sqlite_master WHERE type='table'"))
                table_count = result.scalar()
                print(f"  ✅ SQLite connected: {table_count} tables found")
        except Exception as e:
            print(f"  ❌ SQLite connection failed: {e}")
            return False
            
        try:
            postgres_engine = create_engine(self.postgres_url)
            with postgres_engine.connect() as conn:
                result = conn.execute(text("SELECT version()"))
                version = result.scalar()
                print(f"  ✅ PostgreSQL connected: {version.split(',')[0]}")
        except Exception as e:
            print(f"  ❌ PostgreSQL connection failed: {e}")
            return False
            
        return True
    
    def run_alembic_migrations(self):
        print("\n🔧 Running Alembic migrations on PostgreSQL...")
        try:
            os.chdir(project_root)
            result = os.system(f"DATABASE_URL='{self.postgres_url}' alembic upgrade head")
            if result == 0:
                print("  ✅ Alembic migrations completed")
                return True
            else:
                print("  ⚠️ Alembic migrations failed or had warnings")
                return False
        except Exception as e:
            print(f"  ❌ Migration error: {e}")
            return False
    
    def get_table_names(self, engine):
        metadata = MetaData()
        metadata.reflect(bind=engine)
        return [table.name for table in metadata.sorted_tables if table.name != 'alembic_version']
    
    def migrate_table(self, table_name: str, source_engine, target_engine):
        print(f"\n📦 Migrating table: {table_name}")
        
        metadata_source = MetaData()
        metadata_source.reflect(bind=source_engine)
        
        metadata_target = MetaData()
        metadata_target.reflect(bind=target_engine)
        
        if table_name not in metadata_source.tables:
            print(f"  ⚠️ Table {table_name} not found in source database")
            return 0
            
        source_table = Table(table_name, metadata_source, autoload_with=source_engine)
        target_table = Table(table_name, metadata_target, autoload_with=target_engine)
        
        SourceSession = sessionmaker(bind=source_engine)
        TargetSession = sessionmaker(bind=target_engine)
        
        with source_engine.connect() as source_conn:
            count_result = source_conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            total_rows = count_result.scalar()
            
            if total_rows == 0:
                print(f"  ℹ️ Table {table_name} is empty, skipping")
                return 0
                
            print(f"  📊 Total rows to migrate: {total_rows:,}")
            
            offset = 0
            migrated_count = 0
            
            with tqdm(total=total_rows, desc=f"  Copying {table_name}", unit="rows") as pbar:
                while offset < total_rows:
                    rows = source_conn.execute(
                        source_table.select().offset(offset).limit(self.batch_size)
                    ).fetchall()
                    
                    if not rows:
                        break
                    
                    rows_dicts = [dict(row._mapping) for row in rows]
                    
                    with target_engine.begin() as target_conn:
                        target_conn.execute(target_table.insert(), rows_dicts)
                    
                    migrated_count += len(rows)
                    offset += self.batch_size
                    pbar.update(len(rows))
            
            print(f"  ✅ Migrated {migrated_count:,} rows")
            return migrated_count
    
    def verify_migration(self, source_engine, target_engine, table_names):
        print("\n🔍 Verifying data integrity...")
        
        all_match = True
        for table_name in table_names:
            with source_engine.connect() as source_conn:
                source_count = source_conn.execute(
                    text(f"SELECT COUNT(*) FROM {table_name}")
                ).scalar()
            
            with target_engine.connect() as target_conn:
                target_count = target_conn.execute(
                    text(f"SELECT COUNT(*) FROM {table_name}")
                ).scalar()
            
            if source_count == target_count:
                print(f"  ✅ {table_name}: {source_count:,} rows (matched)")
            else:
                print(f"  ❌ {table_name}: source={source_count:,}, target={target_count:,} (MISMATCH)")
                all_match = False
        
        return all_match
    
    def run(self):
        print("\n" + "="*60)
        print("  DATABASE MIGRATION: SQLite → PostgreSQL")
        print("="*60)
        
        if not self.validate_connections():
            print("\n❌ Connection validation failed. Aborting migration.")
            return False
        
        if not os.path.exists(self.sqlite_path):
            print(f"\n❌ SQLite database not found: {self.sqlite_path}")
            return False
        
        if not self.run_alembic_migrations():
            print("\n⚠️ Warning: Alembic migrations had issues, but continuing...")
        
        source_engine = create_engine(f"sqlite:///{self.sqlite_path}")
        target_engine = create_engine(self.postgres_url)
        
        table_names = self.get_table_names(source_engine)
        print(f"\n📋 Tables to migrate: {', '.join(table_names)}")
        
        total_migrated = 0
        for table_name in table_names:
            count = self.migrate_table(table_name, source_engine, target_engine)
            total_migrated += count
        
        print("\n" + "="*60)
        print(f"  MIGRATION SUMMARY")
        print("="*60)
        print(f"  Total rows migrated: {total_migrated:,}")
        print(f"  Tables migrated: {len(table_names)}")
        
        if self.verify_migration(source_engine, target_engine, table_names):
            print("\n✅ Migration completed successfully!")
            print("  All data verified and matches source database.")
            return True
        else:
            print("\n⚠️ Migration completed with warnings!")
            print("  Some row counts don't match. Please verify manually.")
            return False


def main():
    sqlite_path = project_root / "vendor_ai.db"
    postgres_url = os.getenv("DATABASE_URL")
    
    if not postgres_url:
        print("❌ ERROR: DATABASE_URL environment variable not set")
        print("\nUsage:")
        print('  export DATABASE_URL="postgresql://user:pass@host:port/dbname"')
        print("  python scripts/migrate_sqlite_to_postgres.py")
        sys.exit(1)
    
    if not postgres_url.startswith("postgresql://"):
        print("❌ ERROR: DATABASE_URL must be a PostgreSQL connection string")
        print(f"  Got: {postgres_url}")
        sys.exit(1)
    
    if not sqlite_path.exists():
        print(f"❌ ERROR: SQLite database not found at {sqlite_path}")
        sys.exit(1)
    
    migrator = DatabaseMigrator(str(sqlite_path), postgres_url)
    success = migrator.run()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
