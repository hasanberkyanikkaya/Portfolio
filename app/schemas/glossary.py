from pydantic import BaseModel


class GlossaryTerm(BaseModel):
    term: str
    definition: str


class GlossaryResponse(BaseModel):
    terms: list[GlossaryTerm]
