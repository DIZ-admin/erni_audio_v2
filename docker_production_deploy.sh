#!/bin/bash

# =============================================================================
# Production Deployment Script для Erni Audio v2
# =============================================================================

set -euo pipefail

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции для логирования
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка зависимостей
check_dependencies() {
    log_info "Проверка зависимостей..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker не установлен"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose не установлен"
        exit 1
    fi
    
    log_success "Все зависимости установлены"
}

# Проверка .env файла
check_env_file() {
    log_info "Проверка .env файла..."
    
    if [[ ! -f .env ]]; then
        log_warning ".env файл не найден. Создаю из шаблона..."
        if [[ -f .env.example ]]; then
            cp .env.example .env
            log_warning "Отредактируйте .env файл с реальными API ключами!"
            log_warning "Особенно важно установить:"
            log_warning "  - PYANNOTEAI_API_TOKEN"
            log_warning "  - OPENAI_API_KEY"
            log_warning "  - REPLICATE_API_TOKEN"
            read -p "Нажмите Enter после редактирования .env файла..."
        else
            log_error ".env.example не найден. Создайте .env файл вручную."
            exit 1
        fi
    fi
    
    # Проверяем наличие критических переменных
    source .env
    
    if [[ -z "${PYANNOTEAI_API_TOKEN:-}" ]]; then
        log_error "PYANNOTEAI_API_TOKEN не установлен в .env"
        exit 1
    fi
    
    if [[ -z "${OPENAI_API_KEY:-}" ]]; then
        log_error "OPENAI_API_KEY не установлен в .env"
        exit 1
    fi
    
    log_success ".env файл корректен"
}

# Сборка образа
build_image() {
    log_info "Сборка Docker образа..."
    
    docker build -t erni-audio-v2:latest .
    
    if [[ $? -eq 0 ]]; then
        log_success "Docker образ собран успешно"
    else
        log_error "Ошибка сборки Docker образа"
        exit 1
    fi
}

# Создание необходимых директорий
create_directories() {
    log_info "Создание необходимых директорий..."
    
    mkdir -p data/raw data/interim data/processed
    mkdir -p voiceprints
    mkdir -p logs/metrics logs/health_reports
    mkdir -p cache
    
    log_success "Директории созданы"
}

# Запуск тестов
run_tests() {
    log_info "Запуск тестов перед развёртыванием..."
    
    if [[ -f docker_test.py ]]; then
        python3 docker_test.py --quick
        if [[ $? -ne 0 ]]; then
            log_error "Базовые тесты не прошли"
            exit 1
        fi
        log_success "Базовые тесты пройдены"
    fi
    
    if [[ -f docker_functional_test.py ]]; then
        python3 docker_functional_test.py --quick
        if [[ $? -ne 0 ]]; then
            log_error "Функциональные тесты не прошли"
            exit 1
        fi
        log_success "Функциональные тесты пройдены"
    fi
}

# Развёртывание
deploy() {
    log_info "Развёртывание production среды..."
    
    # Останавливаем существующие контейнеры
    docker-compose down --remove-orphans
    
    # Запускаем новые контейнеры
    docker-compose up -d
    
    if [[ $? -eq 0 ]]; then
        log_success "Контейнеры запущены"
    else
        log_error "Ошибка запуска контейнеров"
        exit 1
    fi
}

# Проверка здоровья
health_check() {
    log_info "Проверка здоровья сервисов..."
    
    # Ждём запуска сервисов
    sleep 10
    
    # Проверяем статус контейнеров
    if docker-compose ps | grep -q "Up"; then
        log_success "Контейнеры работают"
    else
        log_error "Контейнеры не запустились"
        docker-compose logs
        exit 1
    fi
    
    # Проверяем health check основного сервиса
    log_info "Ожидание готовности сервисов (до 60 секунд)..."
    for i in {1..12}; do
        if docker-compose exec -T erni-audio python health_check.py --json > /dev/null 2>&1; then
            log_success "Health check пройден"
            break
        fi
        
        if [[ $i -eq 12 ]]; then
            log_error "Health check не прошёл за 60 секунд"
            docker-compose logs erni-audio
            exit 1
        fi
        
        sleep 5
    done
}

# Показать информацию о развёртывании
show_deployment_info() {
    log_success "🎉 Production развёртывание завершено успешно!"
    echo
    log_info "Информация о сервисах:"
    docker-compose ps
    echo
    log_info "Доступные эндпоинты:"
    echo "  • Основной pipeline: http://localhost:8000"
    echo "  • Webhook сервер: http://localhost:8001"
    echo "  • Health check: http://localhost:8000/health"
    echo
    log_info "Полезные команды:"
    echo "  • Логи: docker-compose logs -f"
    echo "  • Статус: docker-compose ps"
    echo "  • Остановка: docker-compose down"
    echo "  • Перезапуск: docker-compose restart"
    echo
    log_info "Мониторинг:"
    echo "  • Логи: tail -f logs/*.log"
    echo "  • Метрики: ls -la logs/metrics/"
    echo "  • Health reports: ls -la logs/health_reports/"
}

# Основная функция
main() {
    echo "🐳 Erni Audio v2 - Production Deployment"
    echo "========================================"
    echo
    
    # Проверяем аргументы
    SKIP_TESTS=false
    SKIP_BUILD=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-tests)
                SKIP_TESTS=true
                shift
                ;;
            --skip-build)
                SKIP_BUILD=true
                shift
                ;;
            --help)
                echo "Использование: $0 [опции]"
                echo "Опции:"
                echo "  --skip-tests   Пропустить тесты"
                echo "  --skip-build   Пропустить сборку образа"
                echo "  --help         Показать эту справку"
                exit 0
                ;;
            *)
                log_error "Неизвестная опция: $1"
                exit 1
                ;;
        esac
    done
    
    # Выполняем развёртывание
    check_dependencies
    check_env_file
    create_directories
    
    if [[ "$SKIP_BUILD" != true ]]; then
        build_image
    fi
    
    if [[ "$SKIP_TESTS" != true ]]; then
        run_tests
    fi
    
    deploy
    health_check
    show_deployment_info
}

# Обработка сигналов
trap 'log_error "Развёртывание прервано"; exit 130' INT TERM

# Запуск
main "$@"
