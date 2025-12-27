
"""
PDF Processing Operations
"""

import os
from PyPDF2 import PdfMerger
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from io import BytesIO


class PDFProcessor:
    """Handle PDF operations"""
    
    def __init__(self):
        self.default_page_size = A4
    
    def merge_pdfs(self, input_paths, output_path):
        """
        Merge multiple PDFs into one
        """
        if len(input_paths) < 2:
            raise ValueError("Need at least 2 PDFs to merge")
        
        merger = PdfMerger()
        
        try:
            for pdf_path in input_paths:
                if os.path.exists(pdf_path):
                    merger.append(pdf_path)
            
            merger.write(output_path)
            
        except Exception as e:
            raise Exception(f"Merge failed: {str(e)}")
        
        finally:
            merger.close()
    
    def add_watermark(self, input_path, output_path, text, position='center', opacity=0.3):
        """
        Add text watermark to PDF
        """
        from PyPDF2 import PdfReader, PdfWriter
        
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"File not found: {input_path}")
        
        # Create watermark PDF
        packet = BytesIO()
        
        # Create canvas
        can = canvas.Canvas(packet, pagesize=self.default_page_size)
        can.setFillAlpha(opacity)
        
        # Set font
        font_size = 36
        if len(text) > 30:
            font_size = 24
        elif len(text) > 50:
            font_size = 18
        
        can.setFont("Helvetica-Bold", font_size)
        can.setFillColorRGB(0.5, 0.5, 0.5)  # Gray color
        
        # Get page dimensions
        page_width, page_height = self.default_page_size
        
        # Position the text
        if position == 'center':
            x = page_width / 2
            y = page_height / 2
            can.drawCentredString(x, y, text)
        elif position == 'top':
            x = page_width / 2
            y = page_height - 100
            can.drawCentredString(x, y, text)
        elif position == 'bottom':
            x = page_width / 2
            y = 100
            can.drawCentredString(x, y, text)
        elif position == 'diagonal':
            can.saveState()
            can.translate(page_width / 2, page_height / 2)
            can.rotate(45)
            can.drawCentredString(0, 0, text)
            can.restoreState()
        else:
            x = page_width / 2
            y = page_height / 2
            can.drawCentredString(x, y, text)
        
        can.save()
        
        # Move to beginning of BytesIO buffer
        packet.seek(0)
        
        # Create watermark PDF
        watermark_pdf = PdfReader(packet)
        
        # Open source PDF
        with open(input_path, 'rb') as file:
            reader = PdfReader(file)
            writer = PdfWriter()
            
            # Apply watermark to each page
            for page in reader.pages:
                page.merge_page(watermark_pdf.pages[0])
                writer.add_page(page)
            
            # Write output
            with open(output_path, 'wb') as output_file:
                writer.write(output_file)
