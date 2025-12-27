"""
Temporary file management
"""

import os
import tempfile
import threading
import time
from datetime import datetime, timedelta


class TempFileManager:
    """Manage temporary files"""
    
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp(prefix='pdf_bot_')
        print(f"Temp directory: {self.temp_dir}")
    
    def cleanup_old_files(self, max_age_minutes=30):
        """
        Clean up old files
        """
        try:
            cutoff_time = datetime.now() - timedelta(minutes=max_age_minutes)
            
            for filename in os.listdir(self.temp_dir):
                file_path = os.path.join(self.temp_dir, filename)
                try:
                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if file_time < cutoff_time:
                        os.unlink(file_path)
                except:
                    pass
        except Exception as e:
            print(f"Cleanup error: {e}")
