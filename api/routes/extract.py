"""AI opportunity-extraction route.

Turns a single blob of pasted, unstructured text (recruiter emails, LinkedIn
messages, WhatsApp chats, job descriptions, mixed threads) into a structured
list of opportunities via the LLM-backed OpportunityExtractor agent.
"""
from fastapi import APIRouter, Depends, HTTPException

from agents.extractor import OpportunityExtractor
from api.dependencies.security import get_current_user
from config.logging import logger
from models.database.models import UserDB
from models.schemas import ExtractRequest, ExtractResponse

router = APIRouter(prefix="/api/extract", tags=["extraction"])

extractor = OpportunityExtractor()


@router.post("", response_model=ExtractResponse)
async def extract_opportunities(payload: ExtractRequest, current_user: UserDB = Depends(get_current_user)):
    if not payload.raw_text or not payload.raw_text.strip():
        raise HTTPException(status_code=400, detail="Please paste some text to extract opportunities from.")

    if not extractor.is_available():
        raise HTTPException(
            status_code=503,
            detail="AI extraction is unavailable: GROQ_API_KEY is not configured on the server.",
        )

    try:
        opportunities = extractor.extract(payload.raw_text)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Extraction failed: {e}")

    if not opportunities:
        raise HTTPException(
            status_code=422,
            detail="No opportunities were found in the pasted text. Try including company names, "
            "emails, or role details.",
        )

    return ExtractResponse(opportunities=opportunities)
