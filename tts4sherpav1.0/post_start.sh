#!/usr/bin/env bash
set -euo pipefail

log() {
    echo -e "$(date '+%Y/%m/%d %H:%M:%S') $1"
}

log_info() { log "\033[1;34m [INFO] \033[0m $1"; }
log_success() { log "\033[1;32m [SUCCESS] \033[0m $1"; }
log_warning() { log "\033[1;33m [WARNING] \033[0m $1"; }
log_error() { log "\033[1;31m [ERROR] \033[0m $1"; }

log_success "TTS CPU版 服务启动成功"
log_info ""
log_info "📋 TTS CPU版 连接信息:"
log_info "主机: 10.172.0.20"
log_info "端口: 7899"
log_info ""
exit 0
