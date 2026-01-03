"""
Prompt Loader Utility

Agent-local prompt management for loading prompts from text files.
프롬프트는 각 에이전트의 prompts/ 디렉토리에 위치합니다:
- app/agents/features/presentation/prompts/
- app/agents/features/search_rag/prompts/
"""
from pathlib import Path
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Agent prompts directories (각 에이전트 로컬 디렉토리)
AGENTS_BASE_DIR = Path(__file__).resolve().parents[1] / "agents" / "features"

# Agent category to directory mapping
AGENT_PROMPT_DIRS = {
    "presentation": AGENTS_BASE_DIR / "presentation" / "prompts",
    "search_rag": AGENTS_BASE_DIR / "search_rag" / "prompts",
    "patent": AGENTS_BASE_DIR / "patent" / "prompts",
}


class PromptLoader:
    """Loads and caches prompt templates from agent-local directories"""
    
    _cache: Dict[str, str] = {}
    
    @classmethod
    def load(cls, category: str, prompt_name: str) -> str:
        """
        Load a prompt from agent-local prompts directory
        
        Args:
            category: Agent category (e.g., 'presentation', 'search_rag')
            prompt_name: Prompt file name without extension (e.g., 'react_agent_system')
            
        Returns:
            Prompt text
            
        Raises:
            FileNotFoundError: If prompt file doesn't exist
        """
        cache_key = f"{category}/{prompt_name}"
        
        # Return from cache if available
        if cache_key in cls._cache:
            return cls._cache[cache_key]
        
        # Get the prompts directory for this category
        prompts_dir = AGENT_PROMPT_DIRS.get(category)
        if not prompts_dir:
            raise FileNotFoundError(
                f"Unknown prompt category: {category}\n"
                f"Available categories: {list(AGENT_PROMPT_DIRS.keys())}"
            )
        
        # Try .prompt extension first, then .txt (backward compatibility)
        prompt_path = prompts_dir / f"{prompt_name}.prompt"
        if not prompt_path.exists():
            prompt_path = prompts_dir / f"{prompt_name}.txt"
        
        if not prompt_path.exists():
            raise FileNotFoundError(
                f"Prompt file not found: {prompt_path}\n"
                f"Expected location: {prompts_dir}/{prompt_name}.prompt or .txt"
            )
        
        try:
            prompt_text = prompt_path.read_text(encoding="utf-8").strip()
            cls._cache[cache_key] = prompt_text
            logger.debug(f"Loaded prompt: {cache_key} from {prompt_path}")
            return prompt_text
        except Exception as e:
            logger.error(f"Failed to load prompt {cache_key}: {e}")
            raise
    
    @classmethod
    def load_from_path(cls, prompt_path: Path) -> str:
        """
        Load a prompt directly from a file path
        
        Args:
            prompt_path: Absolute path to the prompt file
            
        Returns:
            Prompt text
        """
        cache_key = str(prompt_path)
        
        if cache_key in cls._cache:
            return cls._cache[cache_key]
        
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
        
        try:
            prompt_text = prompt_path.read_text(encoding="utf-8").strip()
            cls._cache[cache_key] = prompt_text
            logger.debug(f"Loaded prompt from path: {prompt_path}")
            return prompt_text
        except Exception as e:
            logger.error(f"Failed to load prompt from {prompt_path}: {e}")
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
            category: Agent category
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
    """Load a prompt from agent-local directory (convenience function)"""
    return PromptLoader.load(category, prompt_name)


def load_presentation_prompt(prompt_name: str) -> str:
    """Load a presentation-related prompt from presentation agent's prompts directory"""
    return PromptLoader.load("presentation", prompt_name)


def load_search_rag_prompt(prompt_name: str) -> str:
    """Load a search_rag-related prompt from search_rag agent's prompts directory"""
    return PromptLoader.load("search_rag", prompt_name)
