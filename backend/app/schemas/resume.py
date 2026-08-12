from pydantic import BaseModel


class ResumeExtractOut(BaseModel):
    filename: str | None = None
    text: str
