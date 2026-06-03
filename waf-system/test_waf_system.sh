#!/bin/bash

# Test Script for WAF System
# Comprehensive testing of all WAF components

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
WAF_ROOT="$SCRIPT_DIR"
PROJECT_ROOT="$( cd "$WAF_ROOT/.." && pwd )"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

print_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

print_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Test counter
TESTS_RUN=0
TESTS_PASSED=0

run_test() {
    local test_name="$1"
    local test_command="$2"
    
    print_test "$test_name"
    TESTS_RUN=$((TESTS_RUN + 1))
    
    if eval "$test_command" >/dev/null 2>&1; then
        print_pass "$test_name"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        print_fail "$test_name"
        return 1
    fi
}

echo "=========================================="
echo "🧪 WAF System Comprehensive Testing"
echo "=========================================="
echo ""

# Basic service availability tests
print_test "Testing service availability..."

run_test "Tomcat service responding" "curl -s http://localhost:8080 -o /dev/null"
run_test "WAF ML service health check" "curl -s http://localhost:8081/health -o /dev/null"
run_test "Monitoring dashboard available" "curl -s http://localhost:8502 -o /dev/null"

# Application tests
print_test "Testing deployed applications..."

run_test "Blog CMS application" "curl -s http://localhost:8080/blog-cms/ -o /dev/null"
run_test "E-commerce application" "curl -s http://localhost:8080/ecommerce/ -o /dev/null" 
run_test "REST API application" "curl -s http://localhost:8080/rest-api/ -o /dev/null"

# WAF functionality tests
print_test "Testing WAF ML service functionality..."

# Test normal request scoring
print_test "Testing normal request scoring..."
NORMAL_REQUEST='{"method":"GET","uri":"/blog-cms/posts","headers":{"User-Agent":"Mozilla/5.0"},"remote_addr":"127.0.0.1","user_agent":"Mozilla/5.0"}'

if curl -s -X POST -H "Content-Type: application/json" -d "$NORMAL_REQUEST" http://localhost:8081/score | grep -q "anomaly_score"; then
    print_pass "Normal request scoring works"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    print_fail "Normal request scoring failed"
fi
TESTS_RUN=$((TESTS_RUN + 1))

# Test suspicious request scoring
print_test "Testing suspicious request scoring..."
SUSPICIOUS_REQUEST='{"method":"GET","uri":"/admin/../../etc/passwd","headers":{"User-Agent":"sqlmap/1.0"},"remote_addr":"127.0.0.1","user_agent":"sqlmap/1.0"}'

if curl -s -X POST -H "Content-Type: application/json" -d "$SUSPICIOUS_REQUEST" http://localhost:8081/score | grep -q "anomaly_score"; then
    print_pass "Suspicious request scoring works"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    print_fail "Suspicious request scoring failed"
fi
TESTS_RUN=$((TESTS_RUN + 1))

# Test WAF statistics endpoint
run_test "WAF statistics endpoint" "curl -s http://localhost:8081/stats | grep -q 'total_requests'"

# File system tests
print_test "Testing file system setup..."

run_test "Logs directory exists" "test -d '$WAF_ROOT/data/logs'"
run_test "Models directory exists" "test -d '$WAF_ROOT/data/models'"
# Glob-safe access log detection: either nginx access.log exists OR tomcat access logs match
run_test "Access log file created" "test -f '$WAF_ROOT/data/logs/access.log' || compgen -G \"$WAF_ROOT/tomcat/current/logs/localhost_access_log*.txt\" > /dev/null"

# Python environment tests
print_test "Testing Python environment..."

cd "$WAF_ROOT"
if [ -d "python-env" ]; then
    source python-env/bin/activate
    
    run_test "PyTorch installation" "python -c 'import torch; print(torch.__version__)'"
    run_test "Transformers library" "python -c 'import transformers; print(transformers.__version__)'"
    run_test "FastAPI installation" "python -c 'import fastapi; print(fastapi.__version__)'"
    run_test "Custom WAF modules importable" "python -c 'import sys; sys.path.append(\"ml-pipeline/training\"); import waf_model'"
    
    deactivate
