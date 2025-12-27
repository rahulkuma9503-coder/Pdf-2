"""
Temporary file management and cleanup
"""

import os
import tempfile
import shutil
import threading
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class TempFileManager:
    """Manage temporary files with automatic cleanup"""
    
    def __init__(self, cleanup_interval: int = 3600):  # 1 hour default
        """
        Initialize temporary file manager
        
        Args:
            cleanup_interval: Seconds between cleanup runs
        """
        # Create temp directory
        self.temp_dir = tempfile.mkdtemp(prefix='pdf_bot_')
        self.cleanup_interval = cleanup_interval
        self.cleanup_thread = None
        self.stop_cleanup = threading.Event()
        
        logger.info(f"Temp directory created: {self.temp_dir}")
        
        # Start cleanup thread
        self.start_cleanup_thread()
    
    def create_temp_file(self, suffix: str = '.pdf', prefix: str = 'temp_') -> str:
        """
        Create a temporary file
        
        Args:
            suffix: File suffix/extension
            prefix: File prefix
            
        Returns:
            Path to created file
        """
        temp_file = tempfile.NamedTemporaryFile(
            dir=self.temp_dir,
            suffix=suffix,
            prefix=prefix,
            delete=False
        )
        temp_file.close()
        
        logger.debug(f"Created temp file: {temp_file.name}")
        return temp_file.name
    
    def create_temp_dir(self, prefix: str = 'temp_dir_') -> str:
        """
        Create a temporary directory
        
        Args:
            prefix: Directory prefix
            
        Returns:
            Path to created directory
        """
        return tempfile.mkdtemp(dir=self.temp_dir, prefix=prefix)
    
    def cleanup_old_files(self, max_age_minutes: int = 60):
        """
        Clean up files older than max_age_minutes
        
        Args:
            max_age_minutes: Maximum age in minutes
        """
        try:
            cutoff_time = datetime.now() - timedelta(minutes=max_age_minutes)
            deleted_count = 0
            
            for root, dirs, files in os.walk(self.temp_dir, topdown=False):
                # Delete old files
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                        
                        if file_time < cutoff_time:
                            os.unlink(file_path)
                            deleted_count += 1
                            logger.debug(f"Deleted old file: {file_path}")
                    
                    except (OSError, FileNotFoundError) as e:
                        logger.debug(f"Could not delete file {file_path}: {e}")
                
                # Delete empty directories (except root)
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    try:
                        if not os.listdir(dir_path):
                            os.rmdir(dir_path)
                            logger.debug(f"Removed empty directory: {dir_path}")
                    except (OSError, FileNotFoundError) as e:
                        logger.debug(f"Could not remove directory {dir_path}: {e}")
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old temporary files")
        
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def cleanup_all(self):
        """Clean up all temporary files"""
        try:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up all temp files in: {self.temp_dir}")
                
                # Recreate directory
                os.makedirs(self.temp_dir, exist_ok=True)
        
        except Exception as e:
            logger.error(f"Error cleaning up all files: {e}")
    
    def start_cleanup_thread(self):
        """Start background cleanup thread"""
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            return
        
        def cleanup_worker():
            logger.info("Cleanup thread started")
            
            while not self.stop_cleanup.is_set():
                try:
                    self.cleanup_old_files(max_age_minutes=30)
                except Exception as e:
                    logger.error(f"Cleanup worker error: {e}")
                
                # Wait for next cleanup cycle
                self.stop_cleanup.wait(self.cleanup_interval)
        
        self.cleanup_thread = threading.Thread(
            target=cleanup_worker,
            daemon=True,
            name="TempFileCleanup"
        )
        self.cleanup_thread.start()
    
    def stop_cleanup_thread(self):
        """Stop background cleanup thread"""
        self.stop_cleanup.set()
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=5)
            logger.info("Cleanup thread stopped")
    
    def get_disk_usage(self) -> dict:
        """
        Get disk usage statistics
        
        Returns:
            Dictionary with disk usage info
        """
        try:
            total_size = 0
            file_count = 0
            
            for dirpath, dirnames, filenames in os.walk(self.temp_dir):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        total_size += os.path.getsize(fp)
                        file_count += 1
                    except OSError:
                        pass
            
            return {
                'temp_dir': self.temp_dir,
                'total_size_bytes': total_size,
                'total_size_mb': total_size / (1024 * 1024),
                'file_count': file_count,
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error getting disk usage: {e}")
            return {'error': str(e)}
    
    def register_file_for_cleanup(self, file_path: str, delay_seconds: int = 300):
        """
        Schedule a file for delayed cleanup
        
        Args:
            file_path: Path to file
            delay_seconds: Delay before cleanup
        """
        def delayed_cleanup():
            time.sleep(delay_seconds)
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
                    logger.debug(f"Delayed cleanup of: {file_path}")
            except Exception as e:
                logger.debug(f"Could not cleanup {file_path}: {e}")
        
        thread = threading.Thread(
            target=delayed_cleanup,
            daemon=True,
            name=f"DelayedCleanup_{os.path.basename(file_path)}"
        )
        thread.start()
    
    def __del__(self):
        """Cleanup on destruction"""
        self.stop_cleanup_thread()
        try:
            self.cleanup_all()
        except:
            pass


class FileSizeLimiter:
    """Enforce file size limits"""
    
    def __init__(self, max_total_size_mb: int = 100, max_files: int = 1000):
        """
        Initialize file size limiter
        
        Args:
            max_total_size_mb: Maximum total size in MB
            max_files: Maximum number of files
        """
        self.max_total_size_bytes = max_total_size_mb * 1024 * 1024
        self.max_files = max_files
    
    def check_limits(self, temp_manager: TempFileManager) -> dict:
        """
        Check if storage limits are exceeded
        
        Args:
            temp_manager: TempFileManager instance
            
        Returns:
            Dictionary with limit status
        """
        usage = temp_manager.get_disk_usage()
        
        if 'error' in usage:
            return {
                'within_limits': False,
                'error': usage['error']
            }
        
        total_size = usage['total_size_bytes']
        file_count = usage['file_count']
        
        size_exceeded = total_size > self.max_total_size_bytes
        count_exceeded = file_count > self.max_files
        
        return {
            'within_limits': not (size_exceeded or count_exceeded),
            'total_size_bytes': total_size,
            'total_size_mb': total_size / (1024 * 1024),
            'max_size_mb': self.max_total_size_bytes / (1024 * 1024),
            'file_count': file_count,
            'max_files': self.max_files,
            'size_exceeded': size_exceeded,
            'count_exceeded': count_exceeded
        }
    
    def enforce_limits(self, temp_manager: TempFileManager):
        """
        Enforce limits by cleaning up oldest files
        
        Args:
            temp_manager: TempFileManager instance
        """
        status = self.check_limits(temp_manager)
        
        if status['within_limits']:
            return
        
        logger.warning(f"Storage limits exceeded. Enforcing cleanup.")
        
        try:
            # Get all files with modification times
            files = []
            for root, _, filenames in os.walk(temp_manager.temp_dir):
                for filename in filenames:
                    file_path = os.path.join(root, filename)
                    try:
                        mtime = os.path.getmtime(file_path)
                        files.append((file_path, mtime))
                    except OSError:
                        pass
            
            # Sort by modification time (oldest first)
            files.sort(key=lambda x: x[1])
            
            # Delete oldest files until within limits
            deleted_count = 0
            for file_path, _ in files:
                if status['within_limits']:
                    break
                
                try:
                    os.unlink(file_path)
                    deleted_count += 1
                    
                    # Update status
                    status = self.check_limits(temp_manager)
                
                except OSError as e:
                    logger.debug(f"Could not delete file {file_path}: {e}")
            
            if deleted_count > 0:
                logger.info(f"Enforced limits: deleted {deleted_count} files")
        
        except Exception as e:
            logger.error(f"Error enforcing limits: {e}")
