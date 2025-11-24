"""
File parser tool for extracting text from various file formats.
"""
import io
import logging
from typing import Dict, Any
from PyPDF2 import PdfReader
from src.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)


class FileParserTool(BaseTool):
    """
    Tool for parsing files and extracting text content.
    
    Supported formats:
    - PDF
    - TXT
    - JSON (passthrough)
    """
    
    def __init__(self):
        super().__init__(
            name="FileParserTool",
            description="Extracts text content from uploaded files"
        )
    
    async def run_async(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse file and extract text.
        
        Args:
            input_data: {
                "file_content": bytes,
                "file_name": str,
                "content_type": str
            }
        
        Returns:
            {
                "text": str,
                "file_name": str,
                "file_type": str,
                "success": bool,
                "error": str (if failed)
            }
        """
        file_content = input_data.get("file_content")
        file_name = input_data.get("file_name", "unknown")
        content_type = input_data.get("content_type", "")
        
        try:
            # PDF parsing
            if file_name.lower().endswith(".pdf") or "pdf" in content_type.lower():
                text = self._parse_pdf(file_content)
                return {
                    "text": text,
                    "file_name": file_name,
                    "file_type": "pdf",
                    "success": True
                }
            
            # Text file parsing
            elif file_name.lower().endswith(".txt") or "text" in content_type.lower():
                text = file_content.decode("utf-8")
                return {
                    "text": text,
                    "file_name": file_name,
                    "file_type": "txt",
                    "success": True
                }
            
            # JSON passthrough
            elif file_name.lower().endswith(".json") or "json" in content_type.lower():
                text = file_content.decode("utf-8")
                return {
                    "text": text,
                    "file_name": file_name,
                    "file_type": "json",
                    "success": True
                }
            
            else:
                return {
                    "text": "",
                    "file_name": file_name,
                    "file_type": "unknown",
                    "success": False,
                    "error": f"Unsupported file type: {file_name}"
                }
        
        except Exception as e:
            logger.error(f"File parsing error for {file_name}: {e}")
            return {
                "text": "",
                "file_name": file_name,
                "file_type": "error",
                "success": False,
                "error": str(e)
            }
    
    def _parse_pdf(self, file_content: bytes) -> str:
        """Extract text from PDF bytes."""
        pdf_stream = io.BytesIO(file_content)
        reader = PdfReader(pdf_stream)
        
        text_parts = []
        for page in reader.pages:
            try:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            except Exception as e:
                logger.warning(f"Failed to extract text from PDF page: {e}")
                continue
        
        return "\n".join(text_parts)