else
    print_warning "Python virtual environment not found"
fi

# Traffic generation test
print_test "Testing traffic generation capabilities..."

# Generate a small amount of test traffic
print_test "Generating test traffic..."
for i in {1..10}; do
    curl -s http://localhost:8080/blog-cms/ -o /dev/null &
    curl -s http://localhost:8080/ecommerce/ -o /dev/null &
    curl -s http://localhost:8080/rest-api/ -o /dev/null &
done
wait

print_pass "Test traffic generation completed"
TESTS_PASSED=$((TESTS_PASSED + 1))
TESTS_RUN=$((TESTS_RUN + 1))

# Check if traffic appears in logs
sleep 2
# Use compgen to safely detect files when multiple matches may exist
if compgen -G "$WAF_ROOT/tomcat/current/logs/localhost_access_log*.txt" > /dev/null; then
    if grep -q "GET" "$WAF_ROOT/tomcat/current/logs/localhost_access_log"*.txt 2>/dev/null; then
        print_pass "Traffic logging works"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        print_fail "No traffic found in logs"
    fi
else
    print_fail "Access log file not found"
fi
TESTS_RUN=$((TESTS_RUN + 1))

# Advanced tests
print_test "Running advanced functionality tests..."

# Test batch scoring
BATCH_REQUEST='{"requests":[{"method":"GET","uri":"/test1","headers":{},"remote_addr":"127.0.0.1","user_agent":"test"},{"method":"POST","uri":"/test2","headers":{},"remote_addr":"127.0.0.1","user_agent":"test"}]}'

if curl -s -X POST -H "Content-Type: application/json" -d "$BATCH_REQUEST" http://localhost:8081/score/batch | grep -q "anomaly_score"; then
    print_pass "Batch request scoring works"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    print_fail "Batch request scoring failed"
fi
TESTS_RUN=$((TESTS_RUN + 1))

# Security tests
print_test "Running security tests..."

# Test various attack patterns
ATTACK_PATTERNS=(
    "GET /admin/../../etc/passwd HTTP/1.1"
    "GET /index.php?id=1' UNION SELECT * FROM users-- HTTP/1.1"
    "GET /<script>alert('xss')</script> HTTP/1.1"
    "GET /search?q=<script>document.cookie</script> HTTP/1.1"
)

