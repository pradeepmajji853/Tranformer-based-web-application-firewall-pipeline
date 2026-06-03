#!/bin/bash

# Complete WAF System Startup Script
# This script starts all components of the WAF system in the correct order

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
WAF_ROOT="$SCRIPT_DIR"
PROJECT_ROOT="$( cd "$WAF_ROOT/.." && pwd )"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Function to check if port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null ; then
        return 0
    else
        return 1
    fi
}

# Function to wait for service to be ready
wait_for_service() {
    local url=$1
    local service_name=$2
    local max_attempts=30
    local attempt=1
    
    print_status "Waiting for $service_name to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s $url >/dev/null 2>&1; then
            print_status "$service_name is ready!"
            return 0
        fi
        
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    print_error "$service_name failed to start within expected time"
    return 1
}

echo "=========================================="
echo "🛡️  WAF System Complete Startup"
echo "=========================================="
echo ""

# Check prerequisites
print_step "Checking prerequisites..."

# Check if Java is installed
if ! command -v java &> /dev/null; then
    print_error "Java is required but not installed"
    exit 1
fi

# Check if Python virtual environment exists
if [ ! -d "$WAF_ROOT/python-env" ]; then
    print_error "Python environment not found. Run setup.sh first"
    exit 1
fi

print_status "Prerequisites check passed"

# Create necessary directories
print_step "Creating directories..."
mkdir -p "$WAF_ROOT"/{data/{logs,models,training},logs,config}

# Start Tomcat
print_step "Starting Apache Tomcat..."
cd "$WAF_ROOT"

# Download and setup Tomcat if not exists
if [ ! -d "tomcat/current" ]; then
    print_status "Setting up Tomcat..."
    mkdir -p tomcat
    cd tomcat
    
    TOMCAT_VERSION="9.0.82"
    if [ ! -f "apache-tomcat-$TOMCAT_VERSION.tar.gz" ]; then
        wget -q "https://archive.apache.org/dist/tomcat/tomcat-9/v$TOMCAT_VERSION/bin/apache-tomcat-$TOMCAT_VERSION.tar.gz"
    fi
    
    if [ ! -d "apache-tomcat-$TOMCAT_VERSION" ]; then
        tar -xzf "apache-tomcat-$TOMCAT_VERSION.tar.gz"
        chmod +x "apache-tomcat-$TOMCAT_VERSION/bin/"*.sh
        ln -sf "apache-tomcat-$TOMCAT_VERSION" current
    fi
    
    cd ..
fi

