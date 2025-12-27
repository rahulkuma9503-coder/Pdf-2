"""
PDF Processing Functions
"""

from PyPDF2 import PdfMerger, PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from io import BytesIO


class PDFProcessor:
    """Simple PDF processor"""
    
    def merge_pdfs(self, input_paths, output_path):
        """Merge multiple PDFs"""
        merger = PdfMerger()
        for pdf in input_paths:
            merger.append(pdf)
        merger.write(output_path)
        merger.close()
    
    def add_watermark(self, input_path, output_path, text, position='center', opacity=0.3):
        """Add watermark to PDF"""
        # Create watermark
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=A4)
        can.setFillAlpha(opacity)
        can.setFont("Helvetica-Bold", 36)
        can.setFillColorRGB(0.5, 0.5, 0.5)
        
        # Position
        if position == 'center':
            can.drawCentredString(300, 400, text)
        elif position == 'top':
            can.drawCentredString(300, 700, text)
        elif position == 'bottom':
            can.drawCentredString(300, 100, text)
        elif position == 'diagonal':
            can.rotate(45)
            can.drawCentredString(300, 300, text)
        
        can.save()
        packet.seek(0)
        
        # Apply watermark
        reader = PdfReader(input_path)
        writer = PdfWriter()
        
        for page in reader.pages:
            page.merge_page(PdfReader(packet).pages[0])
            writer.add_page(page)
        
        with open(output_path, 'wb') as output_file:
            writer.write(output_file)
