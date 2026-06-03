"""
WAF Training Pipeline Orchestrator
Coordinates the entire training pipeline from log generation to model deployment
"""

import asyncio
import logging
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import subprocess
import signal
import sys
import yaml

# Import our modules
sys.path.append('../ml-pipeline/ingestion')
sys.path.append('../ml-pipeline/preprocessing')
sys.path.append('../ml-pipeline/training')
sys.path.append('../ml-pipeline/inference')

from log_ingestion import LogIngestion
from log_processor import LogPreprocessor
from trainer import WAFTrainer, prepare_training_data, collate_fn
from lora_trainer import IncrementalUpdateManager
from waf_model import create_waf_model

class WAFPipelineOrchestrator:
    """Main orchestrator for the WAF training pipeline"""
    
    def __init__(self, config_path: str = "config/pipeline_config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        
        # Initialize components
        self.log_ingestion = None
        self.preprocessor = LogPreprocessor()
        self.model = None
        self.tokenizer = None
        self.trainer = None
        self.update_manager = None
        
        # Pipeline state
        self.is_running = False
        self.processed_sequences = []
        self.training_in_progress = False
        
        # Logging
        self.logger = logging.getLogger(__name__)
        self.setup_logging()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load pipeline configuration"""
        config_path = Path(self.config_path)
        
        if not config_path.exists():
            # Create default config dynamically
            script_dir = Path(__file__).resolve().parent
            project_root = (script_dir / '../..').resolve()
            waf_root = project_root / 'waf-system'
            
            default_config = {
                'logging': {
                    'level': 'INFO',
                    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                },
                'data': {
                    'log_paths': [
                        str(waf_root / 'data' / 'logs' / 'access.log')
                    ],
                    'training_data_dir': str(waf_root / 'data' / 'training'),
                    'model_dir': str(waf_root / 'data' / 'models')
                },
                'model': {
                    'vocab_size': 10000,
                    'hidden_size': 256,
                    'num_layers': 4,
                    'max_sequence_length': 512
                },
                'training': {
                    'batch_size': 32,
                    'learning_rate': 5e-5,
                    'num_epochs': 10,
                    'validation_split': 0.2,
                    'early_stopping_patience': 3
                },
                'pipeline': {
                    'min_sequences_for_training': 1000,
                    'incremental_update_threshold': 500,
                    'training_schedule_hours': 24  # Retrain every 24 hours
                },
                'traffic_generation': {
                    'duration_minutes': 30,
                    'users_per_second': 2,
                    'ramp_up_time': 30
                }
            }
            
            # Save default config
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, 'w') as f:
                yaml.dump(default_config, f, default_flow_style=False)
                
            return default_config
        
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
            
    def setup_logging(self):
        """Setup logging configuration"""
        log_config = self.config.get('logging', {})
        
        logging.basicConfig(
            level=getattr(logging, log_config.get('level', 'INFO')),
            format=log_config.get('format', '%(asctime)s - %(levelname)s - %(message)s'),
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('logs/pipeline.log')
            ]
        )
        
    async def initialize(self):
        """Initialize all pipeline components"""
        self.logger.info("Initializing WAF Training Pipeline...")
        
        # Create directories
        for dir_key in ['training_data_dir', 'model_dir']:
            dir_path = Path(self.config['data'][dir_key])
            dir_path.mkdir(parents=True, exist_ok=True)
            
        Path('logs').mkdir(exist_ok=True)
        
        # Initialize log ingestion
        log_paths = self.config['data']['log_paths']
        self.log_ingestion = LogIngestion(log_paths)
        
        # Initialize or load model
        model_path = Path(self.config['data']['model_dir']) / 'best_model.pt'
        if model_path.exists():
            await self.load_existing_model(str(model_path))
        else:
            await self.initialize_new_model()
            
        # Initialize incremental update manager
        self.update_manager = IncrementalUpdateManager(
            model_path=str(model_path),
            tokenizer=self.tokenizer,
            update_threshold=self.config['pipeline']['incremental_update_threshold']
        )
        
        self.logger.info("Pipeline initialization complete")
        
    async def initialize_new_model(self):
        """Initialize a new model"""
        self.logger.info("Creating new WAF model...")
        
        model_config = self.config['model']
        self.model, self.tokenizer = create_waf_model(
            vocab_size=model_config['vocab_size']
        )
        
        # Initialize trainer
        training_config = self.config['training']
        self.trainer = WAFTrainer(
            self.model,
            self.tokenizer,
            learning_rate=training_config['learning_rate']
        )
        
    async def load_existing_model(self, model_path: str):
        """Load existing trained model"""
        self.logger.info(f"Loading existing model from {model_path}")
        
        # This would load the trained model
        # For now, create new model
        await self.initialize_new_model()
        
    async def generate_training_traffic(self):
        """Generate synthetic traffic for training"""
        self.logger.info("Starting traffic generation for training data...")
        
        traffic_config = self.config['traffic_generation']
        
        # Start traffic generation using Locust
        locust_cmd = [
            'locust',
            '-f', 'scripts/traffic_generator.py',
            '--host', 'http://localhost',
            '--users', str(traffic_config.get('users_per_second', 2) * 60),
            '--spawn-rate', str(traffic_config['users_per_second']),
            '--run-time', f"{traffic_config['duration_minutes']}m",
            '--headless'
        ]
        
        try:
            process = subprocess.Popen(
                locust_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for traffic generation to complete
            stdout, stderr = process.communicate(
                timeout=traffic_config['duration_minutes'] * 60 + 300  # 5 min buffer
            )
            
            if process.returncode == 0:
                self.logger.info("Traffic generation completed successfully")
                return True
            else:
                self.logger.error(f"Traffic generation failed: {stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.warning("Traffic generation timed out")
            process.kill()
            return False
        except Exception as e:
            self.logger.error(f"Error in traffic generation: {e}")
            return False
            
    async def collect_and_process_logs(self) -> int:
        """Collect and process logs into training sequences"""
        self.logger.info("Starting log collection and processing...")
        
        # Start log ingestion
        await self.log_ingestion.start_ingestion()
        
        processed_count = 0
        sequence_buffer = []
        
        try:
            # Process logs for a specific duration or until we have enough
            min_sequences = self.config['pipeline']['min_sequences_for_training']
            start_time = time.time()
            timeout = 300  # 5 minutes timeout
            
            async for log_entry in self.log_ingestion.get_log_stream():
                # Process log entry
                processed = self.preprocessor.process_log_entry(log_entry['raw_log'])
                
                if processed:
                    # Create sequence from processed log
                    sequence = self._create_training_sequence(processed)
                    if sequence:
                        sequence_buffer.append(sequence)
                        processed_count += 1
                        
                        # Add to tokenizer vocabulary
                        for token in sequence:
                            self.tokenizer.add_token(token)
                
                # Check stopping conditions
                if (len(sequence_buffer) >= min_sequences or 
                    time.time() - start_time > timeout):
                    break
                    
        except Exception as e:
            self.logger.error(f"Error in log processing: {e}")
        finally:
            self.log_ingestion.stop_ingestion()
            
        # Store processed sequences
        self.processed_sequences.extend(sequence_buffer)
        
        self.logger.info(f"Processed {processed_count} log entries into {len(sequence_buffer)} sequences")
        return len(sequence_buffer)
        
    def _create_training_sequence(self, processed: Dict[str, Any]) -> List[str]:
        """Create training sequence from processed log entry"""
        parsed = processed['parsed']
        
        sequence = [
            parsed.get('method', 'GET'),
            self._normalize_path(parsed.get('path_only', '/')),
            str(parsed.get('status', 200)),
        ]
        
        # Add additional features
        features = processed.get('features', {})
        
        if features.get('has_referer'):
            sequence.append('HAS_REFERER')
            
        if features.get('is_error'):
            sequence.append('ERROR_STATUS')
            
        # Add user agent category
        user_agent = parsed.get('http_user_agent', '')
        if 'Mozilla' in user_agent:
            sequence.append('BROWSER')
        elif any(bot in user_agent.lower() for bot in ['curl', 'wget', 'python']):
            sequence.append('API_CLIENT')
        else:
            sequence.append('OTHER_AGENT')
            
        return sequence
        
    def _normalize_path(self, path: str) -> str:
        """Normalize URL path for training"""
        # Replace numeric IDs with placeholder
        import re
        normalized = re.sub(r'/\d+', '/<ID>', path)
        return normalized
        
    async def train_initial_model(self):
        """Train the initial model on collected sequences"""
        if len(self.processed_sequences) < self.config['pipeline']['min_sequences_for_training']:
            self.logger.warning("Not enough sequences for training")
            return False
            
        self.logger.info(f"Starting initial model training with {len(self.processed_sequences)} sequences")
        self.training_in_progress = True
        
        try:
            # Prepare datasets
            train_dataset, val_dataset = prepare_training_data(
                self.processed_sequences,
                self.tokenizer
            )
            
            # Create data loaders
            from torch.utils.data import DataLoader
            
            training_config = self.config['training']
            train_dataloader = DataLoader(
                train_dataset,
                batch_size=training_config['batch_size'],
                shuffle=True,
                collate_fn=collate_fn
            )
            
            val_dataloader = DataLoader(
                val_dataset,
                batch_size=training_config['batch_size'],
                shuffle=False,
                collate_fn=collate_fn
            ) if val_dataset else None
            
            # Train model
            model_dir = Path(self.config['data']['model_dir'])
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.trainer.train(
                    train_dataloader=train_dataloader,
                    val_dataloader=val_dataloader,
                    num_epochs=training_config['num_epochs'],
                    save_dir=str(model_dir),
                    early_stopping_patience=training_config['early_stopping_patience']
                )
            )
            
            self.logger.info("Initial model training completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error in model training: {e}")
            return False
        finally:
            self.training_in_progress = False
            
    async def run_continuous_pipeline(self):
        """Run the continuous training pipeline"""
        self.is_running = True
        self.logger.info("Starting continuous WAF training pipeline...")
        
        # Initial setup
        await self.generate_training_traffic()
        await asyncio.sleep(10)  # Wait for logs to be written
        
        sequences_collected = await self.collect_and_process_logs()
        
        if sequences_collected > 0:
            success = await self.train_initial_model()
            if not success:
                self.logger.error("Initial training failed")
                return False
        
        # Start continuous monitoring and incremental updates
        last_training_time = time.time()
        training_interval = self.config['pipeline']['training_schedule_hours'] * 3600
        
        while self.is_running:
            try:
                # Collect new logs
                new_sequences = await self.collect_and_process_logs()
                
                if new_sequences > 0 and self.update_manager:
                    # Add to incremental update buffer
                    recent_sequences = self.processed_sequences[-new_sequences:]
                    self.update_manager.add_benign_sequences(recent_sequences)
                
                # Check if it's time for a full retraining
                if (time.time() - last_training_time) > training_interval:
                    self.logger.info("Scheduled retraining triggered")
                    await self.train_initial_model()
                    last_training_time = time.time()
                
                # Wait before next collection cycle
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                self.logger.error(f"Error in continuous pipeline: {e}")
                await asyncio.sleep(60)
                
        self.logger.info("Continuous pipeline stopped")
        
    def stop_pipeline(self):
        """Stop the continuous pipeline"""
        self.is_running = False
        if self.log_ingestion:
            self.log_ingestion.stop_ingestion()
            
    def get_pipeline_status(self) -> Dict[str, Any]:
        """Get current pipeline status"""
        return {
            'is_running': self.is_running,
            'training_in_progress': self.training_in_progress,
            'total_sequences_processed': len(self.processed_sequences),
            'model_loaded': self.model is not None,
            'tokenizer_vocab_size': len(self.tokenizer.token_to_id) if self.tokenizer else 0,
            'update_manager_status': self.update_manager.get_update_status() if self.update_manager else None
        }

async def main():
    """Main entry point"""
    orchestrator = WAFPipelineOrchestrator()
    
    # Handle shutdown gracefully
    def signal_handler(signum, frame):
        print("\nShutting down pipeline...")
        orchestrator.stop_pipeline()
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Initialize and run
    await orchestrator.initialize()
    await orchestrator.run_continuous_pipeline()

if __name__ == "__main__":
    asyncio.run(main())
