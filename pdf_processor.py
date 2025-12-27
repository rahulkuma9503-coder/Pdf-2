"""
PDF Processing Operations
"""

import os
from PyPDF2 import PdfReader, PdfWriter, PdfMerger
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.utils import ImageReader
from io import BytesIO
import math


class PDFProcessor:
    """Handle all PDF operations"""
    
    def __init__(self):
        self.default_page_size = A4
    
    def merge_pdfs(self, input_paths, output_path):
        """
        Merge multiple PDFs into one
        
        Args:
            input_paths: List of PDF file paths
            output_path: Output file path
        """
        if len(input_paths) < 2:
            raise ValueError("Need at least 2 PDFs to merge")
        
        merger = PdfMerger()
        
        try:
            for pdf_path in input_paths:
                if not os.path.exists(pdf_path):
                    raise FileNotFoundError(f"File not found: {pdf_path}")
                
                merger.append(pdf_path)
            
            merger.write(output_path)
            
        except Exception as e:
            raise Exception(f"Merge failed: {str(e)}")
        
        finally:
            merger.close()
    
    def rename_pdf(self, input_path, output_path):
        """
        Rename PDF (essentially copy with new name)
        
        Args:
            input_path: Source PDF path
            output_path: Destination PDF path
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        try:
            with open(input_path, 'rb') as infile:
                reader = PdfReader(infile)
                writer = PdfWriter()
                
                for page in reader.pages:
                    writer.add_page(page)
                
                with open(output_path, 'wb') as outfile:
                    writer.write(outfile)
        
        except Exception as e:
            raise Exception(f"Rename failed: {str(e)}")
    
    def add_watermark(self, input_path, output_path, text, position='center', opacity=0.5):
        """
        Add text watermark to PDF
        
        Args:
            input_path: Source PDF path
            output_path: Output PDF path
            text: Watermark text
            position: 'center', 'top', 'bottom', 'diagonal', 'corners'
            opacity: Transparency (0.0 to 1.0)
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Create watermark PDF
        watermark_pdf = self._create_watermark_pdf(text, position, opacity)
        
        try:
            # Open source PDF
            with open(input_path, 'rb') as file:
                reader = PdfReader(file)
                writer = PdfWriter()
                
                # Apply watermark to each page
                for page_num, page in enumerate(reader.pages):
                    # Merge watermark with page
                    page.merge_page(watermark_pdf.pages[0])
                    writer.add_page(page)
                
                # Write output
                with open(output_path, 'wb') as output_file:
                    writer.write(output_file)
        
        except Exception as e:
            raise Exception(f"Watermark failed: {str(e)}")
    
    def _create_watermark_pdf(self, text, position, opacity):
        """
        Create a single-page PDF with watermark
        
        Returns:
            PdfReader object with watermark
        """
        # Create in-memory PDF
        packet = BytesIO()
        
        # Create canvas with A4 size
        can = canvas.Canvas(packet, pagesize=self.default_page_size)
        can.setFillAlpha(opacity)  # Set transparency
        
        # Set font (adjust size based on text length)
        text_length = len(text)
        if text_length <= 10:
            font_size = 48
        elif text_length <= 20:
            font_size = 36
        elif text_length <= 30:
            font_size = 24
        else:
            font_size = 18
        
        can.setFont("Helvetica-Bold", font_size)
        can.setFillColorRGB(0.5, 0.5, 0.5)  # Gray color
        
        # Get page dimensions
        page_width, page_height = self.default_page_size
        
        if position == 'center':
            # Single centered watermark
            self._draw_text_centered(can, text, page_width/2, page_height/2)
        
        elif position == 'top':
            # Top center
            self._draw_text_centered(can, text, page_width/2, page_height - 100)
        
        elif position == 'bottom':
            # Bottom center
            self._draw_text_centered(can, text, page_width/2, 100)
        
        elif position == 'diagonal':
            # Diagonal across page
            self._draw_diagonal_watermarks(can, text, page_width, page_height)
        
        elif position == 'corners':
            # Watermark in all four corners
            self._draw_corner_watermarks(can, text, page_width, page_height, font_size)
        
        else:
            # Default to center
            self._draw_text_centered(can, text, page_width/2, page_height/2)
        
        can.save()
        
        # Move to beginning of BytesIO buffer
        packet.seek(0)
        
        # Create PDF from buffer
        watermark_pdf = PdfReader(packet)
        
        return watermark_pdf
    
    def _draw_text_centered(self, canvas_obj, text, x, y, rotation=0):
        """Draw centered text with optional rotation"""
        if rotation:
            canvas_obj.rotate(rotation)
        canvas_obj.drawCentredString(x, y, text)
        if rotation:
            canvas_obj.rotate(-rotation)
    
    def _draw_diagonal_watermarks(self, canvas_obj, text, page_width, page_height):
        """Draw watermarks diagonally across page"""
        # Multiple diagonal watermarks
        spacing = 150
        font_size = 36
        canvas_obj.setFont("Helvetica-Bold", font_size)
        
        # Draw at 45 degree angle
        canvas_obj.rotate(45)
        
        # Calculate starting position
        num_watermarks = int(math.sqrt(page_width**2 + page_height**2) / spacing) + 2
        
        for i in range(-num_watermarks, num_watermarks + 1):
            x = i * spacing
            for j in range(-num_watermarks, num_watermarks + 1):
                y = j * spacing
                canvas_obj.drawCentredString(x, y, text)
        
        canvas_obj.rotate(-45)
    
    def _draw_corner_watermarks(self, canvas_obj, text, page_width, page_height, font_size):
        """Draw watermarks in all four corners"""
        margin = 100
        small_font = max(12, font_size - 12)
        canvas_obj.setFont("Helvetica", small_font)
        
        # Top-left
        canvas_obj.drawString(margin, page_height - margin - 20, text)
        # Top-right
        canvas_obj.drawRightString(page_width - margin, page_height - margin - 20, text)
        # Bottom-left
        canvas_obj.drawString(margin, margin, text)
        # Bottom-right
        canvas_obj.drawRightString(page_width - margin, margin, text)
        
        # Center watermark (larger)
        canvas_obj.setFont("Helvetica-Bold", font_size)
        self._draw_text_centered(canvas_obj, text, page_width/2, page_height/2)
    
    def validate_pdf(self, file_path):
        """Validate if file is a valid PDF"""
        try:
            with open(file_path, 'rb') as file:
                reader = PdfReader(file)
                return len(reader.pages) > 0
        except:
            return False
