#!/usr/bin/env bash
# deploy.sh — Deploy FPR Census MCP Server to GCP VM
#
# Run from the project root on Mac:
#   ./deploy/deploy.sh
#
# Prerequisites:
#   - gcloud CLI authenticated
#   - CENSUS_API_KEY set
#
# Environment variables:
#   CENSUS_API_KEY — Census Bureau API key (required)

set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

VM_NAME="openclaw-gateway"
VM_ZONE="us-central1-c"
VM_USER="ricardorivera"
VM_PROJECT="luchoopenclaw"
REMOTE_DIR="/home/${VM_USER}/fpr-censo-mcp"
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

GCP_SSH="gcloud compute ssh ${VM_NAME} --zone=${VM_ZONE} --project=${VM_PROJECT}"
GCP_SCP="gcloud compute scp --zone=${VM_ZONE} --project=${VM_PROJECT}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ---------------------------------------------------------------------------
# Pre-checks
# ---------------------------------------------------------------------------

if [[ -z "${CENSUS_API_KEY:-}" ]]; then
    error "CENSUS_API_KEY not set. Export it before deploying:"
    echo "  export CENSUS_API_KEY=your-key"
    exit 1
fi

# ---------------------------------------------------------------------------
# Step 1: Create directories on VM
# ---------------------------------------------------------------------------

info "Step 1/7: Creating directories on VM..."
$GCP_SSH --command="mkdir -p ${REMOTE_DIR}/{src/tools,data,tests}"

# ---------------------------------------------------------------------------
# Step 2: Transfer code
# ---------------------------------------------------------------------------

info "Step 2/7: Transferring code..."
$GCP_SCP \
    "${LOCAL_DIR}/pyproject.toml" \
    "${VM_NAME}:${REMOTE_DIR}/"

$GCP_SCP \
    "${LOCAL_DIR}/src/__init__.py" \
    "${LOCAL_DIR}/src/__main__.py" \
    "${LOCAL_DIR}/src/server.py" \
    "${LOCAL_DIR}/src/census_client.py" \
    "${LOCAL_DIR}/src/geography.py" \
    "${LOCAL_DIR}/src/profiles.py" \
    "${LOCAL_DIR}/src/quality.py" \
    "${VM_NAME}:${REMOTE_DIR}/src/"

$GCP_SCP \
    "${LOCAL_DIR}/src/tools/__init__.py" \
    "${LOCAL_DIR}/src/tools/discovery.py" \
    "${LOCAL_DIR}/src/tools/query.py" \
    "${LOCAL_DIR}/src/tools/analysis.py" \
    "${VM_NAME}:${REMOTE_DIR}/src/tools/"

# ---------------------------------------------------------------------------
# Step 3: Transfer data files
# ---------------------------------------------------------------------------

info "Step 3/7: Transferring data files..."
$GCP_SCP \
    "${LOCAL_DIR}/data/municipios_pr.json" \
    "${LOCAL_DIR}/data/barrios_pr.json" \
    "${LOCAL_DIR}/data/variables_curadas.json" \
    "${VM_NAME}:${REMOTE_DIR}/data/"

# ---------------------------------------------------------------------------
# Step 4: Create venv and install dependencies
# ---------------------------------------------------------------------------

info "Step 4/7: Creating venv and installing dependencies..."
$GCP_SSH --command="
    cd ${REMOTE_DIR}
    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install .
"

# ---------------------------------------------------------------------------
# Step 5: Install systemd service
# ---------------------------------------------------------------------------

info "Step 5/7: Installing systemd service..."
$GCP_SSH --command="
    sudo tee /etc/systemd/system/fpr-censo-mcp.service > /dev/null << 'UNIT'
[Unit]
Description=FPR Census MCP Server
After=network.target

[Service]
Type=simple
User=${VM_USER}
WorkingDirectory=${REMOTE_DIR}
ExecStart=${REMOTE_DIR}/.venv/bin/python -m src.server --transport streamable-http --port 8001
Restart=always
RestartSec=5

Environment=CENSUS_API_KEY=${CENSUS_API_KEY}
Environment=CENSO_PORT=8001

[Install]
WantedBy=multi-user.target
UNIT
    sudo systemctl daemon-reload
    sudo systemctl enable fpr-censo-mcp
"

# ---------------------------------------------------------------------------
# Step 6: Create firewall rule
# ---------------------------------------------------------------------------

info "Step 6/7: Creating GCP firewall rule for port 8001..."
if gcloud compute firewall-rules describe allow-censo-mcp --project="${VM_PROJECT}" &>/dev/null; then
    warn "Firewall rule 'allow-censo-mcp' already exists, skipping"
else
    gcloud compute firewall-rules create allow-censo-mcp \
        --project="${VM_PROJECT}" \
        --direction=INGRESS \
        --priority=1000 \
        --network=default \
        --action=ALLOW \
        --rules=tcp:8001 \
        --source-ranges=0.0.0.0/0 \
        --description="Allow FPR Census MCP server on port 8001"
fi

# ---------------------------------------------------------------------------
# Step 7: Start service and verify
# ---------------------------------------------------------------------------

info "Step 7/7: Starting service..."
$GCP_SSH --command="
    sudo systemctl restart fpr-censo-mcp
    sleep 3
    sudo systemctl status fpr-censo-mcp --no-pager
"

VM_IP=$(gcloud compute instances describe "${VM_NAME}" \
    --zone="${VM_ZONE}" \
    --project="${VM_PROJECT}" \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo ""
info "VM external IP: ${VM_IP}"

sleep 2
if curl -sf "http://${VM_IP}:8001/health" | python3 -m json.tool; then
    echo ""
    info "Health check passed!"
else
    warn "Health check failed — server may still be starting"
    warn "Check logs: ${GCP_SSH} --command=\"sudo journalctl -u fpr-censo-mcp -f --no-pager -n 50\""
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "============================================"
info "Deploy complete!"
echo "============================================"
echo ""
echo "Endpoints:"
echo "  Health:  http://${VM_IP}:8001/health"
echo "  MCP:     http://${VM_IP}:8001/mcp"
echo ""
echo "MCP config for Claude Desktop / .mcp.json:"
echo "  {"
echo "    \"mcpServers\": {"
echo "      \"fpr-censo\": {"
echo "        \"url\": \"http://${VM_IP}:8001/mcp\""
echo "      }"
echo "    }"
echo "  }"
echo ""
echo "Useful commands:"
echo "  Logs:    ${GCP_SSH} --command=\"sudo journalctl -u fpr-censo-mcp -f --no-pager -n 50\""
echo "  Restart: ${GCP_SSH} --command=\"sudo systemctl restart fpr-censo-mcp\""
echo "  Status:  ${GCP_SSH} --command=\"sudo systemctl status fpr-censo-mcp\""
