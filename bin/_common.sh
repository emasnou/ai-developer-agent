#!/usr/bin/env bash
# ==============================================================================
# Biblioteca comuna d'utilitats per als scripts operatius de bin/
# Resol automàticament l'arrel del projecte, l'entorn virtual Python i el format
# de missatges per terminal seguint les bones pràctiques de bash (strict mode).
# ==============================================================================

set -euo pipefail

# Resol l'arrel del repositori independentment del directori des d'on s'invoqui l'script
BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${BIN_DIR}/.." && pwd)"

# Colors ANSI per a sortida estructurada per terminal
readonly COLOR_RESET="\033[0m"
readonly COLOR_INFO="\033[1;34m"
readonly COLOR_OK="\033[1;32m"
readonly COLOR_WARN="\033[1;33m"
readonly COLOR_ERR="\033[1;31m"

log_info() {
    printf "${COLOR_INFO}ℹ️  %s${COLOR_RESET}\n" "$*"
}

log_ok() {
    printf "${COLOR_OK}✅ %s${COLOR_RESET}\n" "$*"
}

log_warn() {
    printf "${COLOR_WARN}⚠️  %s${COLOR_RESET}\n" "$*" >&2
}

log_error() {
    printf "${COLOR_ERR}❌ %s${COLOR_RESET}\n" "$*" >&2
}

# Detecta l'executable de Python prioritzant l'entorn virtual del projecte (.venv o venv)
resolve_python_bin() {
    if [[ -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
        printf "%s" "${PROJECT_ROOT}/.venv/bin/python"
    elif [[ -x "${PROJECT_ROOT}/venv/bin/python" ]]; then
        printf "%s" "${PROJECT_ROOT}/venv/bin/python"
    elif command -v python3 >/dev/null 2>&1; then
        command -v python3
    elif command -v python >/dev/null 2>&1; then
        command -v python
    else
        log_error "No s'ha trobat cap intèrpret de Python (python3/python) ni entorn virtual (.venv)."
        exit 1
    fi
}

# Detecta un binari instal·lat a l'entorn virtual (.venv/bin/<tool>) o al PATH del sistema
resolve_tool_bin() {
    local tool_name="$1"
    if [[ -x "${PROJECT_ROOT}/.venv/bin/${tool_name}" ]]; then
        printf "%s" "${PROJECT_ROOT}/.venv/bin/${tool_name}"
    elif [[ -x "${PROJECT_ROOT}/venv/bin/${tool_name}" ]]; then
        printf "%s" "${PROJECT_ROOT}/venv/bin/${tool_name}"
    elif command -v "${tool_name}" >/dev/null 2>&1; then
        command -v "${tool_name}"
    else
        printf ""
    fi
}

PYTHON_BIN="$(resolve_python_bin)"
export PYTHONPATH="${PROJECT_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

