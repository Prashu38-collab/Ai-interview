from fastapi import APIRouter, File, UploadFile, status

from app.schemas.resume import ResumeExtractOut
from app.services.resume_extractor import extract_pdf_text

router = APIRouter(prefix="/resume", tags=["resume"])


@router.post("/extract", response_model=ResumeExtractOut, status_code=status.HTTP_200_OK)
async def extract_resume(file: UploadFile = File(...)) -> ResumeExtractOut:
    """Upload a PDF resume and get its extracted plain text.

    The frontend shows the text for confirmation before the interview is
    created, so the candidate can fix OCR noise or add missing details.
    """
    content = await file.read()
    return ResumeExtractOut(
        filename=file.filename,
        text=extract_pdf_text(content),
    )
