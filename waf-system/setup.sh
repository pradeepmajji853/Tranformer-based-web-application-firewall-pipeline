#!/bin/bash

# WAF System Setup Script
# This script sets up the complete WAF environment including Tomcat, Nginx, and ML components

set -e

echo "=== WAF System Setup ==="
echo "Setting up complete WAF pipeline with Tomcat, Nginx, and ML components..."

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
WAF_ROOT="$SCRIPT_DIR"
PROJECT_ROOT="$( cd "$WAF_ROOT/.." && pwd )"
TOMCAT_VERSION="9.0.82"
NGINX_VERSION="1.24.0"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Create necessary directories
print_status "Creating directory structure..."
mkdir -p "$WAF_ROOT"/{tomcat,nginx,python-env,data/{logs,models,training},config}

cd "$PROJECT_ROOT"

# Check and install Homebrew if on macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    if ! command_exists brew; then
        print_status "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
fi

# Install system dependencies
print_status "Installing system dependencies..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    if ! command_exists python3; then
        brew install python@3.11
    fi
    if ! command_exists java; then
        brew install openjdk@11
    fi
    if ! command_exists nginx; then
        brew install nginx
    fi
    if ! command_exists maven; then
        brew install maven
    fi
    if ! command_exists wget; then
        brew install wget
    fi
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip python3-venv openjdk-11-jdk maven nginx wget curl
fi

# Download and setup Tomcat
print_status "Setting up Apache Tomcat $TOMCAT_VERSION..."
TOMCAT_DIR="$WAF_ROOT/tomcat"
if [ ! -d "$TOMCAT_DIR/apache-tomcat-$TOMCAT_VERSION" ]; then
    cd "$TOMCAT_DIR"
    wget -q "https://archive.apache.org/dist/tomcat/tomcat-9/v$TOMCAT_VERSION/bin/apache-tomcat-$TOMCAT_VERSION.tar.gz"
    tar -xzf "apache-tomcat-$TOMCAT_VERSION.tar.gz"
    rm "apache-tomcat-$TOMCAT_VERSION.tar.gz"
    
    # Make scripts executable
    chmod +x "apache-tomcat-$TOMCAT_VERSION/bin/"*.sh
    
    # Create symbolic link for easier access
    ln -sf "apache-tomcat-$TOMCAT_VERSION" current
fi

# Deploy WAR files to Tomcat
print_status "Deploying WAR files to Tomcat..."
TOMCAT_WEBAPPS="$TOMCAT_DIR/current/webapps"
cp "$PROJECT_ROOT"/*/target/*.war "$TOMCAT_WEBAPPS/"

# Setup Python environment for ML pipeline
print_status "Setting up Python environment for ML pipeline..."
cd "$WAF_ROOT"
if [ ! -f "python-env/bin/activate" ]; then
    python3 -m venv python-env
fi

# Activate virtual environment and install dependencies
source python-env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

print_status "Installing additional ML dependencies..."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# Create Nginx configuration
print_status "Creating Nginx configuration..."
cat > "$WAF_ROOT/nginx/nginx.conf" << EOF
events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    
    # Custom log format for WAF training
    log_format waf_format '\$remote_addr - \$remote_user [\$time_local] '
                          '"\$request" \$status \$body_bytes_sent '
                          '"\$http_referer" "\$http_user_agent" '
                          '\$request_time';
    
    access_log $WAF_ROOT/data/logs/access.log waf_format;
    error_log $WAF_ROOT/data/logs/error.log;
    
    upstream tomcat_backend {
        server localhost:8080;
    }
    
    upstream waf_ml_service {
        server localhost:8081;
    }
    
    server {
        listen 8088;
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
            access_log $WAF_ROOT/data/logs/access.log waf_format;
            
            proxy_pass http://tomcat_backend;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        }
    }
}
EOF

print_status "Skipping creation of start/stop scripts as they are already managed in git."

print_status "WAF System setup complete!"
print_status "Run '$WAF_ROOT/start_waf_system.sh' to start the system"
print_status "Run '$WAF_ROOT/stop_waf_system.sh' to stop the system"
