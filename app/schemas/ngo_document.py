from pydantic import BaseModel


class NGODocumentCreate(BaseModel):
    document_type: str
    file_url: str
