"""
Agent Memory Model

Stores frequency and metadata for agent-level memories.
Uses Canonicalizer agent for question processing.
"""

from models.mongo_connection import db
from datetime import datetime
from typing import Optional

# MongoDB collection for agent memory tracking
agent_memory_collection = db['agent_memories']


async def create_memory_record(
    resource_id: str,
    agent_id: str,
    canonical_question: str,
    original_answer: Optional[str] = None
) -> dict:
    """
    Create a new memory record in MongoDB with frequency = 1.
    
    Args:
        resource_id: Hippocampus resource ID
        agent_id: Agent/bridge ID
        canonical_question: Canonical form of question from Canonicalizer
        original_answer: The LLM's original response (optional, None if save_response=false)
    
    Returns:
        The created document
    """
    document = {
        "resource_id": resource_id,
        "agent_id": agent_id,
        "canonical_question": canonical_question,
        "original_answer": original_answer,  # Can be None
        "frequency": 1,
        "created_at": datetime.utcnow(),
        "last_seen": datetime.utcnow()
    }
    
    result = await agent_memory_collection.insert_one(document)
    document['_id'] = result.inserted_id
    return document


async def increment_memory_frequency(resource_id: str) -> bool:
    """
    Increment the frequency counter for an existing memory.
    
    Args:
        resource_id: Hippocampus resource ID
    
    Returns:
        True if updated successfully, False otherwise
    """
    result = await agent_memory_collection.update_one(
        {"resource_id": resource_id},
        {
            "$inc": {"frequency": 1},
            "$set": {"last_seen": datetime.utcnow()}
        }
    )
    
    return result.modified_count > 0


async def get_memory_by_resource_id(resource_id: str) -> Optional[dict]:
    """
    Get memory record by Hippocampus resource ID.
    
    Args:
        resource_id: Hippocampus resource ID
    
    Returns:
        Memory document or None
    """
    return await agent_memory_collection.find_one({"resource_id": resource_id})


async def get_top_memories_by_frequency(agent_id: str, limit: int = 10) -> list:
    """
    Get top N most frequently asked questions for an agent.
    
    Args:
        agent_id: Agent/bridge ID
        limit: Number of top memories to return
    
    Returns:
        List of memory documents sorted by frequency
    """
    cursor = await agent_memory_collection.find(
        {"agent_id": agent_id}
    ).sort("frequency", -1).limit(limit)
    
    return await cursor.to_list(length=limit)
