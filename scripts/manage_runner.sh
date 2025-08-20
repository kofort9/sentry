#!/bin/bash
"""
GitHub Actions Runner Management Script

This script helps manage your self-hosted GitHub Actions runner and Ollama service.
Use it to start/stop services when you need them.
"""

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
RUNNER_DIR="${RUNNER_DIR:-./actions-runner}"
OLLAMA_PORT="11434"
GITHUB_REPO="kofort9/sentries"

# Helper functions
print_status() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

check_ollama() {
    if curl -sSf "http://127.0.0.1:${OLLAMA_PORT}/api/tags" >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

check_runner() {
    if [ -f "${RUNNER_DIR}/run.sh" ] && pgrep -f "actions-runner" >/dev/null; then
        return 0
    else
        return 1
    fi
}

start_ollama() {
    print_status "Starting Ollama service..."
    
    if check_ollama; then
        print_success "Ollama is already running"
        return 0
    fi
    
    # Try to start Ollama
    if command -v ollama >/dev/null 2>&1; then
        nohup ollama serve >/dev/null 2>&1 &
        sleep 3
        
        if check_ollama; then
            print_success "Ollama started successfully"
            return 0
        else
            print_error "Failed to start Ollama"
            return 1
        fi
    else
        print_error "Ollama not found. Please install it first:"
        echo "  curl -fsSL https://ollama.ai/install.sh | sh"
        return 1
    fi
}

stop_ollama() {
    print_status "Stopping Ollama service..."
    
    if ! check_ollama; then
        print_warning "Ollama is not running"
        return 0
    fi
    
    pkill -f "ollama serve" || true
    sleep 2
    
    if ! check_ollama; then
        print_success "Ollama stopped successfully"
    else
        print_warning "Ollama may still be running"
    fi
}

start_runner() {
    print_status "Starting GitHub Actions runner..."
    
    if check_runner; then
        print_success "Runner is already running"
        return 0
    fi
    
    if [ ! -d "${RUNNER_DIR}" ]; then
        print_error "Runner directory not found: ${RUNNER_DIR}"
        print_status "To set up the runner:"
        echo "  1. Go to: https://github.com/${GITHUB_REPO}/settings/actions/runners"
        echo "  2. Click 'New self-hosted runner'"
        echo "  3. Follow the setup instructions"
        return 1
    fi
    
    cd "${RUNNER_DIR}"
    nohup ./run.sh >/dev/null 2>&1 &
    sleep 3
    
    if check_runner; then
        print_success "Runner started successfully"
        return 0
    else
        print_error "Failed to start runner"
        return 1
    fi
}

stop_runner() {
    print_status "Stopping GitHub Actions runner..."
    
    if ! check_runner; then
        print_warning "Runner is not running"
        return 0
    fi
    
    pkill -f "actions-runner" || true
    sleep 2
    
    if ! check_runner; then
        print_success "Runner stopped successfully"
    else
        print_warning "Runner may still be running"
    fi
}

check_models() {
    print_status "Checking Ollama models..."
    
    if ! check_ollama; then
        print_error "Ollama is not running"
        return 1
    fi
    
    local models=$(curl -s "http://127.0.0.1:${OLLAMA_PORT}/api/tags" | jq -r '.models[].name' 2>/dev/null || echo "")
    
    if [ -n "$models" ]; then
        print_success "Installed models:"
        echo "$models" | while read -r model; do
            echo "  - $model"
        done
    else
        print_warning "No models found"
        print_status "To install required models:"
        echo "  ollama pull llama3.1:8b-instruct-q4_K_M"
        echo "  ollama pull deepseek-coder:6.7b-instruct-q5_K_M"
    fi
}

install_models() {
    print_status "Installing required models..."
    
    if ! check_ollama; then
        print_error "Ollama is not running. Start it first with: $0 start"
        return 1
    fi
    
    print_status "Installing llama3.1:8b-instruct-q4_K_M..."
    ollama pull llama3.1:8b-instruct-q4_K_M
    
    print_status "Installing deepseek-coder:6.7b-instruct-q5_K_M..."
    ollama pull deepseek-coder:6.7b-instruct-q5_K_M
    
    print_success "Models installed successfully"
}

status() {
    echo -e "${BLUE}🔍 Status Check${NC}"
    echo "=================="
    
    echo -n "Ollama: "
    if check_ollama; then
        print_success "Running"
    else
        print_error "Not running"
    fi
    
    echo -n "Runner: "
    if check_runner; then
        print_success "Running"
    else
        print_error "Not running"
    fi
    
    echo ""
    check_models
}

start_all() {
    print_status "Starting all services..."
    
    start_ollama
    start_runner
    
    print_status "Waiting for services to be ready..."
    sleep 5
    
    status
}

stop_all() {
    print_status "Stopping all services..."
    
    stop_runner
    stop_ollama
    
    print_success "All services stopped"
}

# Main script logic
case "${1:-help}" in
    start)
        start_all
        ;;
    stop)
        stop_all
        ;;
    restart)
        stop_all
        sleep 2
        start_all
        ;;
    ollama)
        case "${2:-start}" in
            start) start_ollama ;;
            stop) stop_ollama ;;
            *) echo "Usage: $0 ollama {start|stop}" ;;
        esac
        ;;
    runner)
        case "${2:-start}" in
            start) start_runner ;;
            stop) stop_runner ;;
            *) echo "Usage: $0 runner {start|stop}" ;;
        esac
        ;;
    models)
        case "${2:-check}" in
            check) check_models ;;
            install) install_models ;;
            *) echo "Usage: $0 models {check|install}" ;;
        esac
        ;;
    status)
        status
        ;;
    help|--help|-h)
        echo "GitHub Actions Runner Management Script"
        echo ""
        echo "Usage: $0 {command} [subcommand]"
        echo ""
        echo "Commands:"
        echo "  start           Start all services (Ollama + Runner)"
        echo "  stop            Stop all services"
        echo "  restart         Restart all services"
        echo "  status          Check status of all services"
        echo ""
        echo "Ollama management:"
        echo "  ollama start    Start Ollama service"
        echo "  ollama stop     Stop Ollama service"
        echo ""
        echo "Runner management:"
        echo "  runner start    Start GitHub Actions runner"
        echo "  runner stop     Stop GitHub Actions runner"
        echo ""
        echo "Model management:"
        echo "  models check    Check installed models"
        echo "  models install  Install required models"
        echo ""
        echo "Examples:"
        echo "  $0 start              # Start everything"
        echo "  $0 status             # Check status"
        echo "  $0 ollama start       # Start just Ollama"
        echo "  $0 models install     # Install required models"
        ;;
    *)
        print_error "Unknown command: $1"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac
