"""
Input validation utilities
"""

import os


class FileValidator:
    """Validate uploaded files"""
    
    def __init__(self, max_size=20 * 1024 * 1024):
        self.max_size = max_size
    
    def is_pdf_file(self, filename):
        """
        Check if file is a PDF
        """
        if not filename:
            return False
        
        return filename.lower().endswith('.pdf')
    
    def is_valid_size(self, file_size):
        """
        Check if file size is within limits
        """
        return file_size <= self.max_size
