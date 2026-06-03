"""
WAF Monitoring Dashboard
Real-time monitoring and visualization of WAF performance and threats
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import sqlite3

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import httpx

# Compatibility helper for Streamlit rerun across versions
def _st_rerun():
    try:
        st.rerun()
    except AttributeError:
        try:
            st.experimental_rerun()
        except AttributeError:
            pass

def _fetch_json(url: str, method: str = 'GET', json_data: dict | None = None, timeout: float = 10.0):
    try:
        if method.upper() == 'POST':
            r = httpx.post(url, json=json_data, timeout=timeout)
        else:
            r = httpx.get(url, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logging.warning(f"HTTP call failed: {e}")
    return None

class WAFMonitor:
    """Monitor for WAF system metrics and alerts"""
    
    def __init__(self, db_path: str = "data/waf_monitoring.db"):
        self.db_path = db_path
        self.init_database()
        self.waf_service_url = "http://localhost:8081"
        
    def init_database(self):
        """Initialize SQLite database for monitoring data"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            # Requests table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME,
                    method TEXT,
                    path TEXT,
                    status_code INTEGER,
                    anomaly_score REAL,
                    is_anomalous BOOLEAN,
                    confidence REAL,
                    processing_time_ms REAL,
                    source_ip TEXT,
                    user_agent TEXT
                )
            """)
            
            # Alerts table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME,
                    alert_type TEXT,
                    severity TEXT,
                    message TEXT,
                    details TEXT,
                    resolved BOOLEAN DEFAULT FALSE
                )
            """)
            
            # Model metrics table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS model_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME,
                    metric_name TEXT,
                    metric_value REAL,
                    model_version TEXT
                )
            """)
            
            conn.commit()
            
    def log_request(self, request_data: Dict[str, Any]):
        """Log a request and its analysis results"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO requests (
                    timestamp, method, path, status_code, anomaly_score,
                    is_anomalous, confidence, processing_time_ms, source_ip, user_agent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.utcnow(),
                request_data.get('method'),
                request_data.get('path'),
                request_data.get('status_code'),
                request_data.get('anomaly_score'),
                request_data.get('is_anomalous'),
                request_data.get('confidence'),
                request_data.get('processing_time_ms'),
                request_data.get('source_ip'),
                request_data.get('user_agent')
            ))
            
    def create_alert(self, alert_type: str, severity: str, message: str, details: str = ""):
        """Create a new alert"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO alerts (timestamp, alert_type, severity, message, details)
                VALUES (?, ?, ?, ?, ?)
            """, (datetime.utcnow(), alert_type, severity, message, details))
            
    def get_recent_requests(self, hours: int = 24) -> pd.DataFrame:
        """Get recent requests data"""
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT * FROM requests 
                WHERE timestamp > datetime('now', '-{} hours')
                ORDER BY timestamp DESC
            """.format(hours)
            
            return pd.read_sql_query(query, conn)
            
    def get_alerts(self, hours: int = 24, resolved: bool = False) -> pd.DataFrame:
        """Get recent alerts"""
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT * FROM alerts 
                WHERE timestamp > datetime('now', '-{} hours')
                AND resolved = {}
                ORDER BY timestamp DESC
            """.format(hours, resolved)
            
            return pd.read_sql_query(query, conn)
            
    def get_threat_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Get threat detection statistics"""
        with sqlite3.connect(self.db_path) as conn:
            total_requests = conn.execute("""
                SELECT COUNT(*) FROM requests 
                WHERE timestamp > datetime('now', '-{} hours')
            """.format(hours)).fetchone()[0]
            
            anomalous_requests = conn.execute("""
                SELECT COUNT(*) FROM requests 
                WHERE timestamp > datetime('now', '-{} hours')
                AND is_anomalous = 1
            """.format(hours)).fetchone()[0]
            
            avg_processing_time = conn.execute("""
                SELECT AVG(processing_time_ms) FROM requests 
                WHERE timestamp > datetime('now', '-{} hours')
            """.format(hours)).fetchone()[0] or 0
            
            top_attack_paths = conn.execute("""
                SELECT path, COUNT(*) as count FROM requests 
                WHERE timestamp > datetime('now', '-{} hours')
                AND is_anomalous = 1
                GROUP BY path
                ORDER BY count DESC
                LIMIT 10
            """.format(hours)).fetchall()
            
            return {
                'total_requests': total_requests,
                'anomalous_requests': anomalous_requests,
                'anomaly_rate': (anomalous_requests / max(1, total_requests)) * 100,
                'avg_processing_time': avg_processing_time,
                'top_attack_paths': top_attack_paths
            }

class WAFDashboard:
    """Streamlit-based WAF monitoring dashboard"""
    
    def __init__(self):
        self.monitor = WAFMonitor()
        self.setup_page()
        
    def setup_page(self):
        """Setup Streamlit page configuration and inject custom styles"""
        st.set_page_config(
            page_title="WAF Sentinel | AI Web Application Firewall Console",
            page_icon="🛡️",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        # Premium CSS Injection
        st.markdown("""
            <style>
            @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap');
            
            /* CSS Variables */
            :root {
                --primary: #6c5ce7;
                --primary-glow: rgba(108, 92, 231, 0.25);
                --success: #00b894;
                --danger: #ff7675;
                --warning: #f1c40f;
                --card-bg: rgba(255, 255, 255, 0.04);
            }
            
            /* Theme Fonts */
            html, body, [class*="css"], .stMarkdown {
                font-family: 'Outfit', sans-serif !important;
            }
            code, pre, [class*="mono"] {
                font-family: 'JetBrains Mono', monospace !important;
            }
            
            /* Gradient Header */
            .main-header {
                background: linear-gradient(135deg, #a29bfe 0%, #6c5ce7 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                font-weight: 800;
                font-size: 2.8rem;
                margin-bottom: 0px;
                letter-spacing: -0.5px;
            }
            
            /* Card Grid Styles */
            .metric-card {
                background: var(--card-bg);
                backdrop-filter: blur(8px);
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-radius: 16px;
                padding: 20px;
                box-shadow: 0 4px 20px 0 rgba(0, 0, 0, 0.2);
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            }
            .metric-card:hover {
                transform: translateY(-3px);
                border-color: var(--primary);
                box-shadow: 0 8px 30px 0 var(--primary-glow);
            }
            .metric-label {
                font-size: 0.85rem;
                font-weight: 700;
                color: #b2bec3;
                text-transform: uppercase;
                letter-spacing: 1.2px;
                margin-bottom: 6px;
            }
            .metric-value {
                font-size: 2.0rem;
                font-weight: 800;
                color: #ffffff;
                line-height: 1.1;
            }
            
            /* Status Badges */
            .status-badge {
                display: inline-flex;
                align-items: center;
                gap: 6px;
                padding: 5px 12px;
                border-radius: 50px;
                font-size: 0.85rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            .status-online {
                background: rgba(0, 184, 148, 0.15);
                color: var(--success);
                border: 1px solid rgba(0, 184, 148, 0.3);
            }
            .status-offline {
                background: rgba(255, 118, 117, 0.15);
                color: var(--danger);
                border: 1px solid rgba(255, 118, 117, 0.3);
            }
            
            /* Recruiter Specs Box */
            .spec-box {
                background: rgba(108, 92, 231, 0.04);
                border: 1px solid rgba(108, 92, 231, 0.15);
                border-radius: 12px;
                padding: 15px;
                margin-bottom: 12px;
            }
            .spec-title {
                font-size: 0.8rem;
                font-weight: 700;
                color: #a29bfe;
                text-transform: uppercase;
                letter-spacing: 1px;
                margin-bottom: 4px;
            }
            .spec-content {
                font-size: 1.05rem;
                font-weight: 600;
                color: #ffffff;
            }
            </style>
        """, unsafe_allow_html=True)
        
    def render_header_metrics(self):
        """Render metrics row in glassmorphism dashboard cards"""
        threat_stats = self.monitor.get_threat_statistics(hours=24)
        live_stats = _fetch_json("http://localhost:8081/stats") or {}
        
        total_requests = threat_stats['total_requests']
        blocked_threats = threat_stats['anomalous_requests']
        anomaly_rate = threat_stats['anomaly_rate']
        avg_processing_time = threat_stats['avg_processing_time']
        
        if live_stats:
            total_requests = live_stats.get('total_requests', total_requests)
            anomaly_rate = live_stats.get('anomaly_rate', anomaly_rate)
            if anomaly_rate < 1.0 and anomaly_rate > 0:
                anomaly_rate *= 100.0
            avg_processing_time = live_stats.get('avg_processing_time', avg_processing_time)
            
        status_class = "status-online" if live_stats else "status-offline"
        status_text = "🟢 Active (ML Online)" if live_stats else "🔴 Offline"
        
        st.markdown(f"""
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 25px;">
                <div class="metric-card">
                    <div class="metric-label">WAF Guard Status</div>
                    <div class="metric-value">
                        <span class="status-badge {status_class}">{status_text}</span>
                    </div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Processed Requests (24h)</div>
                    <div class="metric-value">{total_requests:,}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Blocked Threats (24h)</div>
                    <div class="metric-value" style="color: {'var(--danger)' if blocked_threats > 0 else 'var(--success)'};">
                        {blocked_threats:,}
                    </div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Model Avg Latency</div>
                    <div class="metric-value" style="color: #a29bfe;">{avg_processing_time:.1f}ms</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    def render_project_overview(self):
        """Render the primary recruiter-focused project welcome tab"""
        st.markdown("### 🚀 Project Overview & Architecture")
        st.markdown(
            "Welcome to the **WAF Sentinel** console. This is an advanced machine-learning Web Application Firewall "
            "designed to intercept and block web attacks inline using self-supervised transformer models."
        )
        
        col1, col2 = st.columns([3, 2])
        
        with col1:
            st.markdown("#### 🔍 How this Project Works")
            st.markdown(
                "1. **LogBERT Anomaly Model**: Traditional rule-based WAFs rely on fragile, complex regular expressions. "
                "Instead, this system uses a custom **4-layer Transformer Encoder** trained on baseline normal traffic. "
                "It learns the deep syntax of normal HTTP requests and flags sequence deviations as anomalies."
            )
            st.markdown(
                "2. **Active Inline Blocking**: Nginx (port `8088`) intercepts all incoming requests. Using the `auth_request` "
                "module, Nginx queries the WAF ML service (`/validate` endpoint) in sub-10ms. If anomalous, it returns "
                "HTTP `403 Forbidden`, blocking the attacker instantly before the payload reaches the server."
            )
            st.markdown(
                "3. **Zero-Downtime LoRA Pipeline**: When new benign logs are ingested, low-rank adapters (LoRA) "
                "can be fine-tuned in a background thread and loaded into memory instantly without stopping the service."
            )
            
            st.markdown("#### 🗺️ Deployment Flowchart")
            st.code("""
  [ Client / Attacker ]
           │
           ▼ (HTTP Request on Port 8088)
     [ Nginx Proxy ]  ───(auth_request /validate)───►  [ FastAPI WAF ML Service (Port 8081) ]
           │                                                        │
      (HTTP 200 OK)                                           (HTTP 403 Forbidden)
           │                                                        │
           ▼                                                        ▼
[ Tomcat Web Apps (Port 8080) ]                               [ Blocked! (HTTP 403) ]
  ├─ /blog-cms/ (JSP Blog)
  ├─ /ecommerce/ (Shopping App)
  └─ /rest-api/ (Task Manager)
            """, language="text")
            
        with col2:
            st.markdown("#### ⚙️ Technical Specifications")
            st.markdown(f"""
                <div class="spec-box">
                    <div class="spec-title">ML Model Architecture</div>
                    <div class="spec-content">Transformer Encoder (4 Layers, 8 Attention Heads)</div>
                </div>
                <div class="spec-box">
                    <div class="spec-title">Active Protection Proxy</div>
                    <div class="spec-content">Nginx Reverse Proxy (port 8088) using auth_request</div>
                </div>
                <div class="spec-box">
                    <div class="spec-title">Target Servlets</div>
                    <div class="spec-content">3 Java WAR Web Applications running on Tomcat (port 8080)</div>
                </div>
                <div class="spec-box">
                    <div class="spec-title">Background Training Engine</div>
                    <div class="spec-content">Self-Supervised MLM + Contrastive Learning</div>
                </div>
            """, unsafe_allow_html=True)
            
            st.markdown("#### 🔗 Deployed Applications Links")
            st.markdown("- **Secure Access Gateway (Protected via Nginx WAF - Port 8088)**:")
            st.markdown("  * [E-commerce App (Secure)](http://localhost:8088/ecommerce/)")
            st.markdown("  * [REST Task API (Secure)](http://localhost:8088/rest-api/)")
            st.markdown("  * [Blog CMS App (Secure)](http://localhost:8088/blog-cms/)")
            st.markdown("- **Direct Tomcat Gateway (Unprotected Bypass - Port 8080)**:")
            st.markdown("  * [Tomcat Manager Home](http://localhost:8080/)")

    def render_threat_center(self):
        """Render threat details and active alerts"""
        st.markdown("### 🚨 Threat Center")
        st.markdown("Review detected attacks, anomalous endpoints, and operational system alerts.")
        
        col1, col2 = st.columns([3, 2])
        
        with col1:
            st.markdown("#### 🎯 Most Targeted Endpoints (Top 10)")
            threat_stats = self.monitor.get_threat_statistics(hours=24)
            if threat_stats['top_attack_paths']:
                paths_df = pd.DataFrame(
                    threat_stats['top_attack_paths'],
                    columns=['Path', 'Attack Count']
                )
                
                fig = px.bar(
                    paths_df.head(10),
                    x='Attack Count',
                    y='Path',
                    orientation='h',
                    color='Attack Count',
                    color_continuous_scale=['#fd79a8', '#ff7675', '#d63031']
                )
                fig.update_layout(
                    height=380,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="Outfit, sans-serif", color="#b2bec3"),
                    margin=dict(t=10, b=10, l=10, r=10)
                )
                fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(255,255,255,0.05)')
                fig.update_yaxes(showgrid=False)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No threat data registered in the last 24 hours.")
                
        with col2:
            st.markdown("#### ⚠️ Active Security Alerts")
            alerts_df = self.monitor.get_alerts(hours=24, resolved=False)
            
            if not alerts_df.empty:
                for _, alert in alerts_df.iterrows():
                    with st.expander(f"🚨 {alert['alert_type']} - {alert['severity'].upper()}", expanded=True):
                        st.markdown(f"**Time:** {alert['timestamp']}")
                        st.markdown(f"**Message:** {alert['message']}")
                        if alert['details']:
                            st.caption(f"Details: {alert['details']}")
                        if st.button(f"Resolve Alert {alert['id']}", key=f"resolve_{alert['id']}"):
                            with sqlite3.connect(self.monitor.db_path) as conn:
                                conn.execute("UPDATE alerts SET resolved = 1 WHERE id = ?", (alert['id'],))
                            st.success("Alert resolved successfully!")
                            _st_rerun()
            else:
                st.success("All systems green. No active alerts!")

    def render_traffic_analytics(self):
        """Render detailed traffic analytics & anomaly timeline charts"""
        st.markdown("### 📊 Traffic & Anomaly Analytics")
        st.markdown("Deep dive telemetry charts tracking request throughput, anomaly baselines, and model inference speed.")
        
        df = self.monitor.get_recent_requests(hours=24)
        
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Resample hourly
            df_hourly = df.set_index('timestamp').resample('h').agg({
                'id': 'count',
                'is_anomalous': 'sum',
                'anomaly_score': 'mean',
                'processing_time_ms': 'mean'
            }).reset_index()
            
            df_hourly['normal_requests'] = df_hourly['id'] - df_hourly['is_anomalous']
            
            fig = make_subplots(
                rows=2, cols=1,
                subplot_titles=('Request Volume', 'Avg Anomaly Score & Latency (ms)'),
                vertical_spacing=0.15
            )
            
            # Volume
            fig.add_trace(
                go.Bar(
                    x=df_hourly['timestamp'],
                    y=df_hourly['normal_requests'],
                    name='Allowed (Benign)',
                    marker_color='#00b894'
                ),
                row=1, col=1
            )
            fig.add_trace(
                go.Bar(
                    x=df_hourly['timestamp'],
                    y=df_hourly['is_anomalous'],
                    name='Blocked (Anomalous)',
                    marker_color='#ff7675'
                ),
                row=1, col=1
            )
            
            # Anomaly & Latency
            fig.add_trace(
                go.Scatter(
                    x=df_hourly['timestamp'],
                    y=df_hourly['anomaly_score'],
                    name='Avg Anomaly Score',
                    line=dict(color='#fd9644', width=3)
                ),
                row=2, col=1
            )
            fig.add_trace(
                go.Scatter(
                    x=df_hourly['timestamp'],
                    y=df_hourly['processing_time_ms'],
                    name='Avg Latency (ms)',
                    line=dict(color='#a29bfe', width=2, dash='dash')
                ),
                row=2, col=1
            )
            
            fig.update_layout(
                height=520,
                showlegend=True,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Outfit, sans-serif", color="#b2bec3"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(t=50, b=30, l=10, r=10)
            )
            
            # Grid lines
            for row in [1, 2]:
                fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(255,255,255,0.05)', row=row, col=1)
                fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(255,255,255,0.05)', row=row, col=1)
                
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No traffic telemetry logged yet. Generate some traffic to see metrics.")

    def render_model_performance(self):
        """Render model statistics, hyperparameters, and custom background training control"""
        st.markdown("### 🤖 LogBERT Model & LoRA Training")
        st.markdown(
            "This section displays model statuses and controls for retraining/fine-tuning. "
            "Retraining runs asynchronously in a background thread pool, keeping the main WAF thread non-blocking."
        )
        
        status = _fetch_json("http://localhost:8081/train/status") or {}
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("#### ⚙️Retraining Controls")
            with st.form("retrain_form"):
                epochs = st.number_input("Retrain Epochs", min_value=1, max_value=10, value=1)
                batch_size = st.number_input("Batch Size", min_value=8, max_value=128, value=32, step=8)
                max_lines = st.number_input("Max Log Lines to Ingest", min_value=100, max_value=20000, value=5000, step=100)
                
                default_paths = [
                    str(Path('data/logs/access.log').resolve()),
                    str(Path('tomcat/current/logs/localhost_access_log*.txt').resolve())
                ]
                synth = Path('data/logs/benign_synth.log').resolve()
                if synth.exists():
                    default_paths.insert(0, str(synth))
                log_paths_str = st.text_input("Log Sources (comma separated paths/globs)", ", ".join(default_paths))
                
                submitted = st.form_submit_button("Launch Retraining Task", type="primary")
                
            if submitted:
                paths = [p.strip() for p in log_paths_str.split(',') if p.strip()]
                payload = {
                    "log_paths": paths,
                    "epochs": int(epochs),
                    "max_lines": int(max_lines),
                    "batch_size": int(batch_size)
                }
                res = _fetch_json("http://localhost:8081/train_from_logs", method='POST', json_data=payload)
                if res and res.get('status') == 'started':
                    st.success("Background training successfully initiated! Event loop is safe.")
                else:
                    st.warning("Failed to start training. Verify WAF ML service port.")
                _st_rerun()
                
        with col2:
            st.markdown("#### 📡 Real-Time Retraining Telemetry")
            if status:
                st.markdown(f"""
                    <div class="spec-box">
                        <div class="spec-title">Current Training State</div>
                        <div class="spec-content" style="color: var(--primary); text-transform: uppercase;">
                            {status.get('status', 'idle')}
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                
                progress = min(1.0, float(status.get('progress', 0.0)))
                st.markdown(f"**Retraining Progress:** {progress*100:.0f}%")
                st.progress(progress)
                
                st.markdown(f"**Epoch Sequence:** {status.get('current_epoch', 0)} / {status.get('epochs_total', 0)}")
                
                if status.get('result'):
                    st.markdown("**Latest Metrics Output:**")
                    st.json(status['result'])
                if status.get('error'):
                    st.error(status['error'])
            else:
                st.info("Telemetry data unavailable.")
                
            if st.button("🔄 Hot-Reload Active Weights"):
                res = _fetch_json("http://localhost:8081/model/reload", method='POST')
                if res and res.get('status') == 'reloaded':
                    st.success("Trained weights hot-reloaded successfully with zero-downtime!")
                else:
                    st.error("Failed to reload active weights.")

    def render_live_feed(self):
        """Render clean, color-coded live request log feed"""
        st.markdown("### 📡 Real-Time HTTP Ingestion Feed")
        st.markdown("Live tail of all HTTP requests passing through the Nginx secure proxy gateway.")
        
        df = self.monitor.get_recent_requests(hours=1)
        
        if not df.empty:
            recent_df = df.head(30)[['timestamp', 'method', 'path', 'status_code', 'anomaly_score', 'is_anomalous', 'source_ip']]
            
            def highlight_row(row):
                if row['is_anomalous']:
                    # Light reddish color for blocked anomalies
                    return ['background-color: rgba(255, 118, 117, 0.15)'] * len(row)
                # Light greenish color for allowed requests
                return ['background-color: rgba(0, 184, 148, 0.05)'] * len(row)
                
            styled_df = recent_df.style.apply(highlight_row, axis=1)
            st.dataframe(styled_df, use_container_width=True)
        else:
            st.info("No recent requests processed in the last hour.")

    def render_quick_test(self):
        """Render interactive attack sandbox playground"""
        st.markdown("### 🧪 Attack Sandbox Playground")
        st.markdown(
            "Test attack payloads against the ML model. Send requests live and watch the model classify, "
            "score, and flag them based on sequence token patterns."
        )
        
        with st.form("sandbox_form"):
            col1, col2 = st.columns([1, 1])
            with col1:
                method = st.selectbox("HTTP Method", ["GET", "POST", "PUT", "DELETE"], index=0)
                path = st.text_input("Request Endpoint", value="/ecommerce/search?q=")
                payload = st.text_input("Attack Vector / Input Parameter", value="' OR '1'='1")
            with col2:
                user_agent = st.text_input("User-Agent Header", value="Mozilla/5.0 (Macintosh; Intel Mac OS X)")
                remote_addr = st.text_input("Client IP", value="192.168.1.50")
                body = st.text_area("POST Request Body", value="", height=70)
                
            submitted = st.form_submit_button("Submit Payload to WAF Guard")
            
        if submitted:
            uri = path
            if method in ["GET", "DELETE"]:
                uri = f"{path}{payload}"
            elif method in ["POST", "PUT"] and not body:
                body = payload
                
            req = {
                "method": method,
                "uri": uri,
                "headers": {"X-Sandbox-Client": "1"},
                "remote_addr": remote_addr,
                "user_agent": user_agent,
                "body": body or None
            }
            
            res = _fetch_json("http://localhost:8081/score", method='POST', json_data=req)
            if res:
                score = res.get('anomaly_score', 0.0)
                is_anomalous = res.get('is_anomalous', False)
                confidence = res.get('confidence', 0.0)
                
                # Visual notification banner
                if is_anomalous:
                    st.error(
                        f"🚨 **WAF ALERT: BLOCK ACTION TRIGGERED (HTTP 403)** | "
                        f"Anomaly Score: {score:.4f} | Confidence: {confidence:.2f}"
                    )
                else:
                    st.success(
                        f"✅ **WAF OK: REQUEST ALLOWED (HTTP 200)** | "
                        f"Anomaly Score: {score:.4f} | Confidence: {confidence:.2f}"
                    )
                    
                st.markdown("#### Model Inference Details JSON")
                st.json(res)
                
                # Log locally to update analytics
                self.monitor.log_request({
                    'method': method,
                    'path': uri,
                    'status_code': 403 if is_anomalous else 200,
                    'anomaly_score': float(score),
                    'is_anomalous': bool(is_anomalous),
                    'confidence': float(confidence),
                    'processing_time_ms': float(res.get('processing_time_ms', 0.0)),
                    'source_ip': remote_addr,
                    'user_agent': user_agent
                })
            else:
                st.error("Failed to fetch response. Make sure the WAF ML service is running.")

    def render_sidebar(self):
        """Render sidebar dashboard details and guard status"""
        st.sidebar.markdown("### 🛡️ WAF Sentinel Config")
        
        # System settings
        time_range = st.sidebar.selectbox("Analytics Window", ["Last Hour", "Last 6 Hours", "Last 24 Hours"], index=2)
        auto_refresh = st.sidebar.checkbox("Dashboard Auto-Refresh (30s)", value=False)
        
        # System micro-stats
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### ⚙️ Gateway Statuses")
        
        # Check active status of services
        tomcat_ok = _fetch_json("http://localhost:8080") is not None
        ml_ok = _fetch_json("http://localhost:8081/health") is not None
        nginx_ok = _fetch_json("http://localhost:8088/ecommerce/") is not None # checking via nginx
        
        def render_status_bullet(label: str, status: bool):
            indicator = "🟢 ONLINE" if status else "🔴 OFFLINE"
            color = "var(--success)" if status else "var(--danger)"
            st.sidebar.markdown(f"**{label}:** <span style='color: {color}; font-weight:700;'>{indicator}</span>", unsafe_allow_html=True)
            
        render_status_bullet("Nginx Gateway (8088)", nginx_ok)
        render_status_bullet("WAF ML Engine (8081)", ml_ok)
        render_status_bullet("Tomcat Server (8080)", tomcat_ok)
        
        # Retraining indicator
        status = _fetch_json("http://localhost:8081/train/status") or {}
        is_training = status.get('running', False)
        train_indicator = "🔄 RETRAINING..." if is_training else "🟢 IDLE"
        train_color = "var(--warning)" if is_training else "var(--success)"
        st.sidebar.markdown(f"**Model Status:** <span style='color: {train_color}; font-weight:700;'>{train_indicator}</span>", unsafe_allow_html=True)
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("##### 💡 Recruiter Tip:")
        st.sidebar.caption(
            "Use the **🧪 Attack Sandbox** to submit malicious strings like `UNION SELECT` or `<script>` to see the model actively catch attacks."
        )
        
        if st.sidebar.button("🔄 Reload Dashboard Logs"):
            _st_rerun()
            
        return {
            'time_range': time_range,
            'auto_refresh': auto_refresh
        }

    def run(self):
        """Run the dashboard app"""
        # Render sidebar
        settings = self.render_sidebar()
        
        # Main Title & Subtitle
        st.markdown('<div class="main-header">🛡️ WAF Sentinel</div>', unsafe_allow_html=True)
        st.markdown(
            '<div style="font-size: 1.15rem; color: #b2bec3; margin-bottom: 25px; font-weight: 500;">'
            'AI-Powered Web Application Firewall with Real-Time Transformer Anomaly Interception'
            '</div>', 
            unsafe_allow_html=True
        )
        
        # Render dynamic glassmorphic card metrics
        self.render_header_metrics()
        
        # Configure tab structure
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "🚀 Project Overview", 
            "🚨 Threat Center", 
            "📊 Traffic Analytics", 
            "🤖 Model & LoRA Retraining", 
            "📡 Real-time Log Feed", 
            "🧪 Attack Sandbox"
        ])
        
        with tab1:
            self.render_project_overview()
            
        with tab2:
            self.render_threat_center()
            
        with tab3:
            self.render_traffic_analytics()
            
        with tab4:
            self.render_model_performance()
            
        with tab5:
            self.render_live_feed()
            
        with tab6:
            self.render_quick_test()
            
        # Dashboard auto refresh logic
        if settings['auto_refresh']:
            time.sleep(30)
            _st_rerun()

def main():
    dashboard = WAFDashboard()
    dashboard.run()

if __name__ == "__main__":
    main()
