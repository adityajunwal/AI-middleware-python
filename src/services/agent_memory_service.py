"""
Agent Memory Service with Canonicalizer Integration

Stores relevant conversations in Hippocampus and tracks frequency in MongoDB.
Uses existing Gtwy Canonicalizer agent for question processing.
"""

import json
import logging
from typing import Dict, Optional, Tuple
from config import Config
from src.services.utils.apiservice import fetch

logger = logging.getLogger(__name__)

HIPPOCAMPUS_SEARCH_URL = 'http://hippocampus.gtwy.ai/search'
HIPPOCAMPUS_RESOURCE_URL = 'http://hippocampus.gtwy.ai/resource'


async def call_canonicalizer_agent(
    system_prompt: str,
    user_message: str,
    llm_response: str,
    canonicalizer_agent_id: str
) -> Optional[dict]:
    """
    Call Gtwy Canonicalizer agent to process question.
    
    Args:
        system_prompt: Agent's system prompt
        user_message: User's original question
        llm_response: LLM's response
        canonicalizer_bridge_id: Bridge ID of Canonicalizer agent
    
    Returns:
        {
            "question": "canonical question",
            "is_agent_level": true,
            "save_response": true
        }
        or None if error
    """
    try:        
        # Prepare payload for Gtwy API
        payload = {
            "user": f"System: {system_prompt}\n\nUser: {user_message}\n\nAssistant: {llm_response}",
            "agent_id": canonicalizer_agent_id
        }
        
        headers = {
            "pauthkey": Config.AI_MIDDLEWARE_PAUTH_KEY,
            "Content-Type": "application/json"
        }
        
        # Call Gtwy API
        gtwy_api_url = "https://api.gtwy.ai/api/v2/model/chat/completion"
        
        response_data, _ = await fetch(
            url=gtwy_api_url,
            method="POST",
            headers=headers,
            json_body=payload
        )
        
        # Parse JSON response
        if not response_data:
            logger.error("Agent Memory Service: No response from Canonicalizer API")
            return None
        
        content = response_data.get('response', {}).get('data', {}).get('content', '{}')
        canonical_data = json.loads(content)
        return canonical_data
        
    except Exception as e:
        logger.error(f"Agent Memory Service: Error calling canonicalizer agent: {str(e)}")
        return None


async def search_hippocampus_for_memories(
    canonical_question: str,
    agent_id: str,
    top_k: int = 5,
    limit: int = 5,
    minScore: float = 0.9
) -> Tuple[Optional[str], float]:
    """
    Search Hippocampus for similar canonical questions.
    
    Args:
        canonical_question: Canonical form of question
        agent_id: Agent/bridge ID
        top_k: Number of top results to retrieve
    
    Returns:
        Tuple of (resource_id, score) for top match, or (None, 0.0)
    """
    try:
        headers = {
            'x-api-key': Config.HIPPOCAMPUS_API_KEY,
            'Content-Type': 'application/json'
        }
        
        payload = {
            'query': canonical_question,
            'ownerId': agent_id,
            'collectionId': Config.HIPPOCAMPUS_AGENT_MEMORY_DOC_ID,
            'top_k': top_k,
            'limit': limit,
            'minScore': minScore
        }
        
        response_data, _ = await fetch(
            url=HIPPOCAMPUS_SEARCH_URL,
            method="POST",
            headers=headers,
            json_body=payload
        )
        
        if 'result' in response_data:
            results = response_data['result']
            if results and len(results) > 0:
                top_result = results[0]
                resource_id = top_result.get('payload', {}).get('resourceId')
                score = top_result.get('score', 0.0)
                logger.info(f"Agent Memory Service: Top memory match: resource_id={resource_id}, score={score:.1%}")
                return resource_id, score
        
        return None, 0.0
        
    except Exception as e:
        logger.error(f"Agent Memory Service: Error searching Hippocampus: {str(e)}")
        return None, 0.0


async def update_frequency_in_mongodb(resource_id: str) -> bool:
    """
    Increment frequency counter in MongoDB.
    
    Args:
        resource_id: Hippocampus resource ID
    
    Returns:
        True if updated successfully
    """
    try:
        from src.models.agent_memory_model import increment_memory_frequency
        success = await increment_memory_frequency(resource_id)
        
        if success:
            logger.info(f"Agent Memory Service: Incremented frequency for resource_id: {resource_id}")
        else:
            logger.warning(f"Agent Memory Service: Memory record not found for resource_id: {resource_id}")
        
        return success
        
    except Exception as e:
        logger.error(f"Agent Memory Service: Error updating frequency: {str(e)}")
        return False


