import asyncio, sys, subprocess, time, requests
sys.path.insert(0, ".")

from app.core.database import AsyncSessionLocal
from sqlalchemy import text

async def check_schema():
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'langchain_pg_embedding'
            ORDER BY ordinal_position
        """))
        for row in result:
            print(f"  {row.column_name}: {row.data_type}")
        
        # Also check count
        result2 = await session.execute(text("SELECT count(*) FROM langchain_pg_embedding"))
        count = result2.scalar()
        print(f"\nTotal rows: {count}")
        
        # Get a sample row
        result3 = await session.execute(text("""
            SELECT id, collection_id, cmetadata::text, custom_id 
            FROM langchain_pg_embedding 
            LIMIT 1
        """))
        for row in result3:
            print(f"\nSample row:")
            print(f"  id={row.id}")
            print(f"  collection_id={row.collection_id}")
            print(f"  cmetadata={row.cmetadata[:200]}")
            try:
                print(f"  custom_id={row.custom_id}")
            except:
                print(f"  <no custom_id column>")
                
        # Try uuid
        try:
            result4 = await session.execute(text("""
                SELECT uuid FROM langchain_pg_embedding LIMIT 1
            """))
            for row in result4:
                print(f"  uuid={row.uuid}")
        except Exception as e:
            print(f"  <no uuid column: {e}>")

asyncio.run(check_schema())
