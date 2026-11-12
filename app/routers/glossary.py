from fastapi import APIRouter

from app.schemas.glossary import GlossaryResponse
from app.services.glossary import GLOSSARY

router = APIRouter(prefix="/glossary", tags=["glossary"])


@router.get("", response_model=GlossaryResponse)
async def get_glossary() -> GlossaryResponse:
    """Static educational term definitions — no DB, no external APIs."""
    return GlossaryResponse(terms=GLOSSARY)
