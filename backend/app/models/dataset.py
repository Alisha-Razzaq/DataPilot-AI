"""Pydantic schemas for dataset upload responses."""

from pydantic import BaseModel, Field


class DatasetUploadResponse(BaseModel):
    """Public metadata returned after a successful CSV upload.

    Does not include the stored filesystem path or the dataset rows.
    """

    dataset_id: str = Field(description="Server-generated unique identifier.")
    original_filename: str = Field(
        description="Client-provided filename, used for display only."
    )
    rows: int = Field(description="Number of data rows (excluding the header).")
    columns: int = Field(description="Number of columns.")
    column_names: list[str] = Field(description="Column headers from the CSV.")
