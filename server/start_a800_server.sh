#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

export PYTHONUTF8=1
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export HF_DATASETS_OFFLINE="${HF_DATASETS_OFFLINE:-1}"
export TOKENIZERS_PARALLELISM="${TOKENIZERS_PARALLELISM:-false}"

HOST="${ROLEWEAVER_HOST:-0.0.0.0}"
PORT="${ROLEWEAVER_PORT:-8000}"
CONFIG_FILE="${ROLEWEAVER_CONFIG_FILE:-${ROOT_DIR}/server/roleweaver.a800.config.csv}"
VENV_DIR="${ROLEWEAVER_VENV_DIR:-${ROOT_DIR}/runtime/server_venv}"
PYTHON_BIN="${ROLEWEAVER_PYTHON:-${VENV_DIR}/bin/python}"

echo "[RoleWeaver A800] Root: ${ROOT_DIR}"
echo "[RoleWeaver A800] Config: ${CONFIG_FILE}"
echo "[RoleWeaver A800] Bind: http://${HOST}:${PORT}"

if [ ! -x "${PYTHON_BIN}" ]; then
  BASE_PYTHON="${ROLEWEAVER_BASE_PYTHON:-python3}"
  echo "[RoleWeaver A800] Creating venv at ${VENV_DIR}"
  "${BASE_PYTHON}" -m venv "${VENV_DIR}"
fi

if [ "${ROLEWEAVER_SKIP_INSTALL:-0}" != "1" ]; then
  echo "[RoleWeaver A800] Installing/updating server dependencies..."
  "${PYTHON_BIN}" -m pip install --upgrade pip
  "${PYTHON_BIN}" -m pip install -r "${ROOT_DIR}/server/requirements-a800.txt"
else
  echo "[RoleWeaver A800] Skipping dependency install because ROLEWEAVER_SKIP_INSTALL=1"
fi

echo "[RoleWeaver A800] Starting API service..."
echo "[RoleWeaver A800] Health: http://<server-ip>:${PORT}/health"
echo "[RoleWeaver A800] Web UI: http://<server-ip>:${PORT}/"
exec "${PYTHON_BIN}" "${ROOT_DIR}/API.py" --config "${CONFIG_FILE}" --host "${HOST}" --port "${PORT}"
