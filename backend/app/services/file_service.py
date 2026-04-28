from pathlib import Path

from fastapi import HTTPException, UploadFile


class FileService:
    max_file_size_bytes = 2 * 1024 * 1024
    supported_extensions = {".txt", ".md", ".csv"}

    async def read_text_file(self, file: UploadFile) -> str:
        extension = Path(file.filename or "").suffix.lower()
        if extension not in self.supported_extensions:
            raise HTTPException(
                status_code=400,
                detail="Only .txt, .md, and .csv files are supported.",
            )

        content = await file.read()
        if len(content) > self.max_file_size_bytes:
            raise HTTPException(
                status_code=413,
                detail="Uploaded file is too large. Maximum size is 2MB.",
            )

        try:
            return self._clean_text(content.decode("utf-8"))
        except UnicodeDecodeError as error:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file must be valid UTF-8 text.",
            ) from error

    def _clean_text(self, text: str) -> str:
        return text.replace("\r\n", "\n").replace("\r", "\n").strip()
