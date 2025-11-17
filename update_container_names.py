#!/usr/bin/env python3
import asyncio
import sys
import os
sys.path.append('backend')

from backend.app.core.database import get_db
from sqlalchemy import text

async def check_and_update_container_names():
    """Check current container names and update them to remove icons"""
    
    # Get database session
    db_gen = get_db()
    db = await anext(db_gen)
    
    try:
        # First, check table structure
        print("Checking table structure...")
        result = await db.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'tb_knowledge_containers'
            ORDER BY ordinal_position
        """))
        columns = result.fetchall()
        print("Available columns:")
        for col in columns:
            print(f"  {col.column_name}: {col.data_type}")
        
        print("\n" + "="*60)
        
        # Check current container names
        print("Current container names:")
        result = await db.execute(text("""
            SELECT container_id, container_name 
            FROM tb_knowledge_containers 
            ORDER BY container_id
        """))
        rows = result.fetchall()
        
        for row in rows:
            print(f"  {row.container_id}: {row.container_name}")
        
        print("\n" + "="*60)
        
        # Update container names to remove icons
        print("Updating container names to remove icons...")
        
        updates = []
        for row in rows:
            original_name = row.container_name
            # Remove common icons
            new_name = original_name
            
            # Remove folder icon 📁
            if "📁" in new_name:
                new_name = new_name.replace("📁", "").strip()
            
            # Remove building icon 🏢
            if "🏢" in new_name:
                new_name = new_name.replace("🏢", "").strip()
            
            # Remove other potential icons (📊, 📈, 📋, etc.)
            icons_to_remove = ["📊", "📈", "📋", "📝", "📂", "🏪", "🏬", "🏭", "🏯", "🏰"]
            for icon in icons_to_remove:
                if icon in new_name:
                    new_name = new_name.replace(icon, "").strip()
            
            if original_name != new_name:
                updates.append((row.container_id, original_name, new_name))
        
        if not updates:
            print("No icons found in container names. No updates needed.")
            return
        
        print(f"Found {len(updates)} containers with icons to update:")
        for container_id, old_name, new_name in updates:
            print(f"  {container_id}: '{old_name}' -> '{new_name}'")
        
        # Confirm before updating
        print(f"\nThis will update {len(updates)} container names.")
        confirm = input("Do you want to proceed with the updates? (y/N): ")
        
        if confirm.lower() in ['y', 'yes']:
            # Perform updates
            for container_id, old_name, new_name in updates:
                await db.execute(text("""
                    UPDATE tb_knowledge_containers 
                    SET container_name = :new_name 
                    WHERE container_id = :container_id
                """), {
                    "new_name": new_name,
                    "container_id": container_id
                })
            
            await db.commit()
            print(f"Successfully updated {len(updates)} container names!")
            
            # Show updated names
            print("\nUpdated container names:")
            result = await db.execute(text("""
                SELECT container_id, container_name 
                FROM tb_knowledge_containers 
                ORDER BY container_id
            """))
            updated_rows = result.fetchall()
            
            for row in updated_rows:
                print(f"  {row.container_id}: {row.container_name}")
        else:
            print("Update cancelled.")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        await db.rollback()
    
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(check_and_update_container_names())
