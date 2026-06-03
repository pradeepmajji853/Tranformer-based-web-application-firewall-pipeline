"""
WAF Inference Service
FastAPI-based service for real-time anomaly detection on HTTP requests
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import glob

import torch
import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import redis
from torch.utils.data import DataLoader

import os
import sys

# Establish important paths
current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, '../..'))  # points to waf-system

# Try absolute package imports first; fall back to path-based imports if needed
try:
    from ml_pipeline.preprocessing.log_processor import LogPreprocessor
    from ml_pipeline.training.waf_model import WAFTransformer, WAFTokenizer, create_waf_model, WAFTransformerConfig
    from ml_pipeline.training.trainer import WAFTrainer, prepare_training_data, collate_fn
except Exception:
    # Fallback: insert paths for the hyphenated package directory
    sys.path.insert(0, os.path.join(project_root, 'ml-pipeline'))
    sys.path.insert(0, os.path.join(project_root, 'ml-pipeline', 'training'))
    sys.path.insert(0, os.path.join(project_root, 'ml-pipeline', 'preprocessing'))
    from log_processor import LogPreprocessor  # type: ignore
    from waf_model import WAFTransformer, WAFTokenizer, create_waf_model, WAFTransformerConfig  # type: ignore
    from trainer import WAFTrainer, prepare_training_data, collate_fn  # type: ignore

class RequestData(BaseModel):
    """Model for incoming HTTP request data"""
    method: str
    uri: str
    headers: Dict[str, str] = {}
    remote_addr: str
    user_agent: str = ""
    body: Optional[str] = None
    timestamp: Optional[str] = None

class AnomalyResponse(BaseModel):
    """Model for anomaly detection response"""
    request_id: str
    anomaly_score: float
    is_anomalous: bool
    confidence: float
    template_id: Optional[int] = None
    features: Dict[str, Any] = {}
    processing_time_ms: float

class BatchRequest(BaseModel):
    """Model for batch inference requests"""
    requests: List[RequestData]

class ModelUpdateRequest(BaseModel):
    """Model for incremental model updates"""
    log_entries: List[str]
    is_benign: bool = True

class TrainFromLogsRequest(BaseModel):
    """Request schema for training from log files"""
    log_paths: Optional[List[str]] = None
    epochs: int = 1
    max_lines: int = 5000
    batch_size: int = 32

class WAFInferenceService:
    """Main WAF inference service"""
    
    def __init__(
        self,
        model_path: str,
        threshold: float = 0.5,
        redis_url: str = "redis://localhost:6379/0",
        max_queue_size: int = 1000,
        batch_size: int = 32,
        batch_timeout: float = 0.01  # 10ms
    ):
        self.model_path = model_path
        self.threshold = threshold
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.max_queue_size = max_queue_size
        
        # Initialize components
        self.preprocessor = LogPreprocessor()
        self.model = None
        self.tokenizer = None
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
        # Request queue for batching
        self.request_queue = asyncio.Queue(maxsize=max_queue_size)
        self.response_futures = {}
        
        # Redis for caching and statistics
        try:
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.redis_available = True
        except:
            self.redis_client = None
            self.redis_available = False
            logging.warning("Redis not available, caching disabled")
            
        # Statistics
        self.stats = {
            'total_requests': 0,
            'anomalous_requests': 0,
            'avg_processing_time': 0.0,
            'last_model_update': None
        }
        
        # Logger
        self.logger = logging.getLogger(__name__)
        
        # Training job status
        self.training_status = {
            'running': False,
            'status': 'idle',
            'progress': 0.0,
            'epochs_total': 0,
            'current_epoch': 0,
            'result': None,
            'error': None,
            'started_at': None,
            'finished_at': None
        }
        
    async def initialize(self):
        """Initialize the service"""
        self.load_model()
        
        # Start background batch processor
        asyncio.create_task(self.batch_processor())
        
        self.logger.info("WAF Inference Service initialized")
        
    def load_model(self):
        """Load the trained model"""
        try:
            model_path = Path(self.model_path)
            if not model_path.exists():
                # Fallback to notebook_model.pt if present
                fallback = model_path.parent / 'notebook_model.pt'
                if fallback.exists():
                    self.logger.warning(f"Model not found at {model_path}, loading fallback {fallback}")
                    model_path = fallback
                else:
                    self.logger.warning(f"Model not found at {model_path}, creating new model")
                    m, t = create_waf_model()
                    self.model = m
                    self.tokenizer = t
                    return
                
            # Load model
            checkpoint = torch.load(str(model_path), map_location=self.device)
            model_config = checkpoint['model_config']
            
            config = WAFTransformerConfig(**model_config)
            
            model = WAFTransformer(config).to(self.device)
            model.load_state_dict(checkpoint['model_state_dict'])
            model.eval()
            
            # Load tokenizer
            tokenizer_path = str(model_path).replace('.pt', '_tokenizer.json')
            tokenizer = WAFTokenizer(vocab_size=config.vocab_size)
            if Path(tokenizer_path).exists():
                tokenizer.load_vocabulary(tokenizer_path)
            
            # Thread-safe assignment
            self.model = model
            self.tokenizer = tokenizer
            self.logger.info(f"Model loaded from {model_path}")
            
        except Exception as e:
            self.logger.error(f"Error loading model: {e}")
            # Fallback to new model
            m, t = create_waf_model()
            self.model = m
            self.tokenizer = t
            
    async def predict_single(self, request_data: RequestData) -> AnomalyResponse:
        """Predict anomaly for a single request"""
        start_time = time.time()
        request_id = f"req_{int(time.time() * 1000)}_{hash(str(request_data)) % 10000}"
        
        try:
            # Convert request to log format
            log_line = self._request_to_log_format(request_data)
            
            # Preprocess
            processed = self.preprocessor.process_log_entry(log_line)
            if not processed:
                raise ValueError("Failed to process request")
                
            # Create sequence tokens
            sequence = self._create_sequence_from_processed(processed)
            
            # Tokenize
            encoded = self.tokenizer.encode(sequence, max_length=128)
            
            # Inference
            raw_anomaly_score, _ = await self._run_inference(encoded)
            
            # Check for out-of-vocabulary [UNK] tokens (unseen templates/paths)
            input_ids = encoded['input_ids'].tolist()
            unk_id = self.tokenizer.special_tokens['[UNK]']
            has_unk = unk_id in input_ids
            
            # Extract features from preprocessor
            features = processed.get('features', {})
            contains_threat = (
                features.get('contains_script_tags', False) or
                features.get('contains_sql_keywords', False) or
                features.get('contains_xss_patterns', False) or
                features.get('suspicious_user_agent', False)
            )
            
            # Direct path traversal checks
            uri_lower = request_data.uri.lower()
            has_traversal = "../" in uri_lower or "etc/passwd" in uri_lower or "cmd.exe" in uri_lower or "whoami" in uri_lower
            
            # Calibrate anomaly score
            anomaly_score = raw_anomaly_score
            if has_unk:
                anomaly_score = max(anomaly_score, 0.65)
            if has_traversal:
                anomaly_score = max(anomaly_score, 0.85)
            if contains_threat:
                anomaly_score = max(anomaly_score, 0.95)
            if not has_unk and not contains_threat and not has_traversal:
                anomaly_score = min(anomaly_score, 0.25)
                
            is_anomalous = anomaly_score > self.threshold
            confidence = abs(anomaly_score - 0.5) * 2
            
            # Update statistics
            processing_time = (time.time() - start_time) * 1000
            self._update_stats(processing_time, is_anomalous)
            
            # Cache result if Redis available
            if self.redis_available:
                cache_key = f"waf:prediction:{hash(log_line)}"
                cache_data = {
                    'anomaly_score': anomaly_score,
                    'is_anomalous': is_anomalous,
                    'timestamp': datetime.utcnow().isoformat()
                }
                await self._redis_set(cache_key, json.dumps(cache_data), ex=300)  # 5 min cache
                
            response = AnomalyResponse(
                request_id=request_id,
                anomaly_score=float(anomaly_score),
                is_anomalous=is_anomalous,
                confidence=float(confidence),
                template_id=processed.get('template_id'),
                features=features,
                processing_time_ms=processing_time
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error in prediction: {e}")
            return AnomalyResponse(
                request_id=request_id,
                anomaly_score=0.0,
                is_anomalous=False,
                confidence=0.0,
                processing_time_ms=(time.time() - start_time) * 1000
            )
            
    async def predict_batch(self, requests: List[RequestData]) -> List[AnomalyResponse]:
        """Predict anomalies for a batch of requests"""
        if len(requests) == 1:
            return [await self.predict_single(requests[0])]
            
        start_time = time.time()
        responses = []
        
        try:
            # Process all requests
            processed_requests = []
            for req in requests:
                log_line = self._request_to_log_format(req)
                processed = self.preprocessor.process_log_entry(log_line)
                if processed:
                    sequence = self._create_sequence_from_processed(processed)
                    encoded = self.tokenizer.encode(sequence, max_length=128)
                    processed_requests.append((req, processed, encoded))
                else:
                    processed_requests.append((req, None, None))
                    
            # Batch inference
            if processed_requests:
                batch_inputs = []
                batch_masks = []
                valid_indices = []
                
                for i, (req, processed, encoded) in enumerate(processed_requests):
                    if encoded is not None:
                        batch_inputs.append(encoded['input_ids'])
                        batch_masks.append(encoded['attention_mask'])
                        valid_indices.append(i)
                        
                if batch_inputs:
                    # Stack tensors
                    input_ids = torch.stack(batch_inputs).to(self.device)
                    attention_mask = torch.stack(batch_masks).to(self.device)
                    
                    # Run batch inference
                    with torch.no_grad():
                        outputs = self.model(
                            input_ids=input_ids,
                            attention_mask=attention_mask
                        )
                        anomaly_scores = outputs['anomaly_score'].cpu().numpy()
                        
                    # Create responses
                    for i, (req, processed, encoded) in enumerate(processed_requests):
                        request_id = f"batch_{int(start_time)}_{i}"
                        
                        if i in valid_indices:
                            batch_idx = valid_indices.index(i)
                            raw_score = anomaly_scores[batch_idx]
                            
                            # Calibrate score
                            input_ids_list = encoded['input_ids'].tolist()
                            unk_id = self.tokenizer.special_tokens['[UNK]']
                            has_unk = unk_id in input_ids_list
                            
                            features = processed.get('features', {}) if processed else {}
                            contains_threat = (
                                features.get('contains_script_tags', False) or
                                features.get('contains_sql_keywords', False) or
                                features.get('contains_xss_patterns', False) or
                                features.get('suspicious_user_agent', False)
                            )
                            
                            uri_lower = req.uri.lower()
                            has_traversal = "../" in uri_lower or "etc/passwd" in uri_lower or "cmd.exe" in uri_lower or "whoami" in uri_lower
                            
                            anomaly_score = raw_score
                            if has_unk:
                                anomaly_score = max(anomaly_score, 0.65)
                            if has_traversal:
                                anomaly_score = max(anomaly_score, 0.85)
                            if contains_threat:
                                anomaly_score = max(anomaly_score, 0.95)
                            if not has_unk and not contains_threat and not has_traversal:
                                anomaly_score = min(anomaly_score, 0.25)
                                
                            confidence = abs(anomaly_score - 0.5) * 2
                            is_anomalous = anomaly_score > self.threshold
                            
                            response = AnomalyResponse(
                                request_id=request_id,
                                anomaly_score=float(anomaly_score),
                                is_anomalous=is_anomalous,
                                confidence=float(confidence),
                                template_id=processed.get('template_id') if processed else None,
                                features=features,
                                processing_time_ms=(time.time() - start_time) * 1000 / len(requests)
                            )
                        else:
                            # Failed to process
                            response = AnomalyResponse(
                                request_id=request_id,
                                anomaly_score=0.0,
                                is_anomalous=False,
                                confidence=0.0,
                                processing_time_ms=(time.time() - start_time) * 1000 / len(requests)
                            )
                            
                        responses.append(response)
                        
            return responses
            
        except Exception as e:
            self.logger.error(f"Error in batch prediction: {e}")
            # Return default responses
            return [
                AnomalyResponse(
                    request_id=f"batch_error_{i}",
                    anomaly_score=0.0,
                    is_anomalous=False,
                    confidence=0.0,
                    processing_time_ms=(time.time() - start_time) * 1000 / len(requests)
                )
                for i in range(len(requests))
            ]
            
    async def _run_inference(self, encoded: Dict[str, torch.Tensor]) -> tuple:
        """Run inference on encoded input"""
        with torch.no_grad():
            input_ids = encoded['input_ids'].unsqueeze(0).to(self.device)
            attention_mask = encoded['attention_mask'].unsqueeze(0).to(self.device)
            
            outputs = self.model(
                input_ids=input_ids,
                attention_mask=attention_mask
            )
            
            anomaly_score = outputs['anomaly_score'].item()
            confidence = abs(anomaly_score - 0.5) * 2  # Distance from decision boundary
            
            return anomaly_score, confidence
            
    async def batch_processor(self):
        """Background task to process requests in batches"""
        while True:
            try:
                batch_requests = []
                futures = []
                
                # Collect requests for batching
                deadline = time.time() + self.batch_timeout
                
                while len(batch_requests) < self.batch_size and time.time() < deadline:
                    try:
                        request_data, future = await asyncio.wait_for(
                            self.request_queue.get(),
                            timeout=max(0, deadline - time.time())
                        )
                        batch_requests.append(request_data)
                        futures.append(future)
                    except asyncio.TimeoutError:
                        break
                        
                if batch_requests:
                    # Process batch
                    responses = await self.predict_batch(batch_requests)
                    
                    # Return results to futures
                    for future, response in zip(futures, responses):
                        if not future.done():
                            future.set_result(response)
                            
                # Small delay to prevent busy waiting
                await asyncio.sleep(0.001)
                
            except Exception as e:
                self.logger.error(f"Error in batch processor: {e}")
                await asyncio.sleep(0.1)
                
    def _request_to_log_format(self, request_data: RequestData) -> str:
        """Convert request data to log format"""
        timestamp = request_data.timestamp or datetime.utcnow().strftime('%d/%b/%Y:%H:%M:%S +0000')
        status = 200  # Assume OK since we're processing the request
        
        log_line = (
            f'{request_data.remote_addr} - - [{timestamp}] '
            f'"{request_data.method} {request_data.uri} HTTP/1.1" {status} 0 '
            f'"-" "{request_data.user_agent}"'
        )
        
        return log_line
        
    def _create_sequence_from_processed(self, processed: Dict[str, Any]) -> List[str]:
        """Create token sequence from processed log entry"""
        parsed = processed['parsed']
        
        sequence = [
            parsed.get('method', 'GET'),
            parsed.get('path_only', '/'),
            str(parsed.get('status', 200)),
        ]
        
        # Add user agent tokens (simplified)
        user_agent = parsed.get('http_user_agent', '')
        if user_agent and user_agent != '-':
            # Extract browser/tool name
            if 'Mozilla' in user_agent:
                sequence.append('Mozilla')
            elif 'curl' in user_agent:
                sequence.append('curl')
            elif 'python' in user_agent:
                sequence.append('python')
            else:
                sequence.append('Other-Agent')
                
        return sequence
        
    def _update_stats(self, processing_time: float, is_anomalous: bool):
        """Update service statistics"""
        self.stats['total_requests'] += 1
        if is_anomalous:
            self.stats['anomalous_requests'] += 1
            
        # Update average processing time (running average)
        total = self.stats['total_requests']
        current_avg = self.stats['avg_processing_time']
        self.stats['avg_processing_time'] = ((current_avg * (total - 1)) + processing_time) / total
        
    async def _redis_set(self, key: str, value: str, ex: int = None):
        """Set value in Redis with error handling"""
        if self.redis_available:
            try:
                self.redis_client.set(key, value, ex=ex)
            except:
                pass
                
    async def get_stats(self) -> Dict[str, Any]:
        """Get service statistics"""
        stats = self.stats.copy()
        stats['anomaly_rate'] = (
            self.stats['anomalous_requests'] / max(1, self.stats['total_requests'])
        )
        stats['uptime'] = time.time() - getattr(self, 'start_time', time.time())
        
        return stats

    # Helper: build sequences from log files
    def _build_sequences_from_logs(self, log_paths: List[str], max_lines: int = 5000) -> List[List[str]]:
        sequences: List[List[str]] = []
        read_lines = 0
        for p in log_paths:
            try:
                # Expand globs robustly (supports absolute patterns)
                expanded = glob.glob(p) if any(ch in p for ch in ['*', '?', '[']) else [p]
                for path_str in sorted(expanded):
                    path = Path(path_str)
                    if not path.exists() or not path.is_file():
                        continue
                    with path.open('r', errors='ignore') as f:
                        for line in f:
                            if read_lines >= max_lines:
                                break
                            processed = self.preprocessor.process_log_entry(line.strip())
                            if processed:
                                seq = self._create_sequence_from_processed(processed)
                                sequences.append(seq)
                                read_lines += 1
                    if read_lines >= max_lines:
                        break
            except Exception as e:
                self.logger.warning(f"Failed reading logs from {p}: {e}")
            if read_lines >= max_lines:
                break
        self.logger.info(f"Collected {len(sequences)} sequences from logs")
        return sequences
    
    def _train_from_logs_sync(self, log_paths: List[str], epochs: int = 1, max_lines: int = 5000, batch_size: int = 32):
        if self.training_status['running']:
            self.logger.info("Training already in progress")
            return
        
        self.training_status.update({
            'running': True,
            'status': 'preparing',
            'progress': 0.0,
            'epochs_total': epochs,
            'current_epoch': 0,
            'result': None,
            'error': None,
            'started_at': datetime.utcnow().isoformat(),
            'finished_at': None
        })
        try:
            # Discover default logs if none provided
            if not log_paths:
                # project_root already points to waf-system directory
                default_paths = [
                    str(Path(project_root) / 'data' / 'logs' / 'access.log'),
                    str(Path(project_root) / 'tomcat' / 'current' / 'logs' / 'localhost_access_log*.txt')
                ]
                synth = Path(project_root) / 'data' / 'logs' / 'benign_synth.log'
                if synth.exists():
                    default_paths.insert(0, str(synth))
                log_paths = default_paths
            
            self.training_status['status'] = 'loading logs'
            sequences = self._build_sequences_from_logs(log_paths, max_lines=max_lines)
            if len(sequences) < 10:
                raise RuntimeError("Not enough log data to train (need at least 10 sequences)")
            
            # Prepare datasets
            self.training_status['status'] = 'preparing dataset'
            train_dataset, val_dataset = prepare_training_data(sequences, self.tokenizer)
            train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, collate_fn=collate_fn)
            val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, collate_fn=collate_fn)
            
            # Trainer
            trainer = WAFTrainer(self.model, self.tokenizer, device=self.device)
            
            # Train epochs
            for epoch in range(epochs):
                self.training_status['current_epoch'] = epoch + 1
                self.training_status['status'] = f'training epoch {epoch+1}/{epochs}'
                train_metrics = trainer.train_epoch(train_loader)
                val_metrics = trainer.evaluate(val_loader)
                self.training_status['progress'] = (epoch + 1) / max(1, epochs)
                self.training_status['result'] = {
                    'train': train_metrics,
                    'val': val_metrics
                }
            
            # Save and reload
            save_dir = Path(self.model_path).parent
            save_dir.mkdir(parents=True, exist_ok=True)
            trainer.save_model(self.model_path)
            self.stats['last_model_update'] = datetime.utcnow().isoformat()
            self.load_model()
            
            self.training_status['status'] = 'completed'
            self.training_status['finished_at'] = datetime.utcnow().isoformat()
            self.training_status['running'] = False
        except Exception as e:
            self.logger.exception("Training failed")
            self.training_status['status'] = 'error'
            self.training_status['error'] = str(e)
            self.training_status['running'] = False
            self.training_status['finished_at'] = datetime.utcnow().isoformat()

# Initialize service
waf_service = WAFInferenceService(
    model_path=str((Path(project_root) / 'data' / 'models' / 'best_model.pt').resolve())
)

# FastAPI app
app = FastAPI(
    title="WAF Anomaly Detection API",
    description="Transformer-based Web Application Firewall for anomaly detection",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    waf_service.start_time = time.time()
    await waf_service.initialize()

@app.get("/")
async def index():
    return {
        "service": "WAF Anomaly Detection API",
        "endpoints": [
            "/health", "/stats", "/score", "/score/batch", "/model/update",
            "/train_from_logs", "/train/status", "/model/reload"
        ]
    }

@app.post("/score", response_model=AnomalyResponse)
async def score_request(request_data: RequestData):
    """Score a single HTTP request for anomaly detection"""
    try:
        response = await waf_service.predict_single(request_data)
        return response
    except Exception as e:
        logging.error(f"Error scoring request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/validate")
async def validate_request(request: Request):
    """
    Validation endpoint for Nginx auth_request module.
    Extracts original request metadata from headers and returns 200 OK or 403 Forbidden.
    """
    method = request.headers.get("x-original-method", "GET")
    uri = request.headers.get("x-original-uri", "/")
    remote_addr = request.headers.get("x-original-ip", "127.0.0.1")
    user_agent = request.headers.get("x-original-ua", "")
    
    # Form RequestData object
    req_data = RequestData(
        method=method,
        uri=uri,
        remote_addr=remote_addr,
        user_agent=user_agent
    )
    
    try:
        response = await waf_service.predict_single(req_data)
        
        # Check if the WAF detects an anomaly
        if response.is_anomalous:
            logging.warning(
                f"[WAF BLOCK] Anomalous request blocked! Method: {method}, URI: {uri}, "
                f"IP: {remote_addr}, Score: {response.anomaly_score:.4f}"
            )
            raise HTTPException(status_code=403, detail="Request blocked by WAF")
            
        return {"status": "allowed"}
    except HTTPException as he:
        raise he
    except Exception as e:
        logging.error(f"Error validating request: {e}")
        # Default to allow in case of internal errors to prevent service failure (fail-open)
        return {"status": "allowed_fallback"}

@app.post("/score/batch", response_model=List[AnomalyResponse])
async def score_batch(batch_request: BatchRequest):
    """Score multiple HTTP requests for anomaly detection"""
    try:
        responses = await waf_service.predict_batch(batch_request.requests)
        return responses
    except Exception as e:
        logging.error(f"Error scoring batch: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats")
async def get_stats():
    """Get service statistics"""
    return await waf_service.get_stats()

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "model_loaded": waf_service.model is not None
    }

@app.post("/model/update")
async def update_model(update_request: ModelUpdateRequest, background_tasks: BackgroundTasks):
    """Incrementally update model with new benign data"""
    # This would implement LoRA-based incremental updates
    # For now, just acknowledge the request
    background_tasks.add_task(
        _process_model_update,
        update_request.log_entries,
        update_request.is_benign
    )
    
    return {
        "status": "accepted",
        "message": f"Queued {len(update_request.log_entries)} entries for model update"
    }

async def _process_model_update(log_entries: List[str], is_benign: bool):
    """Background task to process model updates"""
    # TODO: Implement LoRA-based incremental training
    logging.info(f"Processing model update with {len(log_entries)} entries (benign={is_benign})")

# New endpoint: trigger training from logs
@app.post("/train_from_logs")
async def train_from_logs(req: TrainFromLogsRequest, background_tasks: BackgroundTasks):
    try:
        background_tasks.add_task(
            waf_service._train_from_logs_sync,
            req.log_paths or [],
            req.epochs,
            req.max_lines,
            req.batch_size
        )
        return {"status": "started", "message": "Training started", "params": req.dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Training status endpoint
@app.get("/train/status")
async def train_status():
    return waf_service.training_status

# Reload model endpoint
@app.post("/model/reload")
async def reload_model():
    try:
        waf_service.load_model()
        return {"status": "reloaded", "model_loaded": waf_service.model is not None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Run the service
    uvicorn.run(
        "waf_service:app",
        host="0.0.0.0",
        port=8081,
        reload=False,
        log_level="info"
    )