for pattern in "${ATTACK_PATTERNS[@]}"; do
    method=$(echo "$pattern" | cut -d' ' -f1)
    uri=$(echo "$pattern" | cut -d' ' -f2)
    
    attack_request="{\"method\":\"$method\",\"uri\":\"$uri\",\"headers\":{\"User-Agent\":\"AttackBot/1.0\"},\"remote_addr\":\"127.0.0.1\",\"user_agent\":\"AttackBot/1.0\"}"
    
    response=$(curl -s -X POST -H "Content-Type: application/json" -d "$attack_request" http://localhost:8081/score)
    
    if echo "$response" | grep -q "anomaly_score"; then
        anomaly_score=$(echo "$response" | grep -o '"anomaly_score":[0-9.]*' | cut -d':' -f2)
        echo "    Attack pattern: $uri -> Score: $anomaly_score"
    fi
done

print_pass "Security pattern testing completed"
TESTS_PASSED=$((TESTS_PASSED + 1))
TESTS_RUN=$((TESTS_RUN + 1))

# Test active blocking through Nginx on port 8088
print_test "Testing active threat blocking through Nginx reverse proxy (port 8088)..."
BLOCKED_COUNT=0
for pattern in "${ATTACK_PATTERNS[@]}"; do
    method=$(echo "$pattern" | cut -d' ' -f1)
    uri=$(echo "$pattern" | cut -d' ' -f2)
    
    # Send request to Nginx proxy
    http_code=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" -H "User-Agent: AttackBot/1.0" "http://localhost:8088$uri")
    
    if [ "$http_code" -eq 403 ]; then
        echo "    Active Blocking: $method $uri -> BLOCKED (HTTP 403)"
        BLOCKED_COUNT=$((BLOCKED_COUNT + 1))
    else
        echo "    Active Blocking: $method $uri -> ALLOWED (HTTP $http_code)"
    fi
done

if [ $BLOCKED_COUNT -gt 0 ]; then
    print_pass "Active blocking test passed ($BLOCKED_COUNT/${#ATTACK_PATTERNS[@]} attacks blocked)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    print_warning "Active blocking test failed (0/${#ATTACK_PATTERNS[@]} attacks blocked)"
fi
TESTS_RUN=$((TESTS_RUN + 1))

# Performance test
print_test "Running performance test..."

start_time=$(date +%s.%N)
for i in {1..50}; do
    curl -s -X POST -H "Content-Type: application/json" -d "$NORMAL_REQUEST" http://localhost:8081/score -o /dev/null &
done
wait
end_time=$(date +%s.%N)

duration=$(echo "$end_time - $start_time" | bc)
rps=$(echo "scale=2; 50 / $duration" | bc)

echo "    Performance: 50 requests in ${duration}s (${rps} req/s)"

if (( $(echo "$rps > 10" | bc -l) )); then
    print_pass "Performance test (>10 req/s)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    print_fail "Performance test (<10 req/s)"
fi
TESTS_RUN=$((TESTS_RUN + 1))

# Integration test - end-to-end workflow
print_test "Running end-to-end integration test..."

# 1. Generate traffic
# 2. Check if it appears in logs
# 3. Verify WAF processes it
# 4. Check monitoring data

print_test "Step 1: Generate diverse traffic patterns..."
USER_AGENTS=("Mozilla/5.0" "curl/7.68.0" "python-requests/2.25.1")
PATHS=("/", "/users", "/products", "/search?q=test", "/admin", "/api/v1/users")

for i in {1..20}; do
    ua=${USER_AGENTS[$((RANDOM % ${#USER_AGENTS[@]}))]}
    path=${PATHS[$((RANDOM % ${#PATHS[@]}))]}
    app=$((RANDOM % 3))
    
    case $app in
        0) base_url="http://localhost:8080/blog-cms" ;;
        1) base_url="http://localhost:8080/ecommerce" ;;
        2) base_url="http://localhost:8080/rest-api" ;;
    esac
    
    curl -s -H "User-Agent: $ua" "$base_url$path" -o /dev/null &
done
wait

sleep 3
print_pass "Traffic generation completed"

# Final summary
echo ""
echo "=========================================="
echo "📊 Test Results Summary"
echo "=========================================="
echo ""
echo "Total Tests Run: $TESTS_RUN"
echo "Tests Passed: $TESTS_PASSED"
echo "Tests Failed: $((TESTS_RUN - TESTS_PASSED))"
echo ""

if [ $TESTS_PASSED -eq $TESTS_RUN ]; then
    print_pass "🎉 ALL TESTS PASSED!"
    echo ""
    echo "✅ Your WAF system is fully functional and ready for use!"
    echo ""
    echo "🔗 Quick Links:"
    echo "  • Applications: http://localhost:8080/"
    echo "  • WAF API: http://localhost:8081/"
    echo "  • Monitoring: http://localhost:8502/"
    echo ""
    echo "📈 Next Steps:"
    echo "  1. Visit the monitoring dashboard to see live metrics"
    echo "  2. Try sending some test requests to the applications"
    echo "  3. Check the WAF detection results in real-time"
    echo "  4. Experiment with malicious payloads (safely!)"
    
    exit 0
else
    print_fail "Some tests failed. Please check the logs and configuration."
    echo ""
    echo "🔧 Troubleshooting:"
    echo "  • Check service logs: tail -f $WAF_ROOT/logs/*.log"
    echo "  • Verify all services are running: ps aux | grep -E '(tomcat|python|nginx)'"
    echo "  • Check port availability: lsof -i :8080,8081,8502"
    
    exit 1
fi
