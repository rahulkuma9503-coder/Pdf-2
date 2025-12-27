"""
Input validation utilities
"""

import os
import re
from typing import Optional


class FileValidator:
    """Validate uploaded files"""
    
    def __init__(self, max_size: int = 20 * 1024 * 1024):  # 20MB default
        self.max_size = max_size
    
    def is_pdf_file(self, filename: str) -> bool:
        """
        Check if file is a PDF
        
        Args:
            filename: Name of the file
            
        Returns:
            True if PDF, False otherwise
        """
        if not filename:
            return False
        
        # Check extension
        ext = os.path.splitext(filename)[1].lower()
        if ext != '.pdf':
            return False
        
        # Additional check for MIME type patterns
        pdf_patterns = [
            r'\.pdf$',
            r'application/pdf',
            r'pdf'
        ]
        
        filename_lower = filename.lower()
        return any(pattern in filename_lower for pattern in pdf_patterns)
    
    def is_valid_size(self, file_size: int) -> bool:
        """
        Check if file size is within limits
        
        Args:
            file_size: Size in bytes
            
        Returns:
            True if within limit, False otherwise
        """
        return file_size <= self.max_size
    
    def is_safe_filename(self, filename: str) -> bool:
        """
        Check if filename is safe (no path traversal attempts)
        
        Args:
            filename: Name of the file
            
        Returns:
            True if safe, False otherwise
        """
        if not filename:
            return False
        
        # Check for path traversal attempts
        unsafe_patterns = [
            '..',
            '/',
            '\\',
            ':',
            ';',
            '|',
            '*',
            '?',
            '"',
            '<',
            '>'
        ]
        
        return not any(pattern in filename for pattern in unsafe_patterns)
    
    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename by removing unsafe characters
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        if not filename:
            return "document.pdf"
        
        # Remove directory path
        basename = os.path.basename(filename)
        
        # Remove unsafe characters
        safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
        sanitized = ''.join(c for c in basename if c in safe_chars)
        
        # Ensure it ends with .pdf
        if not sanitized.lower().endswith('.pdf'):
            sanitized += '.pdf'
        
        # Default name if empty
        if not sanitized or sanitized == '.pdf':
            sanitized = 'document.pdf'
        
        return sanitized
    
    def validate_pdf_structure(self, file_path: str) -> bool:
        """
        Basic validation of PDF structure
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            True if valid PDF structure, False otherwise
        """
        try:
            with open(file_path, 'rb') as f:
                # Check PDF header
                header = f.read(5)
                return header == b'%PDF-'
        except:
            return False


class TextValidator:
    """Validate text inputs"""
    
    @staticmethod
    def is_valid_watermark_text(text: str, max_length: int = 100) -> bool:
        """
        Validate watermark text
        
        Args:
            text: Watermark text
            max_length: Maximum allowed length
            
        Returns:
            True if valid, False otherwise
        """
        if not text or not text.strip():
            return False
        
        # Check length
        if len(text.strip()) > max_length:
            return False
        
        # Check for dangerous characters
        dangerous_patterns = [
            '<script',
            'javascript:',
            'onload=',
            'onerror=',
            'eval(',
            'alert(',
            'document.cookie'
        ]
        
        text_lower = text.lower()
        return not any(pattern in text_lower for pattern in dangerous_patterns)
    
    @staticmethod
    def is_valid_filename(filename: str, max_length: int = 100) -> bool:
        """
        Validate filename
        
        Args:
            filename: Proposed filename
            max_length: Maximum allowed length
            
        Returns:
            True if valid, False otherwise
        """
        if not filename or not filename.strip():
            return False
        
        if len(filename) > max_length:
            return False
        
        # Remove extension for validation
        name_without_ext = os.path.splitext(filename)[0]
        
        # Check for invalid characters
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        return not any(char in name_without_ext for char in invalid_chars)
    
    @staticmethod
    def is_valid_opacity(value: str) -> Optional[float]:
        """
        Validate opacity value
        
        Args:
            value: Opacity as string
            
        Returns:
            Float value if valid, None otherwise
        """
        try:
            opacity = float(value)
            if 0.1 <= opacity <= 1.0:
                return opacity
            return None
        except ValueError:
            return None


class InputSanitizer:
    """Sanitize user inputs"""
    
    @staticmethod
    def sanitize_text(text: str) -> str:
        """
        Sanitize user text input
        
        Args:
            text: Raw text input
            
        Returns:
            Sanitized text
        """
        if not text:
            return ""
        
        # Remove excessive whitespace
        text = ' '.join(text.split())
        
        # Escape HTML special characters
        html_escape_table = {
            "&": "&amp;",
            '"': "&quot;",
            "'": "&apos;",
            ">": "&gt;",
            "<": "&lt;",
        }
        
        for char, escape in html_escape_table.items():
            text = text.replace(char, escape)
        
        return text.strip()
    
    @staticmethod
    def sanitize_watermark_text(text: str) -> str:
        """
        Special sanitization for watermark text
        
        Args:
            text: Watermark text
            
        Returns:
            Sanitized watermark text
        """
        sanitized = InputSanitizer.sanitize_text(text)
        
        # Limit length for watermark
        if len(sanitized) > 50:
            sanitized = sanitized[:47] + "..."
        
        return sanitized