async def create_memory_in_hippocampus_and_mongodb(
    canonical_question: str,
    original_answer: Optional[str],
    agent_id: str
) -> bool:
    """
    Create new memory in Hippocampus and MongoDB.
    
    Args:
        canonical_question: Canonical form of question
        original_answer: LLM's original response (None if save_response=false)
        agent_id: Agent/bridge ID
    
    Returns:
        True if created successfully
    """
    try:
        # Create in Hippocampus
        content = json.dumps({
            "question": canonical_question,
            "answer": original_answer or ""  # Empty string if no answer
        })
        
        payload = {
            "collectionId": Config.HIPPOCAMPUS_AGENT_MEMORY_DOC_ID,
            "title": agent_id,
            "ownerId": agent_id,
            "content": content,
            "settings": {
                "strategy": "custom",
                "chunkingUrl": "https://flow.sokt.io/func/scriQywSNndU",
                "chunkSize": 4000
            }
        }
        
        headers = {
            "x-api-key": Config.HIPPOCAMPUS_API_KEY,
            "Content-Type": "application/json"
        }
        
        response_data, _ = await fetch(
            url=HIPPOCAMPUS_RESOURCE_URL,
            method="POST",
            headers=headers,
            json_body=payload
        )
        
        resource_id = response_data.get('_id') if response_data else None
        
        if not resource_id:
            logger.error("Agent Memory Service: Failed to create resource in Hippocampus")
            return False
        
        # Create in MongoDB (only store answer if provided)
        from src.models.agent_memory_model import create_memory_record
        await create_memory_record(
            resource_id=resource_id,
            agent_id=agent_id,
            canonical_question=canonical_question,
            original_answer=original_answer  # Will be None if save_response=false
        )
        
        answer_status = "with answer" if original_answer else "question only"
        logger.info(f"Agent Memory Service: Created new memory ({answer_status}, frequency=1) for agent_id: {agent_id}")
        return True
        
    except Exception as e:
        logger.error(f"Agent Memory Service: Error creating memory: {str(e)}")
        return False


async def save_to_agent_memory(
    user_question: str,
    assistant_answer: str,
    agent_id: str,
    system_prompt: str,
    canonicalizer_agent_id: str
) -> bool:
    """
    Save conversation to agent memory using Canonicalizer.
    
    Flow:
    1. Call Canonicalizer agent
    2. If is_agent_level = false → Stop
    3. If is_agent_level = true → Search Hippocampus
    4. Update frequency or create new memory
    5. Store response only if save_response = true
    
    Args:
        user_question: User's original question
        assistant_answer: LLM's response
        agent_id: Agent/bridge ID
        system_prompt: Agent's system prompt
        canonicalizer_bridge_id: Canonicalizer agent bridge ID
    
    Returns:
        True if saved/updated successfully
    """
    try:
        if not Config.HIPPOCAMPUS_API_KEY or not Config.HIPPOCAMPUS_AGENT_MEMORY_DOC_ID:
            logger.warning("Agent Memory Service: Hippocampus not configured")
            return False
        
        if not canonicalizer_agent_id:
            logger.warning("Agent Memory Service: Canonicalizer agent ID not configured")
            return False
        
        # Step 1: Call Canonicalizer agent
        canonical_data = await call_canonicalizer_agent(
            system_prompt=system_prompt,
            user_message=user_question,
            llm_response=assistant_answer,
            canonicalizer_agent_id=canonicalizer_agent_id
        )
        
        if not canonical_data:
            logger.error("Agent Memory Service: Failed to get response from Canonicalizer")
            return False
        
        # Step 2: Check if agent-level
        if not canonical_data.get('is_agent_level', False):
            logger.info(f"Agent Memory Service: Not agent-level - not saving: '{user_question[:50]}...'")
            return False
        
        canonical_question = canonical_data.get('question')
        if not canonical_question:
            logger.error("Agent Memory Service: Canonicalizer did not return canonical question")
            return False
        
        # Determine if we should save the response
        save_response = canonical_data.get('save_response', False)
        
        # Step 3: Search Hippocampus
        resource_id, score = await search_hippocampus_for_memories(
            canonical_question=canonical_question,
            agent_id=agent_id,
            top_k=5,
            limit=5,
            minScore=0.9
        )
        
        # Step 4: Update or create
        if resource_id:
            logger.info(f"Agent Memory Service: Similar memory found (score={score:.1%}), updating frequency")
            return await update_frequency_in_mongodb(resource_id)
        else:
            logger.info(f"Agent Memory Service: Creating new memory for canonical question: '{canonical_question}'")
            # Pass save_response flag to determine if we store the answer
            return await create_memory_in_hippocampus_and_mongodb(
                canonical_question=canonical_question,
                original_answer=assistant_answer if save_response else None,
                agent_id=agent_id
            )
        
    except Exception as e:
        logger.error(f"Agent Memory Service: Error in save_to_agent_memory: {str(e)}")
        return False