# Deploy WAR files
print_status "Deploying WAR files..."
cp "$PROJECT_ROOT"/*/target/*.war "$WAF_ROOT/tomcat/current/webapps/" 2>/dev/null || true

# Configure Tomcat for logging
print_status "Configuring Tomcat logging..."
cat > "$WAF_ROOT/tomcat/current/conf/server.xml" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<Server port="8005" shutdown="SHUTDOWN">
  <Listener className="org.apache.catalina.startup.VersionLoggerListener" />
  <Listener className="org.apache.catalina.core.AprLifecycleListener" SSLEngine="on" />
  <Listener className="org.apache.catalina.core.JreMemoryLeakPreventionListener" />
  <Listener className="org.apache.catalina.mbeans.GlobalResourcesLifecycleListener" />
  <Listener className="org.apache.catalina.core.ThreadLocalLeakPreventionListener" />

  <GlobalNamingResources>
    <Resource name="UserDatabase" auth="Container"
              type="org.apache.catalina.UserDatabase"
              description="User database that can be updated and saved"
              factory="org.apache.catalina.users.MemoryUserDatabaseFactory"
              pathname="conf/tomcat-users.xml" />
  </GlobalNamingResources>

  <Service name="Catalina">
    <Connector port="8080" protocol="HTTP/1.1"
               connectionTimeout="20000"
               redirectPort="8443" />

    <Engine name="Catalina" defaultHost="localhost">
      <Realm className="org.apache.catalina.realm.LockOutRealm">
        <Realm className="org.apache.catalina.realm.UserDatabaseRealm"
               resourceName="UserDatabase"/>
      </Realm>

      <Host name="localhost" appBase="webapps"
            unpackWARs="true" autoDeploy="true">
        
        <!-- Access Log Valve for WAF training -->
        <Valve className="org.apache.catalina.valves.AccessLogValve" directory="logs"
               prefix="localhost_access_log" suffix=".txt"
               pattern='%h - %u %t "%r" %s %b "%{Referer}i" "%{User-Agent}i" %D' />
      </Host>
    </Engine>
  </Service>
</Server>
EOF

# Start Tomcat
if check_port 8080; then
    print_warning "Port 8080 already in use, stopping existing Tomcat"
    "$WAF_ROOT/tomcat/current/bin/shutdown.sh" 2>/dev/null || true
    sleep 5
fi

export CATALINA_HOME="$WAF_ROOT/tomcat/current"
"$WAF_ROOT/tomcat/current/bin/startup.sh"

# Wait for Tomcat to start
wait_for_service "http://localhost:8080" "Tomcat"

# Start Python ML Pipeline
print_step "Starting ML Pipeline..."
cd "$WAF_ROOT"
source python-env/bin/activate

# Ensure core requirements are installed (torch, fastapi, etc.)
pip install -q -r requirements.txt || true

# Install any missing dependencies (include requests, remove invalid sqlite3)
pip install -q streamlit plotly httpx pyyaml locust faker requests ipywidgets nbclient nbconvert ipykernel || true

# Start WAF inference service
print_status "Starting WAF inference service..."
# Stop any existing process on 8081 that might be older
if lsof -Pi :8081 -sTCP:LISTEN -t >/dev/null ; then
    print_warning "Port 8081 in use, attempting to stop existing WAF service"
    kill $(lsof -Pi :8081 -sTCP:LISTEN -t) || true
    sleep 2
fi
nohup python ml-pipeline/inference/waf_service.py > logs/waf_service.log 2>&1 &
WAF_SERVICE_PID=$!
echo $WAF_SERVICE_PID > logs/waf_service.pid

# Wait for ML service to start
wait_for_service "http://localhost:8081/health" "WAF ML Service"

# Install and configure Nginx if available
print_step "Configuring reverse proxy..."

# Check if nginx is available
if command -v nginx &> /dev/null; then
    print_status "Configuring Nginx reverse proxy..."

    # Resolve mime.types path with fallbacks
    MIME_TYPES_PATH="/etc/nginx/mime.types"
    if [ ! -f "$MIME_TYPES_PATH" ]; then
        if [ -f "/opt/homebrew/etc/nginx/mime.types" ]; then
            MIME_TYPES_PATH="/opt/homebrew/etc/nginx/mime.types"
        elif [ -f "/usr/local/etc/nginx/mime.types" ]; then
            MIME_TYPES_PATH="/usr/local/etc/nginx/mime.types"
        else
            # Create a minimal local mime.types
            cat > "$WAF_ROOT/nginx_mime.types" << 'EOMT'
types {
    text/html                             html htm shtml;
    text/css                              css;
    text/xml                              xml;
    image/gif                             gif;
    image/jpeg                            jpeg jpg;
    application/javascript                js;
    application/json                      json;
    application/xml                       xml;
}
EOMT
            MIME_TYPES_PATH="$WAF_ROOT/nginx_mime.types"
        fi
    fi

    # Choose a non-privileged port to avoid sudo
    NGINX_PORT=8088

    # Create nginx config with resolved mime types path
    cat > "$WAF_ROOT/nginx.conf" << EOF
events {
    worker_connections 1024;
}

http {
    include $MIME_TYPES_PATH;
    default_type application/octet-stream;
    
    # Custom log format for WAF training
    log_format waf_format '
        \$remote_addr - \$remote_user [\$time_local] '
        '"\$request" \$status \$body_bytes_sent '
        '"\$http_referer" "\$http_user_agent" '
        '\$request_time';
    
    access_log "$WAF_ROOT/data/logs/access.log" waf_format;
    error_log "$WAF_ROOT/data/logs/error.log";
    
    upstream tomcat_backend {
        server localhost:8080;
    }
    
    upstream waf_ml_service {
        server localhost:8081;
    }
    
    server {
        listen $NGINX_PORT;
        server_name localhost;
        
        # WAF ML Service endpoint
        location /waf-api/ {
            proxy_pass http://waf_ml_service/;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        }
        
        # Internal WAF validation subrequest
        location = /waf-validate {
            internal;
            proxy_pass http://waf_ml_service/validate;
            proxy_pass_request_body off;
            proxy_set_header Content-Length "";
            proxy_set_header X-Original-URI \$request_uri;
            proxy_set_header X-Original-Method \$request_method;
            proxy_set_header X-Original-IP \$remote_addr;
            proxy_set_header X-Original-UA \$http_user_agent;
        }
        
        # Main application proxy
        location / {
            auth_request /waf-validate;
            
            # Log request for ML processing
            access_log "$WAF_ROOT/data/logs/access.log" waf_format;
            
            proxy_pass http://tomcat_backend;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        }
    }
}
EOF

    # Stop any nginx instance started with our prefix
    nginx -p "$WAF_ROOT" -c "$WAF_ROOT/nginx.conf" -s stop 2>/dev/null || true
    sleep 1

    # Start Nginx without sudo on high port and with bootstrap error log
    if check_port $NGINX_PORT; then
        print_warning "Port $NGINX_PORT in use, attempting to stop existing nginx"
        nginx -p "$WAF_ROOT" -c "$WAF_ROOT/nginx.conf" -s stop 2>/dev/null || true
        sleep 2
    fi
    
    nginx -g "error_log '$WAF_ROOT/data/logs/nginx_bootstrap_error.log' notice;" -p "$WAF_ROOT" -c "$WAF_ROOT/nginx.conf"
    print_status "Nginx reverse proxy started on port $NGINX_PORT"
else
    print_warning "Nginx not available, WAF will run on port 8080 directly"
fi

# Generate initial training traffic
print_step "Generating initial training traffic..."
print_status "Starting traffic generation (this may take a few minutes)..."

# Start traffic generation in background
cd "$WAF_ROOT"
nohup python -c "
import subprocess
import time
import sys
sys.path.append('scripts')

# Start a simple traffic generator
import requests
import random
import threading
import time

def generate_traffic():
    base_urls = [
        'http://localhost:8080/blog-cms/',
        'http://localhost:8080/ecommerce/', 
        'http://localhost:8080/rest-api/'
    ]
    
    paths = [
        '', 'index.jsp', 'users', 'products', 'posts', 'search?q=test',
        'api/users', 'api/tasks', 'cart', 'login', 'admin'
    ]
    
    user_agents = [
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'curl/7.68.0',
        'Python-requests/2.25.1'
    ]
    
    for _ in range(200):  # Generate 200 requests
        try:
            base_url = random.choice(base_urls)
            path = random.choice(paths)
            user_agent = random.choice(user_agents)
            
            headers = {'User-Agent': user_agent}
            
            url = base_url + path
            response = requests.get(url, headers=headers, timeout=5)
            print(f'Generated request: {response.status_code} {url}')
            
            time.sleep(random.uniform(0.1, 2.0))  # Random delay
            
        except Exception as e:
            print(f'Request failed: {e}')
            
    print('Traffic generation completed')

generate_traffic()
" > logs/traffic_generation.log 2>&1 &

TRAFFIC_PID=$!
echo $TRAFFIC_PID > logs/traffic_generation.pid

# Wait for some traffic to be generated
sleep 30

# Start monitoring dashboard
print_step "Starting monitoring dashboard..."
nohup streamlit run monitoring/dashboard.py --server.port=8502 --server.headless=true > logs/dashboard.log 2>&1 &
DASHBOARD_PID=$!
echo $DASHBOARD_PID > logs/dashboard.pid

# Wait for dashboard to start
sleep 5

# Save all PIDs for cleanup
cat > "$WAF_ROOT/logs/system.pids" << EOF
TOMCAT_PID=$(pgrep -f "catalina")
WAF_SERVICE_PID=$WAF_SERVICE_PID
DASHBOARD_PID=$DASHBOARD_PID
TRAFFIC_PID=$TRAFFIC_PID
EOF

echo ""
echo "=========================================="
echo "🛡️  WAF System Started Successfully!"
echo "=========================================="
echo ""
echo "📊 Services Running:"
echo "  • Tomcat (Java Apps):     http://localhost:8080"
echo "  • WAF ML Service:         http://localhost:8081"
echo "  • Monitoring Dashboard:   http://localhost:8502"
if command -v nginx &> /dev/null; then
    echo "  • Nginx Reverse Proxy:    http://localhost:8088"
fi
echo ""
echo "🎯 Applications Available:"
echo "  • Blog CMS:               http://localhost:8080/blog-cms/"
echo "  • E-commerce:             http://localhost:8080/ecommerce/"  
echo "  • REST API:               http://localhost:8080/rest-api/"
echo ""
echo "📁 Important Paths:"
echo "  • Logs:                   $WAF_ROOT/data/logs/"
echo "  • Models:                 $WAF_ROOT/data/models/"
echo "  • Configuration:          $WAF_ROOT/config/"
echo ""
echo "🔧 Management Commands:"
echo "  • View logs:              tail -f $WAF_ROOT/logs/*.log"
echo "  • Stop system:            $WAF_ROOT/stop_waf_system.sh"
echo "  • Restart WAF service:    $WAF_ROOT/restart_waf_service.sh"
echo ""
echo "🧪 Testing the WAF:"
echo "  1. Open the monitoring dashboard: http://localhost:8502"
echo "  2. Generate some traffic to the applications"
echo "  3. Check the anomaly detection results in the dashboard"
echo ""
print_status "System startup completed successfully!"
print_warning "Note: Initial model training will start automatically as traffic is generated"
