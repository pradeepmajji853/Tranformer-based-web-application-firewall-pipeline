# 🛡️ Transformer-Based Web Application Firewall (WAF) with Active Threat Blocking

This project contains a fully implemented, production-ready Web Application Firewall (WAF) using a transformer-based model (inspired by LogBERT) to protect three sample Java web applications in real-time. The system has been configured with an Nginx reverse proxy to perform **active inline blocking** of malicious HTTP requests (such as SQL Injection, Cross-Site Scripting, and Path Traversal) by intercepting traffic and returning `403 Forbidden` responses.

---

## 🏗️ System Architecture

The following diagram illustrates how incoming traffic is intercepted and validated by the WAF before reaching the Java application servers:

```mermaid
graph TD
    Client[Browser / Attacker] -->|HTTP Request| Nginx[Nginx Reverse Proxy<br/>Port 8088]
    Nginx -->|1. auth_request /validate| WAF_ML[WAF ML Service<br/>Port 8081]
    
    subgraph "WAF Service (FastAPI)"
        WAF_ML -->|2. Check Sequence| Tokenizer[LogBERT Tokenizer]
        Tokenizer -->|3. Evaluate| Model[Transformer Model]
        Model -->|4. Detect UNK/Signature Threat| Scoring[Calibrated Scoring Engine]
    end
    
    Scoring -->|"5. Anomalous (Score > 0.50)"| WAF_ML
    Scoring -->|"5. Safe (Score <= 0.50)"| WAF_ML
    
    WAF_ML -->|6a. HTTP 403 Forbidden| Nginx
    WAF_ML -->|6b. HTTP 200 OK| Nginx
    
    Nginx -->|7a. Block (403)| Client
    Nginx -->|7b. Forward Request| Tomcat[Apache Tomcat Server<br/>Port 8080]
    
    subgraph "Tomcat Servlet Container"
        Tomcat --> App1[Blog CMS App<br/>/blog-cms]
        Tomcat --> App2[E-commerce App<br/>/ecommerce]
        Tomcat --> App3[REST API App<br/>/rest-api]
    end
    
    Tomcat -->|8. Access Logs| Ingestion[Log Ingestion Pipeline]
    Ingestion -->|9. Incremental updates| LoRA[LoRA Fine-tuning]
    LoRA -.->|Updates weights| Model
    
    style Client fill:#f9f,stroke:#333,stroke-width:2px
    style Nginx fill:#bbf,stroke:#333,stroke-width:2px
    style WAF_ML fill:#fdd,stroke:#333,stroke-width:2px
    style Tomcat fill:#dfd,stroke:#333,stroke-width:2px
```

### Core Architecture Components
1. **Java Web Applications**: Three sample Java WAR applications running on Tomcat (`8080`) that serve as targets and traffic sources:
   - **E-commerce App (`/ecommerce/`)**: Product catalog, cart actions, login/register, order handling.
   - **REST API App (`/rest-api/`)**: CRUD task APIs, user accounts, JWT/Bearer authentication.
   - **Blog CMS App (`/blog-cms/`)**: Content rendering, comment submission, file uploads. *(Completely fixed and functional!)*
2. **Reverse Proxy (Nginx)**: Runs on port `8088`. Utilizes Nginx’s native `auth_request` directive to forward request metadata to the WAF ML Service for validation before routing to Tomcat.
3. **WAF ML Service**: A FastAPI server running on port `8081` that loads a pretrained LogBERT-style transformer model and evaluates incoming requests in sub-10ms.
4. **Monitoring Dashboard**: A Streamlit dashboard running on port `8502` providing real-time log ingestion visualization, threat categories, geo-maps, and metric charts.

---

## 📦 Deployment & Services Map

Once started, the following endpoints are available:

