"""
Prompt Loader Utility

Centralized prompt management for loading prompts from text files.
"""
from pathlib import Path
from typing import Dict
import logging

logger = logging.getLogger(__name__)

# Base prompts directory - go up to backend/ then to prompts/
# Path: backend/app/utils/prompt_loader.py -> backend/prompts/
PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


class PromptLoader:
    """Loads and caches prompt templates from files"""
    
    _cache: Dict[str, str] = {}
    
    @classmethod
    def load(cls, category: str, prompt_name: str) -> str:
        """
        Load a prompt from file
        
        Args:
            category: Prompt category (e.g., 'presentation', 'chat')
            prompt_name: Prompt file name without extension (e.g., 'system', 'user')
            
        Returns:
            Prompt text
            
        Raises:
            FileNotFoundError: If prompt file doesn't exist
        """
        cache_key = f"{category}/{prompt_name}"
        
        # Return from cache if available
        if cache_key in cls._cache:
            return cls._cache[cache_key]
        
        # Try .prompt extension first, then .txt (backward compatibility)
        prompt_path = PROMPTS_DIR / category / f"{prompt_name}.prompt"
        if not prompt_path.exists():
            prompt_path = PROMPTS_DIR / category / f"{prompt_name}.txt"
        
        if not prompt_path.exists():
            raise FileNotFoundError(
                f"Prompt file not found: {prompt_path}\n"
                f"Expected location: backend/prompts/{category}/{prompt_name}.prompt or .txt"
            )
        
        try:
            prompt_text = prompt_path.read_text(encoding="utf-8").strip()
            cls._cache[cache_key] = prompt_text
            logger.debug(f"Loaded prompt: {cache_key} from {prompt_path.name}")
            return prompt_text
        except Exception as e:
            logger.error(f"Failed to load prompt {cache_key}: {e}")
            raise
    
    @classmethod
    def clear_cache(cls):
        """Clear the prompt cache (useful for development/testing)"""
        cls._cache.clear()
        logger.info("Prompt cache cleared")
    
    @classmethod
    def reload(cls, category: str, prompt_name: str) -> str:
        """
        Force reload a prompt from file (bypassing cache)
        
        Args:
            category: Prompt category
            prompt_name: Prompt file name without extension
            
        Returns:
            Prompt text
        """
        cache_key = f"{category}/{prompt_name}"
        if cache_key in cls._cache:
            del cls._cache[cache_key]
        return cls.load(category, prompt_name)


# Convenience functions
def load_prompt(category: str, prompt_name: str) -> str:
    """Load a prompt from file (convenience function)"""
    return PromptLoader.load(category, prompt_name)


def load_presentation_prompt(prompt_name: str) -> str:
    """Load a presentation-related prompt"""
    return PromptLoader.load("presentation", prompt_name)
