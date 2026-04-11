from fastapi import APIRouter, HTTPException

from backend.models import LeadUpdate
from backend.services.leads import get_leads, get_lead, update_lead

router = APIRouter(prefix="/api/leads", tags=["leads"])


@router.get("")
async def list_leads():
    """List all leads."""
    return get_leads()


@router.get("/{lead_id}")
async def get_single_lead(lead_id: int):
    """Get a single lead by ID."""
    lead = get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.put("/{lead_id}")
async def modify_lead(lead_id: int, data: LeadUpdate):
    """Update a lead's information."""
    existing = get_lead(lead_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead_data = data.model_dump(exclude_none=True)
    result = update_lead(lead_id, lead_data)
    return result
