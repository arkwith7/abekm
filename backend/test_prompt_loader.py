#!/usr/bin/env python3
"""
Prompt Loader Test Script

Tests the prompt loader functionality and displays loaded prompts.
"""
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.prompt_loader import load_presentation_prompt, PromptLoader


def test_prompt_loading():
    """Test loading all presentation prompts"""
    
    prompts = [
        ("content_structurer_system", "Content Structurer System"),
        ("content_structurer_user", "Content Structurer User"),
        ("html_generator_system", "HTML Generator System"),
        ("html_generator_user", "HTML Generator User"),
    ]
    
    print("=" * 80)
    print("PRESENTATION PROMPT LOADER TEST")
    print("=" * 80)
    print()
    
    for prompt_name, display_name in prompts:
        print(f"📄 {display_name}")
        print("-" * 80)
        
        try:
            prompt_text = load_presentation_prompt(prompt_name)
            
            # Display first 200 chars
            preview = prompt_text[:200]
            if len(prompt_text) > 200:
                preview += "..."
            
            print(f"✅ Loaded successfully ({len(prompt_text)} chars)")
            print(f"Preview: {preview}")
            print()
            
        except FileNotFoundError as e:
            print(f"❌ File not found: {e}")
            print()
        except Exception as e:
            print(f"❌ Error: {e}")
            print()
    
    # Test cache
    print("=" * 80)
    print("CACHE TEST")
    print("=" * 80)
    print(f"Cache size: {len(PromptLoader._cache)} items")
    print(f"Cached keys: {list(PromptLoader._cache.keys())}")
    print()
    
    # Test reload
    print("=" * 80)
    print("RELOAD TEST")
    print("=" * 80)
    print("Clearing cache...")
    PromptLoader.clear_cache()
    print(f"Cache size after clear: {len(PromptLoader._cache)} items")
    print()
    
    print("Reloading content_structurer_system...")
    reloaded = PromptLoader.reload("presentation", "content_structurer_system")
    print(f"✅ Reloaded ({len(reloaded)} chars)")
    print(f"Cache size: {len(PromptLoader._cache)} items")
    print()


if __name__ == "__main__":
    test_prompt_loading()
