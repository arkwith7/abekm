#!/usr/bin/env python3
import asyncio
import sys
import os
sys.path.append('backend')

from backend.app.core.database import get_db
from sqlalchemy import text

async def check_container_names():
    """Check current container names in the database"""
    try:
        db = await anext(get_db())
        
        # Get all container names
        result = await db.execute(text("""
            SELECT container_id, container_name, container_path, container_icon 
            FROM tb_knowledge_containers 
            ORDER BY container_id
        """))
        rows = result.fetchall()
        
        print("Current container data:")
        print("-" * 80)
        for row in rows:
            print(f"ID: {row.container_id}")
            print(f"Name: {row.container_name}")
            print(f"Path: {row.container_path}")
            print(f"Icon: {row.container_icon}")
            print("-" * 40)
            
        await db.close()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_container_names())