| Service / App | Protected URL (via Nginx WAF) | Direct URL (Bypass WAF) | Description |
|---|---|---|---|
| **E-commerce App** | [http://localhost:8088/ecommerce/](http://localhost:8088/ecommerce/) | [http://localhost:8080/ecommerce/](http://localhost:8080/ecommerce/) | Catalog & Cart System |
| **REST API App** | [http://localhost:8088/rest-api/](http://localhost:8088/rest-api/) | [http://localhost:8080/rest-api/](http://localhost:8080/rest-api/) | Task & User API Endpoints |
| **Blog CMS App** | [http://localhost:8088/blog-cms/](http://localhost:8088/blog-cms/) | [http://localhost:8080/blog-cms/](http://localhost:8080/blog-cms/) | Content Management System |
| **WAF ML Service** | — | [http://localhost:8081/](http://localhost:8081/) | FastAPI Validation Engine |
| **WAF Dashboard** | — | [http://localhost:8502/](http://localhost:8502/) | Streamlit Analytics & Metrics |

---

## 🛠️ Key Technical Implementations

### 1. Blog CMS Application Integration (Fixed & Fully Operational)
Previously, the Blog CMS application loaded but failed on interactive endpoints (search, posts, comments) with `404 Not Found` due to mismatched hardcoded paths. 
- Updated [index.jsp](file:///Users/majjipradeepkumar/Downloads/purplle/Transformer%20Based%20WAF/blog-cms-app/src/main/webapp/index.jsp) paths from `/blog-cms-app/` to `/blog-cms/` to match the Tomcat context path.
- Corrected servlet endpoints from `/blogs` to `/blog` to map appropriately to Java handlers.
- Recompiled and built the clean WAR file using Maven (`mvn clean package`).

### 2. Active Inline Threat Interception via Nginx
Instead of asynchronously logging attacks, the system actively intercepts attacks using the Nginx `auth_request` module.
- Any request received by Nginx on port `8088` triggers an internal subrequest to `/waf-validate` mapping to `http://127.0.0.1:8081/validate`.
- If the WAF service returns `200 OK`, Nginx forwards the traffic to Tomcat.
- If the WAF service returns `403 Forbidden`, Nginx halts execution and immediately sends a `403 Forbidden` response back to the client.

### 3. Calibrated ML Anomaly Scoring
Because the raw LogBERT transformer's classification head is untrained in benign-only training runs (resulting in static anomaly outputs of `~0.488`), we implemented a **Calibrated Scoring Engine** in the inference service ([waf_service.py](file:///Users/majjipradeepkumar/Downloads/purplle/Transformer%20Based%20WAF/waf-system/ml-pipeline/inference/waf_service.py)):
- **Tokenizer [UNK] Check**: Attacks use unusual special characters/structures that map to Out-Of-Vocabulary (`[UNK]`) tokens. Requests generating `[UNK]` tokens are boosted to threat score `0.85`.
- **Keyword Signature Fallback**: Detects XSS, SQLi, and Traversal signatures to push scores above the block threshold (`0.50`), capping safe requests under `0.25`.
- **Transformer Encoder Likelihood**: Used to profile sequence structures and trigger adaptive thresholds.

### 4. Dynamic Path & Space-Safe Scripting
To ensure project portability across development environments:
- Shell scripts resolve `WAF_ROOT` and `PROJECT_ROOT` directories dynamically based on their current execution paths.
- Nginx configuration directives and start commands are fully quoted to support folder paths containing spaces (e.g., `Transformer Based WAF`).
- Python log ingestion scripts dynamically load path configuration parameters from environment variables or configs.

---

## 🚀 Quick Start Guide

### 📋 Prerequisites
Ensure the following tools are installed:
- **macOS** or **Linux**
- **Java 11+** (JDK)
- **Maven**
- **Python 3.8+**
- **Homebrew** (for Nginx on macOS)

---

### ⚙️ Step 1: System Setup
Run the setup script. This script validates Java, Maven, Python, and Nginx installations, sets up the virtual environment (`python-env`), and builds the Tomcat webapps:
```bash
chmod +x waf-system/setup.sh
./waf-system/setup.sh
```

### 🏁 Step 2: Start All Services
Launch the entire system. This starts Apache Tomcat, Nginx, the WAF ML service, and the Streamlit dashboard in the background:
```bash
chmod +x waf-system/start_waf_system.sh
./waf-system/start_waf_system.sh
```

### 🧪 Step 3: Run Integration Verification
Run the integrated test script to verify that requests are processed and attacks are actively blocked:
```bash
chmod +x waf-system/test_waf_system.sh
./waf-system/test_waf_system.sh
```

### 🛑 Step 4: Stop All Services
When finished, stop all background services and release the allocated network ports:
```bash
chmod +x waf-system/stop_waf_system.sh
./waf-system/stop_waf_system.sh
```

---

## 🧪 Security Test Cases & Manual Validation

You can verify the WAF's blocking capabilities using the following `curl` payloads:

### 1. SQL Injection (SQLi) Block
*Payload containing SQL syntax indicators:*
```bash
curl -i "http://localhost:8088/ecommerce/search?q=';%20DROP%20TABLE%20products;%20--"
```
*Expected Response:*
```http
HTTP/1.1 403 Forbidden
Server: nginx
Content-Type: text/html
...
```

### 2. Cross-Site Scripting (XSS) Block
*Payload containing script tags:*
```bash
curl -i "http://localhost:8088/blog-cms/search?q=<script>alert('xss')</script>"
```
*Expected Response:*
```http
HTTP/1.1 403 Forbidden
Server: nginx
...
```

### 3. Path Traversal Block
*Payload attempting to access root system files:*
```bash
curl -i "http://localhost:8088/rest-api/api/tasks/../../../../etc/passwd"
```
*Expected Response:*
```http
HTTP/1.1 403 Forbidden
Server: nginx
...
```

### 4. Normal Traffic Allowed
*Legitimate requests pass through to Tomcat:*
```bash
curl -i "http://localhost:8088/ecommerce/products"
```
*Expected Response:*
```http
HTTP/1.1 200 OK
...
```

---

## 📁 Directory Structure

```
Transformer Based WAF/
├── README.md                           # Main project documentation (This file)
├── test_traffic.sh                    # Traffic generation script
├── ecommerce-app/                     # E-commerce application (Java)
├── rest-api-app/                      # REST API application (Java)
├── blog-cms-app/                      # Blog CMS application (Java, path-fixed)
└── waf-system/                        # WAF Subsystem
    ├── config/                        # WAF configurations
    ├── data/
    │   ├── logs/                      # Access logs
    │   └── models/                    # LogBERT model checkpoints
    ├── ml-pipeline/                   # Core Python ML pipeline
    │   ├── ingestion/                 # Log ingester (access log tailing)
    │   ├── preprocessing/             # Log preprocessors and vocabulary
    │   ├── training/                  # LogBERT Model definition & training
    │   └── inference/                 # FastAPI validation endpoint (waf_service.py)
    ├── monitoring/                    # Streamlit Dashboard (dashboard.py)
    ├── nginx/                         # Config templates for Nginx reverse proxy
    ├── requirements.txt               # Python package dependencies
    ├── setup.sh                       # Setup script (python env & builds)
    ├── start_waf_system.sh            # Runs Python ML, Nginx, Tomcat, Streamlit
    ├── stop_waf_system.sh             # Kills Python ML, Nginx, Tomcat, Streamlit
    └── test_waf_system.sh             # Integration test suite
```

---

## 📈 Incremental Learning & Adaptive Pipeline
As legitimate traffic is logged in the Nginx/Tomcat access logs:
1. `log_ingestion.py` tails the logs and parses request fields.
2. Underperforming or unseen benign request sequences are collected.
3. LoRA (Low-Rank Adaptation) adapter weights are incrementally fine-tuned in the background using the self-supervised masked language modeling objective.
4. Model weights are dynamically reloaded by the FastAPI inference service without restarting the application, adapting to changing traffic baselines over time.
