"""
Log Ingestion Module
Handles real-time log ingestion from access logs using file tailing
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import AsyncGenerator, Dict, Any
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import aiofiles
import time
from datetime import datetime

class LogTailHandler(FileSystemEventHandler):
    """File system event handler for log tailing"""
    
    def __init__(self, callback):
        self.callback = callback
        
    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.log'):
            asyncio.create_task(self.callback(event.src_path))

class LogIngestion:
    """Real-time log ingestion service"""
    
    def __init__(self, log_paths: list, queue_size: int = 1000):
        self.log_paths = [Path(path) for path in log_paths]
        self.queue = asyncio.Queue(maxsize=queue_size)
        self.file_positions = {}
        self.observers = []
        self.logger = logging.getLogger(__name__)
        
    async def start_ingestion(self):
        """Start log ingestion from all configured paths"""
        # Initialize file positions
        for log_path in self.log_paths:
            if log_path.exists():
                self.file_positions[str(log_path)] = log_path.stat().st_size
            else:
                self.file_positions[str(log_path)] = 0
                
        # Setup file watchers
        for log_path in self.log_paths:
            observer = Observer()
            handler = LogTailHandler(self._process_log_update)
            observer.schedule(handler, str(log_path.parent), recursive=False)
            observer.start()
            self.observers.append(observer)
            
        # Start background task to process existing logs
        asyncio.create_task(self._process_existing_logs())
        
    async def _process_existing_logs(self):
        """Process any existing log entries"""
        for log_path in self.log_paths:
            if log_path.exists():
                await self._read_new_lines(str(log_path))
                
    async def _process_log_update(self, file_path: str):
        """Process updates to log files"""
        await self._read_new_lines(file_path)
        
    async def _read_new_lines(self, file_path: str):
        """Read new lines from a log file"""
        try:
            current_pos = self.file_positions.get(file_path, 0)
            
            async with aiofiles.open(file_path, 'r') as f:
                await f.seek(current_pos)
                
                async for line in f:
                    line = line.strip()
                    if line:
                        log_entry = {
                            'raw_log': line,
                            'source_file': file_path,
                            'timestamp': datetime.utcnow().isoformat(),
                            'ingestion_time': time.time()
                        }
                        
                        try:
                            await self.queue.put(log_entry)
                        except asyncio.QueueFull:
                            self.logger.warning("Queue full, dropping log entry")
                            
                self.file_positions[file_path] = await f.tell()
                
        except Exception as e:
            self.logger.error(f"Error reading log file {file_path}: {e}")
            
    async def get_log_stream(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Get stream of log entries"""
        while True:
            try:
                log_entry = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                yield log_entry
                self.queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Error in log stream: {e}")
                continue
                
    def stop_ingestion(self):
        """Stop log ingestion"""
        for observer in self.observers:
            observer.stop()
            observer.join()
            
    async def get_queue_size(self) -> int:
        """Get current queue size"""
        return self.queue.qsize()

# Configuration
current_dir = Path(__file__).resolve().parent
project_root = (current_dir / '../../..').resolve()  # points to waf-system's parent directory, which is the repository root
waf_root = project_root / 'waf-system'

DEFAULT_LOG_PATHS = [
    str(waf_root / 'data' / 'logs' / 'access.log'),
    str(waf_root / 'tomcat' / 'current' / 'logs' / 'localhost_access_log.txt')
]

if __name__ == "__main__":
    async def test_ingestion():
        ingestion = LogIngestion(DEFAULT_LOG_PATHS)
        await ingestion.start_ingestion()
        
        async for log_entry in ingestion.get_log_stream():
            print(f"Received: {log_entry}")
            
    asyncio.run(test_ingestion())
