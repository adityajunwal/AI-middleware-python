import json

from config import Config
from src.services.utils.apiservice import fetch
from src.services.utils.logger import logger

# Hippocampus API URLs
HIPPOCAMPUS_RESOURCE_URL = "http://hippocampus.gtwy.ai/resource"
HIPPOCAMPUS_SEARCH_URL = "http://hippocampus.gtwy.ai/search"


async def save_conversation_to_hippocampus(
    user_message: str,
    assistant_message: str,
    agent_id: str,
    bridge_name: str = "",
    system_prompt: str = ""
):
    """
    Save conversation to Hippocampus with intelligent processing.
    
    Uses Canonicalizer AI to process questions, tracks frequency in MongoDB,
    and deduplicates similar questions for FAQ generation.
    
    Args:
        user_message: The user's message content
        assistant_message: The assistant's response content
        agent_id: The bridge/agent ID
        bridge_name: The bridge/agent name (optional, not used)
        system_prompt: The agent's system prompt (for Canonicalizer)
    """
    try:
        if not Config.CANONICALIZER_AGENT_ID:
            logger.warning("Hippocampus: Canonicalizer agent ID not configured")
            return
        
        from src.services.agent_memory_service import save_to_agent_memory
        
        await save_to_agent_memory(
            user_question=user_message,
            assistant_answer=assistant_message,
            agent_id=agent_id,
            system_prompt=system_prompt,
            canonicalizer_agent_id=Config.CANONICALIZER_AGENT_ID,
            bridge_name=bridge_name
        )
        
    except Exception as e:
        logger.error(f"Hippocampus: Error saving conversation: {str(e)}")
