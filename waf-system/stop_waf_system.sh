#!/bin/bash

# WAF System Shutdown Script

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
WAF_ROOT="$SCRIPT_DIR"
PROJECT_ROOT="$( cd "$WAF_ROOT/.." && pwd )"

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

echo "=========================================="
echo "🛑 WAF System Shutdown"
echo "=========================================="

cd "$WAF_ROOT"

# Stop Nginx (custom prefix, no sudo)
print_status "Stopping Nginx..."
nginx -p "$WAF_ROOT" -c "$WAF_ROOT/nginx.conf" -s stop 2>/dev/null || print_warning "Nginx not running or failed to stop"

# Stop services using PID files
if [ -f "logs/system.pids" ]; then
    source logs/system.pids
    
    print_status "Stopping WAF services..."
    
    if [ -n "$WAF_SERVICE_PID" ]; then
        kill $WAF_SERVICE_PID 2>/dev/null || true
        print_status "WAF service stopped"
    fi
    
    if [ -n "$DASHBOARD_PID" ]; then
        kill $DASHBOARD_PID 2>/dev/null || true
        print_status "Dashboard stopped"
    fi
    
    if [ -n "$TRAFFIC_PID" ]; then
        kill $TRAFFIC_PID 2>/dev/null || true
        print_status "Traffic generation stopped"
    fi
fi

# Stop any remaining Python processes
print_status "Stopping Python processes..."
pkill -f "waf_service.py" 2>/dev/null || true
pkill -f "streamlit run monitoring/dashboard.py" 2>/dev/null || true
pkill -f "traffic_generator.py" 2>/dev/null || true

# Stop Tomcat
print_status "Stopping Tomcat..."
if [ -f "tomcat/current/bin/shutdown.sh" ]; then
    "$WAF_ROOT/tomcat/current/bin/shutdown.sh" 2>/dev/null || print_warning "Tomcat not running or failed to stop"
else
    print_warning "Tomcat shutdown script not found"
fi

# Wait for graceful shutdown
sleep 5

# Force kill any remaining Java processes
print_status "Checking for remaining processes..."
TOMCAT_PIDS=$(pgrep -f "catalina" 2>/dev/null || true)
if [ -n "$TOMCAT_PIDS" ]; then
    print_warning "Force killing remaining Tomcat processes..."
    kill -9 $TOMCAT_PIDS 2>/dev/null || true
fi

# Clean up PID files
rm -f logs/*.pid
rm -f logs/system.pids

print_status "WAF System shutdown complete!"
echo ""
echo "🔍 To verify all services are stopped:"
echo "  • Check ports: lsof -i :8088,8080,8081,8502"
echo "  • Check processes: ps aux | grep -E '(nginx|java|python)'"
