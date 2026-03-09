# Contoso Super Agent — AKS POC

A Proof of Concept demonstrating how a **Microsoft M365 Custom Engine Agent** (CEA) communicates with an enterprise orchestrator agent hosted on **Azure Kubernetes Service (AKS)**.

Users interact through **M365 Copilot / Microsoft Teams**. Every message is forwarded to a FastAPI service running on AKS, which calls Azure OpenAI and returns the response directly in chat.

---

## Table of Contents

1. [Overview](#overview)
2. [Problem Statement](#problem-statement)
3. [Solution](#solution)
4. [Requirements](#requirements)
5. [Architecture](#architecture)
6. [Repository Structure](#repository-structure)
7. [Prerequisites](#prerequisites)
8. [Component 1 — AKS API Service](#component-1--aks-api-service)
   - [Local Development](#local-development)
   - [Docker Build](#docker-build)
   - [Install Azure CLI](#install-azure-cli)
   - [Deploy to AKS](#deploy-to-aks)
     - [Option A — Azure Portal (GUI)](#option-a--azure-portal-gui)
     - [Option B — Azure CLI](#option-b--azure-cli)
9. [Testing the AKS API](#testing-the-aks-api)
   - [API Reference](#api-reference)
   - [Test 1 — Health Check](#test-1--health-check)
   - [Test 2 — Prompt](#test-2--prompt)
   - [Test 3 — Missing Configuration](#test-3--missing-configuration)
   - [Test 4 — Docker Container](#test-4--docker-container)
   - [Test 5 — Deployed on AKS](#test-5--deployed-on-aks)
   - [Test 6 — Interactive Swagger UI](#test-6--interactive-swagger-ui)
   - [Troubleshooting — Port Already in Use](#troubleshooting--port-already-in-use)
10. [Component 2 — Custom Engine Agent](#component-2--custom-engine-agent)
    - [Scaffold & Install](#scaffold--install)
    - [Key Source Files](#key-source-files)
    - [Environment Configuration](#environment-configuration)
    - [Local Debug with M365 Agents Toolkit](#local-debug-with-m365-agents-toolkit)
    - [Deploy to Azure](#deploy-to-azure)
11. [End-to-End Flow](#end-to-end-flow)
12. [Testing Guide](#testing-guide)
13. [Configuration Reference](#configuration-reference)
14. [Security Notes](#security-notes)
15. [Changelog](#changelog)

---

## Overview

**Contoso Customer** has built an enterprise orchestrator agent called **Contoso Super Agent** that acts as a single conversational entry point for all employee queries. Contoso Super Agent routes requests to specialized downstream agents for various use cases across the organization.

The orchestrator is designed to run on **Azure Kubernetes Service (AKS)** for enterprise-grade scalability, resilience, and operational control. The front-end surface for employees is **Microsoft 365 Copilot** and **Microsoft Teams**.

This POC validates the end-to-end communication pattern between:
- An **M365 Custom Engine Agent (CEA)** acting as the Teams/Copilot front end
- A **FastAPI backend** deployed on AKS acting as the Contoso Super Agent proxy
- **Azure OpenAI** as the language model

---

## Problem Statement

Contoso Customer wants to provide employees with a unified AI assistant accessible directly from Microsoft Teams and M365 Copilot. The enterprise orchestrator (Contoso Super Agent) must:

1. Be accessible from within Teams / M365 Copilot — the primary employee productivity surface
2. Run on AKS for enterprise control, scalability, and integration with internal systems
3. Support a pattern where the M365 agent layer is kept thin and delegates all intelligence to the AKS backend

The key question this POC answers: **How does an M365 Copilot Custom Engine Agent communicate with a backend service running on AKS?**

---

## Solution

```
M365 Copilot / Teams  →  Custom Engine Agent (CEA)  →  AKS API  →  Azure OpenAI
```

The solution uses two components working together:

| Component | Technology | Role |
|-----------|------------|------|
| **Custom Engine Agent** | Node.js, TypeScript, M365 Agents SDK | Receives messages from Teams/Copilot, forwards them to AKS |
| **AKS API Service** | Python, FastAPI, Docker, Kubernetes | Receives prompts, calls Azure OpenAI, returns responses |

**Key design decisions:**
- The CEA is intentionally thin — it delegates all AI logic to the AKS backend
- Credentials (Azure OpenAI key) are injected into the AKS pod via Kubernetes ConfigMap and Secret — nothing is hard-coded in the image
- The AKS endpoint URL is read from an environment variable (`AKS_ENDPOINT_URL`) — not hard-coded in source
- This pattern scales: the AKS backend can be replaced with or extended to call any enterprise orchestrator

---

## Requirements

### Functional Requirements

| # | Requirement |
|---|-------------|
| FR-1 | Employees can chat with Contoso Super Agent from Microsoft Teams |
| FR-2 | Employees can access the agent from M365 Copilot chat sidebar |
| FR-3 | Every user message is forwarded to the AKS backend and the response is shown in chat |
| FR-4 | The agent must greet the user when they start a conversation |
| FR-5 | The AKS backend must expose a health check endpoint for Kubernetes probes |

### Non-Functional Requirements

| # | Requirement |
|---|-------------|
| NFR-1 | The AKS backend must be containerized and deployable via Kubernetes manifests |
| NFR-2 | Credentials must not be hard-coded — injected via environment variables only |
| NFR-3 | The cluster must be stoppable when not in use to minimize cost |
| NFR-4 | The solution must work with a single AKS node (POC scale) |

### Technical Prerequisites

| Requirement | Details |
|-------------|---------|
| Azure Subscription | Permissions to create Resource Groups, AKS, ACR, App Service, Bot registration |
| Azure OpenAI resource | A deployed model (e.g., `gpt-4o`) with API key and endpoint |
| M365 Account | Teams access with app sideloading enabled; M365 Copilot license |
| Local tools | Node.js 20+, Python 3.11+, Docker Desktop, Azure CLI, kubectl, VS Code |

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│            User  (Teams / M365 Copilot)                  │
└─────────────────────────┬────────────────────────────────┘
                          │  chat message
                          ▼
┌──────────────────────────────────────────────────────────┐
│           Bot Framework Service  (Azure relay)           │
└─────────────────────────┬────────────────────────────────┘
                          │  POST /api/messages
                          ▼
┌──────────────────────────────────────────────────────────┐
│   Custom Engine Agent  (agent_m365_sdk/helloaiworld/)    │
│  Node.js · TypeScript · @microsoft/agents-hosting-express│
│                                                          │
│   onActivity(Message) → fetch → POST /api/prompt         │
└─────────────────────────┬────────────────────────────────┘
                          │  POST /api/prompt
                          │  http://<AKS-PUBLIC-IP>/api/prompt
                          ▼
┌──────────────────────────────────────────────────────────┐
│         AKS API Service  — PUBLIC ENDPOINT               │
│         Kubernetes LoadBalancer · http://<PUBLIC-IP>     │
│                                                          │
│         Python · FastAPI (running inside the pod)        │
│                                                          │
│   POST /api/prompt → calls Azure OpenAI → response       │
└─────────────────────────┬────────────────────────────────┘
                          │  chat completions API
                          ▼
┌──────────────────────────────────────────────────────────┐
│         Azure OpenAI Service                             │
│         https://<resource>.cognitiveservices.azure.com   │
│         Credentials injected via K8s ConfigMap + Secret  │
└──────────────────────────────────────────────────────────┘
```

### Two deployment contexts

| Context | How the API is accessed | When to use `uvicorn` |
|---------|------------------------|----------------------|
| **Local development** | `http://localhost:8000` | Yes — start manually with `uvicorn main:app --reload --port 8000 --env-file .env` |
| **AKS (deployed)** | `http://<PUBLIC-IP>` | No — Kubernetes starts it inside the pod via the Dockerfile `CMD`. Use the public IP. |

> After deploying to AKS, **you never run `uvicorn` manually**. The LoadBalancer public IP is the entry point.

---

## Repository Structure

```
contoso-super-agent-aks-poc/
├── README.md                        ← this file
├── requirements.txt
├── .gitignore
│
├── agent_m365_sdk/                  ← ACTIVE: M365 Custom Engine Agent
│   └── helloaiworld/                ← agent project root (open this in VS Code)
│       ├── package.json
│       ├── tsconfig.json
│       ├── m365agents.yml           ← M365 Agents Toolkit provision/deploy config
│       ├── m365agents.local.yml     ← M365 Agents Toolkit local debug config
│       ├── .localConfigs            ← LOCAL ONLY, gitignored — auto-filled by toolkit
│       ├── src/
│       │   ├── index.ts             ← entry point — starts the Express server
│       │   ├── agent.ts             ← message handler — calls AKS API via AKS_ENDPOINT_URL
│       │   └── config.ts            ← reads Azure OpenAI env vars
│       ├── appPackage/
│       │   ├── manifest.json        ← Teams/M365 Copilot app manifest
│       │   ├── color.png
│       │   └── outline.png
│       ├── env/
│       │   ├── .env.local           ← AUTO-GENERATED by toolkit (gitignored)
│       │   └── .env.dev             ← dev/staging values
│       └── infra/
│           ├── azure.bicep          ← App Service + Bot registration
│           └── azure.parameters.json
│
├── agent/                           ← UNUSED scaffold (kept for reference)
│
└── aks-api/                         ← AKS-hosted REST API
    ├── main.py                      ← FastAPI app
    ├── models.py                    ← Pydantic request/response models
    ├── requirements.txt             ← Python dependencies
    ├── Dockerfile
    ├── .env.example                 ← template — copy to .env and fill in values
    ├── .env                         ← LOCAL ONLY, gitignored
    └── k8s/
        ├── deployment.yaml          ← Kubernetes Deployment (mounts ConfigMap + Secret)
        ├── service.yaml             ← Kubernetes Service (LoadBalancer)
        ├── configmap.yaml           ← Non-sensitive env vars (endpoint URL, model name)
        └── secret.yaml              ← Sensitive env vars (API key) — fill before applying, gitignored
```

---

## Prerequisites

### Local Tools

| Tool | Min Version | Install |
|------|-------------|---------|
| Node.js | 20 | [nodejs.org](https://nodejs.org) |
| Python | 3.11 | [python.org](https://python.org) |
| Docker Desktop | Latest | `winget install Docker.DockerDesktop` |
| Azure CLI | Latest | `winget install Microsoft.AzureCLI` |
| kubectl | Latest | `az aks install-cli` (run after Azure CLI is installed) |
| VS Code | Latest | [code.visualstudio.com](https://code.visualstudio.com) |

### VS Code Extensions

| Extension | Purpose |
|-----------|---------|
| M365 Agents Toolkit (Microsoft) | Bot provisioning, local debug, Teams deployment |
| Python (Microsoft) | AKS API development |

### Azure Resources

| Resource | Notes |
|----------|-------|
| Azure Subscription | Permissions: AKS, ACR, App Service, Bot |
| Entra ID App Registration | Auto-created by M365 Agents Toolkit |
| Azure Container Registry (ACR) | For Docker image storage |
| AKS Cluster | Single node pool (POC scale) |
| Azure OpenAI resource | Deployed model (e.g., `gpt-4o`) |
| Azure Bot Service | Auto-created by M365 Agents Toolkit |

### M365 Account

- Teams access with app sideloading enabled
- Microsoft 365 Copilot license (for Copilot chat integration)

---

## Component 1 — AKS API Service

The API is a **FastAPI** service that:
- Accepts `POST /api/prompt` with `{"prompt": "..."}` in the request body
- Forwards the prompt to **Azure OpenAI** using the `openai` Python SDK (`AzureOpenAI` client)
- Returns the model's response to the caller
- Exposes `GET /health` for Kubernetes readiness/liveness probes
- Runs inside a Docker container on AKS, exposed publicly via a Kubernetes LoadBalancer service
- Azure credentials are injected at runtime via Kubernetes ConfigMap and Secret — nothing is hard-coded in the image

### Local Development

#### Step 1 — Configure Azure AI credentials

```bash
cd aks-api
cp .env.example .env
```

Edit `aks-api/.env`:

```env
AZURE_AI_ENDPOINT_URL=https://<your-resource-name>.cognitiveservices.azure.com/
AZURE_AI_API_KEY=<your-api-key>
AZURE_AI_MODEL=gpt-4o
AZURE_AI_API_VERSION=2024-05-01-preview
AZURE_AI_SYSTEM_PROMPT=You are a helpful assistant. Answer the user's question clearly and concisely.
```

> **Important:** `AZURE_AI_ENDPOINT_URL` must be the **base URL only** — no path, no deployment name, no `?api-version`. The SDK constructs the full path automatically.

**Where to find these values:**
1. Go to [portal.azure.com](https://portal.azure.com) → your Azure OpenAI resource
2. Click **"Keys and Endpoint"** in the left nav
3. Copy the **Endpoint** → `AZURE_AI_ENDPOINT_URL`
4. Copy **KEY 1** or **KEY 2** → `AZURE_AI_API_KEY`
5. Go to [ai.azure.com](https://ai.azure.com) → your project → **Models + endpoints** → copy the **Deployment name** → `AZURE_AI_MODEL`

#### Step 2 — Install and run

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/Scripts/activate       # Windows (Git Bash)
# or: .venv\Scripts\activate        # Windows (PowerShell)

# Install dependencies
pip install -r requirements.txt

# Run with .env loaded
uvicorn main:app --reload --port 8000 --env-file .env
```

Once running:
- API base URL: `http://localhost:8000`
- Interactive docs (Swagger): `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

Test the prompt endpoint:

```bash
curl -X POST http://localhost:8000/api/prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt": "hello"}'
```

---

### Docker Build

#### Prerequisites — Install Docker Desktop

Docker Desktop must be installed and running before any `docker` command will work.

**Install via winget (recommended):**
```powershell
winget install Docker.DockerDesktop
```

**Or download manually:** [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)

After installation:
1. Restart your machine
2. Launch **Docker Desktop** from the Start menu
3. Wait until the system tray icon shows **"Docker Desktop is running"**
4. Verify:

```powershell
docker --version
docker run hello-world
```

#### Build and Run

```bash
cd aks-api

# Build image locally
docker build -t contoso-agent-api:latest .

# Run container — pass the .env file so the container gets the Azure credentials
docker run -p 8000:8000 --env-file .env contoso-agent-api:latest

# Test
curl http://localhost:8000/health
```

---

### Install Azure CLI

Azure CLI is required for pushing images to ACR and connecting kubectl to AKS.

**Option 1 — winget (recommended):**
```powershell
winget install Microsoft.AzureCLI --accept-source-agreements --accept-package-agreements
```

**Option 2 — MSI installer:**
1. Go to [aka.ms/installazurecliwindows](https://aka.ms/installazurecliwindows)
2. Download and run the `.msi` installer
3. Follow the prompts and restart your terminal

**Verify:**
```powershell
az --version
# azure-cli  2.x.x
```

**Install kubectl:**
```powershell
az aks install-cli
```

---

### Deploy to AKS

Two approaches are documented — **Azure Portal (GUI)** and **Azure CLI**. Both produce the same result.

> **Prerequisites for both approaches:**
> - Azure subscription with permissions to create Resource Groups, ACR, and AKS
> - Azure CLI installed
> - kubectl installed: `az aks install-cli`
> - Docker Desktop installed and running

---

#### Option A — Azure Portal (GUI)

##### Step 1 — Sign in to Azure Portal

Go to [portal.azure.com](https://portal.azure.com) and sign in with your Azure account.

---

##### Step 2 — Create a Resource Group

1. Search for **"Resource groups"** and click it
2. Click **"+ Create"**
3. Fill in:
   - **Subscription:** select your subscription
   - **Resource group:** `rg-contoso-agent-poc` (or any name you prefer)
   - **Region:** `East US` (or your preferred region)
4. Click **"Review + create"** → **"Create"**

---

##### Step 3 — Create an Azure Container Registry (ACR)

1. Search for **"Container registries"** and click it
2. Click **"+ Create"**
3. Fill in:
   - **Subscription:** select your subscription
   - **Resource group:** `rg-contoso-agent-poc`
   - **Registry name:** `<your-acr-name>` (globally unique, lowercase, alphanumeric only)
   - **Location:** `East US`
   - **Pricing plan:** `Basic`
4. Click **"Review + create"** → **"Create"**
5. Once deployed, go to the registry → **Settings → Access keys** → enable **Admin user**

> Note your **Login server** (`<your-acr-name>.azurecr.io`), **Username**, and **Password** — you will need them to push and pull images.

---

##### Step 4 — Build and Push the Docker Image to ACR

```powershell
# Login to Azure
az login

# Login to ACR
az acr login --name <your-acr-name>

# Build the image
docker build -t contoso-agent-api:latest ./aks-api

# Tag the image for ACR
docker tag contoso-agent-api:latest <your-acr-name>.azurecr.io/contoso-agent-api:latest

# Push to ACR
docker push <your-acr-name>.azurecr.io/contoso-agent-api:latest
```

Verify the image was pushed: go to the container registry → **Services → Repositories**.

---

##### Step 5 — Create an AKS Cluster

1. Search for **"Kubernetes services"** and click it
2. Click **"+ Create"** → **"Create a Kubernetes cluster"**
3. Fill in the **Basics** tab:
   - **Subscription:** select your subscription
   - **Resource group:** `rg-contoso-agent-poc`
   - **Cluster preset configuration:** `Dev/Test`
   - **Kubernetes cluster name:** `<your-cluster-name>`
   - **Region:** `East US` (same as ACR)
   - **Kubernetes version:** leave as default
   - **Authentication method:** `Local accounts with Kubernetes RBAC`
4. Click **"Next: Node pools"**
   - Leave the default node pool as-is (reduce to 1 node if needed for cost)
5. Click **"Next: Networking"** — leave defaults
6. Click **"Next: Integrations"**
   - **Container registry:** select your ACR from the dropdown — this grants AKS pull access automatically
7. Click **"Review + create"** → **"Create"**

> Cluster creation takes approximately **5–10 minutes**.

---

##### Step 6 — Connect kubectl to the Cluster

```powershell
az aks get-credentials --resource-group rg-contoso-agent-poc --name <your-cluster-name>
```

Expected output:
```
Merged "<your-cluster-name>" as current context in C:\Users\<username>\.kube\config
```

Verify the connection:

```powershell
kubectl get nodes
# NAME                                  STATUS   ROLES    AGE    VERSION
# aks-agentpool-xxxxxxxxx-vmssxxxxxx    Ready    <none>   5m     v1.33.x
```

---

##### Step 7 — Update the Deployment Manifest

Edit `aks-api/k8s/deployment.yaml` to reference your ACR image:

```yaml
image: <your-acr-name>.azurecr.io/contoso-agent-api:latest
```

---

##### Step 8 — Configure Azure AI credentials for Kubernetes

**8a — Edit `aks-api/k8s/configmap.yaml`** with your non-sensitive values:

```yaml
data:
  AZURE_AI_ENDPOINT_URL: "https://<your-resource-name>.cognitiveservices.azure.com/"
  AZURE_AI_MODEL: "gpt-4o"
  AZURE_AI_SYSTEM_PROMPT: "You are a helpful assistant."
```

**8b — Edit `aks-api/k8s/secret.yaml`** with your API key:

```yaml
stringData:
  AZURE_AI_API_KEY: "<your-azure-ai-api-key>"
```

> `secret.yaml` is gitignored — never commit it. Apply it directly from your local machine.

**8c — Apply the ConfigMap and Secret:**

```powershell
kubectl apply -f aks-api/k8s/configmap.yaml
kubectl apply -f aks-api/k8s/secret.yaml
```

Verify:

```powershell
kubectl get configmap contoso-agent-api-config
kubectl get secret contoso-agent-api-secrets
```

---

##### Step 9 — Deploy to AKS

```powershell
kubectl apply -f aks-api/k8s/deployment.yaml
kubectl apply -f aks-api/k8s/service.yaml
```

Check the deployment status:

```powershell
# Watch pods come up — press Ctrl+C once STATUS shows "Running"
kubectl get pods --watch

# Then watch the service for a public IP — press Ctrl+C once EXTERNAL-IP shows a real IP
kubectl get service contoso-agent-api-svc --watch
```

> `--watch` streams live updates and **blocks the terminal**. Stop each command with **Ctrl+C** before running the next one.

Wait until `EXTERNAL-IP` shows a real IP address (not `<pending>`):

```
NAME                       TYPE           CLUSTER-IP     EXTERNAL-IP    PORT(S)        AGE
contoso-agent-api-svc      LoadBalancer   10.0.x.x       <EXTERNAL-IP>  80:xxxxx/TCP   3m
```

---

##### Step 10 — Verify the Deployment

```powershell
# Health check
Invoke-RestMethod -Uri http://<EXTERNAL-IP>/health

# Prompt test
Invoke-RestMethod -Method Post -Uri http://<EXTERNAL-IP>/api/prompt `
  -ContentType "application/json" -Body '{"prompt": "status"}'
```

You can also check in the Azure Portal:
1. Go to your AKS cluster
2. Click **Kubernetes resources → Workloads** to see the deployment
3. Click **Kubernetes resources → Services and ingresses** to see the external IP

---

##### Step 11 — Update the Agent

Set `AKS_ENDPOINT_URL` in the agent's environment configuration to point to your AKS public IP:

```env
AKS_ENDPOINT_URL=http://<EXTERNAL-IP>/api/prompt
```

> The agent reads this from the `AKS_ENDPOINT_URL` environment variable. Set it in `.localConfigs` for local debug, or in the App Service environment variables for cloud deployment.

---

##### Step 12 — Stopping the Cluster When Not in Use

Running AKS nodes and the control plane incur ongoing costs even when idle. The table below explains the options:

| Option | Stops VMs | Stops Control Plane | Preserves All K8s State | Recommended |
|---|---|---|---|---|
| `az aks stop` | Yes | **Yes** | Yes | **Yes** |
| `az aks scale --node-count 0` | Yes | No (still billed) | Yes | No |
| Delete service + delete cluster | Yes | Yes | **No** | No |

#### Stop — single command, zero cost, nothing deleted

```powershell
az aks stop --resource-group rg-contoso-agent-poc --name <your-cluster-name>
```

All Kubernetes state is fully preserved: deployments, services, ConfigMaps, Secrets, ACR integration, and kubeconfig. Only ACR storage continues at ~$0.17/day.

#### Resume for a demo

```powershell
# Start the cluster (~3-5 min for nodes to become Ready)
az aks start --resource-group rg-contoso-agent-poc --name <your-cluster-name>

# Verify nodes are up
kubectl get nodes

# Get the public IP (may have changed after stop/start)
kubectl get service contoso-agent-api-svc
```

> **Important:** The LoadBalancer public IP **may change** after a stop/start cycle. Check the `EXTERNAL-IP` column and update `AKS_ENDPOINT_URL` in the agent if it has changed.

---

#### Option B — Azure CLI

```bash
# 1. Login
az login
az account set --subscription "<SUBSCRIPTION_ID>"

# 2. Create resource group
az group create \
  --name rg-contoso-agent-poc \
  --location eastus

# 3. Create Azure Container Registry
az acr create \
  --resource-group rg-contoso-agent-poc \
  --name <your-acr-name> \
  --sku Basic \
  --admin-enabled true

# 4. Build and push image to ACR (no local Docker daemon needed)
az acr build \
  --registry <your-acr-name> \
  --image contoso-agent-api:latest \
  ./aks-api

# 5. Create AKS cluster (1 node for POC)
az aks create \
  --resource-group rg-contoso-agent-poc \
  --name <your-cluster-name> \
  --node-count 1 \
  --node-vm-size Standard_B2s \
  --attach-acr <your-acr-name> \
  --generate-ssh-keys

# 6. Get credentials
az aks get-credentials \
  --resource-group rg-contoso-agent-poc \
  --name <your-cluster-name>

# 7. Update deployment.yaml to reference your ACR image, then apply
kubectl apply -f aks-api/k8s/configmap.yaml
kubectl apply -f aks-api/k8s/secret.yaml

# 8. Deploy the API
kubectl apply -f aks-api/k8s/deployment.yaml
kubectl apply -f aks-api/k8s/service.yaml

# 9. Wait for the LoadBalancer external IP (takes ~2 min)
kubectl get service contoso-agent-api-svc --watch
```

After deployment, verify:

```bash
curl -X POST http://<EXTERNAL-IP>/api/prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt": "status"}'
```

---

## Testing the AKS API

This section covers all test cases for `aks-api/`. Each test includes both **bash/curl** and **PowerShell** commands.

> - **Local:** Start the API with `uvicorn main:app --reload --port 8000 --env-file .env`, use `http://localhost:8000`.
> - **AKS (deployed):** Use `http://<EXTERNAL-IP>` — no `uvicorn` needed.

---

### API Reference

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness/readiness probe |
| `POST` | `/api/prompt` | Submit a user prompt, receive a response |
| `GET` | `/docs` | Interactive Swagger UI (local only) |

**Request body for `POST /api/prompt`:**

```json
{
  "prompt": "string",
  "context": {}
}
```

**Response body:**

```json
{
  "response": "string",
  "source": "string",
  "prompt_received": "string"
}
```

---

### Test 1 — Health Check

**Bash:**
```bash
curl http://localhost:8000/health
```

**PowerShell:**
```powershell
Invoke-RestMethod -Uri http://localhost:8000/health
```

**Expected response (configured):**
```json
{
  "status": "healthy",
  "service": "contoso-agent-api",
  "version": "0.3.0",
  "ai_backend": "azure-openai"
}
```

**Expected response (not configured — missing env vars):**
```json
{
  "status": "healthy",
  "service": "contoso-agent-api",
  "version": "0.3.0",
  "ai_backend": "not-configured"
}
```

---

### Test 2 — Prompt

**Bash:**
```bash
curl -X POST http://localhost:8000/api/prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is the capital of France?"}'
```

**PowerShell:**
```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/prompt `
  -ContentType "application/json" `
  -Body '{"prompt": "What is the capital of France?"}'
```

**Expected response:**
```json
{
  "response": "The capital of France is Paris.",
  "source": "azure-openai/gpt-4o",
  "prompt_received": "What is the capital of France?"
}
```

---

### Test 3 — Missing Configuration

If `AZURE_AI_ENDPOINT_URL` or `AZURE_AI_API_KEY` are not set, the API returns `503`:

```json
{
  "detail": "Azure OpenAI is not configured. Set AZURE_AI_ENDPOINT_URL and AZURE_AI_API_KEY environment variables."
}
```

**Fix:** Ensure `aks-api/.env` exists and both variables are populated, then restart uvicorn.

---

### Test 4 — Docker Container

```bash
docker build -t contoso-agent-api:latest ./aks-api
docker run -d -p 8000:8000 --name contoso-agent-api --env-file aks-api/.env contoso-agent-api:latest

curl http://localhost:8000/health

curl -X POST http://localhost:8000/api/prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt": "status"}'

docker stop contoso-agent-api && docker rm contoso-agent-api
```

**PowerShell:**
```powershell
docker build -t contoso-agent-api:latest ./aks-api
docker run -d -p 8000:8000 --name contoso-agent-api --env-file aks-api/.env contoso-agent-api:latest

Invoke-RestMethod -Uri http://localhost:8000/health
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/prompt `
  -ContentType "application/json" -Body '{"prompt": "status"}'

docker stop contoso-agent-api; docker rm contoso-agent-api
```

---

### Test 5 — Deployed on AKS

```bash
kubectl get service contoso-agent-api-svc

curl http://<EXTERNAL-IP>/health

curl -X POST http://<EXTERNAL-IP>/api/prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt": "status"}'
```

Check pod health:

```bash
kubectl get pods -l app=contoso-agent-api
kubectl logs -l app=contoso-agent-api --tail=50
```

---

### Test 6 — Interactive Swagger UI

1. Start the API: `uvicorn main:app --reload --port 8000 --env-file .env`
2. Open `http://localhost:8000/docs` in a browser
3. Expand `POST /api/prompt` → click **Try it out** → enter a prompt → click **Execute**

---

### Troubleshooting — Port Already in Use

If uvicorn fails with `[WinError 10013]`, port 8000 is occupied.

```powershell
# Find the process
netstat -ano | findstr ":8000"

# Identify it
Get-Process -Id <PID> | Select-Object Id, ProcessName, Path

# Kill it
Stop-Process -Id <PID> -Force

# Confirm port is free
netstat -ano | findstr ":8000"
```

Then retry: `uvicorn main:app --reload --port 8000 --env-file .env`

---

## Component 2 — Custom Engine Agent

The active agent is **`helloaiworld`** located in `agent_m365_sdk/helloaiworld/`. Built using the **M365 Agents SDK** (`@microsoft/agents-hosting-express`), managed by the **M365 Agents Toolkit** VS Code extension.

> **Note:** The `agent/` folder is an unused scaffold and can be ignored.

### SDK and Toolkit

| | Detail |
|---|---|
| **Agent SDK** | `@microsoft/agents-hosting-express` + `@microsoft/agents-hosting` |
| **Toolkit** | M365 Agents Toolkit (`m365agents.local.yml`, `m365agents.yml`) |
| **Language** | TypeScript / Node.js |
| **Port** | 3978 |
| **Bot ID** | Auto-generated by toolkit (stored in `env/.env.local`, gitignored) |
| **Teams App ID** | Auto-generated by toolkit (stored in `env/.env.local`, gitignored) |

### Scaffold & Install

```bash
cd agent_m365_sdk/helloaiworld
npm install
```

### Key Source Files

**`src/index.ts`** — Entry point:

```typescript
import { startServer } from "@microsoft/agents-hosting-express";
import { agentApp } from "./agent";
startServer(agentApp);
```

**`src/agent.ts`** — Message handler, calls AKS API:

```typescript
import { ActivityTypes } from "@microsoft/agents-activity";
import { AgentApplication, MemoryStorage, TurnContext } from "@microsoft/agents-hosting";

const AKS_ENDPOINT_URL = process.env.AKS_ENDPOINT_URL || "http://localhost:8000/api/prompt";

const storage = new MemoryStorage();
export const agentApp = new AgentApplication({ storage });

// Greet user when they join the conversation
agentApp.onConversationUpdate("membersAdded", async (context: TurnContext) => {
  await context.sendActivity(`Hi there! I'm Contoso Super Agent, ready to help.`);
});

// Forward every message to the AKS API and return the response
agentApp.onActivity(ActivityTypes.Message, async (context: TurnContext) => {
  const response = await fetch(AKS_ENDPOINT_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt: context.activity.text }),
  });
  const data = await response.json();
  const formatted = `**Response from Contoso Super Agent AKS API**\n\n${data.response}`;
  await context.sendActivity(formatted);
});
```

> The AKS endpoint is read from `AKS_ENDPOINT_URL` environment variable (falls back to `localhost:8000` for local development).

**`src/config.ts`** — Reads Azure OpenAI env vars:

```typescript
const config = {
  azureOpenAIKey: process.env.AZURE_OPENAI_API_KEY,
  azureOpenAIEndpoint: process.env.AZURE_OPENAI_ENDPOINT,
  azureOpenAIDeploymentName: process.env.AZURE_OPENAI_DEPLOYMENT_NAME,
};
export default config;
```

### Environment Configuration

The toolkit auto-generates `.localConfigs` during provision (F5). It contains:

```env
clientId=<bot-entra-app-client-id>
clientSecret=<bot-entra-app-client-secret>
tenantId=<your-tenant-id>
AKS_ENDPOINT_URL=http://<EXTERNAL-IP>/api/prompt
```

> `.localConfigs` is gitignored and auto-populated by M365 Agents Toolkit. Add `AKS_ENDPOINT_URL` manually after obtaining your AKS public IP.

Provisioned values are stored in `env/.env.local` (gitignored):

```env
BOT_ID=<auto-generated>
TEAMS_APP_ID=<auto-generated>
BOT_DOMAIN=<your-dev-tunnel>.inc1.devtunnels.ms
BOT_ENDPOINT=https://<your-dev-tunnel>.inc1.devtunnels.ms
TEAMS_APP_TENANT_ID=<your-tenant-id>
```

> `env/.env.local` is gitignored — it contains auto-generated IDs and your dev tunnel URL. Re-provision with the toolkit to regenerate it.

### Local Debug with M365 Agents Toolkit

**Prerequisites:**
- VS Code with **M365 Agents Toolkit** extension installed
- Sign in to M365 account in the Toolkit sidebar

**Run locally:**

1. Open VS Code in `agent_m365_sdk/helloaiworld/`
2. Press **F5** — the toolkit will:
   - Create Entra ID App Registration (first run only)
   - Start a Dev Tunnel at `<your-tunnel>.inc1.devtunnels.ms`
   - Register the Bot Framework channel with the tunnel URL
   - Start the agent on port 3978
   - Open Teams or M365 Agents Playground in the browser

**Or run directly from terminal:**

```bash
cd agent_m365_sdk/helloaiworld
npm run dev:teamsfx
```

### Deploy to Azure

```bash
cd agent_m365_sdk/helloaiworld

# Provision Azure resources (App Service + Bot registration)
npx teamsapp provision --env dev

# Build and deploy bot code to App Service
npx teamsapp deploy --env dev

# Publish app to Teams/M365 catalog
npx teamsapp publish --env dev
```

---

## End-to-End Flow

```
User types message in Teams/Copilot
      │
      ▼
Bot Framework Service routes to agent (POST /api/messages)
      │
      ▼
agent_m365_sdk/helloaiworld/src/agent.ts  →  onActivity(Message) fires
      │
      │  fetch(AKS_ENDPOINT_URL)   ← reads from env var
      │  {"prompt": "user message"}
      ▼
AKS LoadBalancer  (public IP, port 80)
      │
      ▼
FastAPI pod running in Kubernetes
  aks-api/main.py → AzureOpenAI client
      │
      │  chat.completions.create(model, messages)
      ▼
Azure OpenAI Service
  https://<resource>.cognitiveservices.azure.com
      │
      │  {"choices": [{"message": {"content": "..."}}]}
      ▼
FastAPI returns PromptResponse to agent
      │
      ▼
Agent sends formatted reply to user in Teams/Copilot
```

---

## Testing Guide

| # | What to Test | Command / Action |
|---|--------------|-----------------|
| 1 | AKS API — local | `uvicorn main:app --reload --port 8000 --env-file .env` → test via `/docs` or curl |
| 2 | AKS API — health | `curl http://localhost:8000/health` |
| 3 | AKS API — on K8s | `curl -X POST http://<EXTERNAL-IP>/api/prompt` |
| 4 | Agent — standalone | `npm run dev:teamsfx` in `agent_m365_sdk/helloaiworld/` |
| 5 | Agent — M365 Playground | F5 → toolkit starts dev tunnel + opens M365 Agents Playground |
| 6 | Agent — Teams E2E | F5 → Teams opens with bot installed via dev tunnel |
| 7 | M365 Copilot | Open copilot.microsoft.com → find agent in side panel |

---

## Configuration Reference

### AKS API (`aks-api/.env`)

| Variable | Description |
|----------|-------------|
| `AZURE_AI_ENDPOINT_URL` | Azure OpenAI base URL — e.g. `https://<resource>.cognitiveservices.azure.com/` |
| `AZURE_AI_API_KEY` | Azure OpenAI API key (KEY 1 or KEY 2 from Azure Portal) |
| `AZURE_AI_MODEL` | Deployment name as shown in AI Foundry (default: `gpt-4o`) |
| `AZURE_AI_API_VERSION` | Azure OpenAI API version (default: `2024-05-01-preview`) |
| `AZURE_AI_SYSTEM_PROMPT` | System prompt sent before each user message (optional) |

### Agent (`.localConfigs`) — add manually after AKS deployment

| Variable | Description |
|----------|-------------|
| `clientId` | Entra ID App Registration Client ID (auto-filled by toolkit) |
| `clientSecret` | Entra ID App Registration Client Secret (auto-filled by toolkit) |
| `tenantId` | Azure AD Tenant ID (auto-filled by toolkit) |
| `AKS_ENDPOINT_URL` | AKS LoadBalancer public IP — e.g. `http://<EXTERNAL-IP>/api/prompt` |

### Agent provisioned values (`env/.env.local`) — auto-generated by toolkit, gitignored

| Variable | Description |
|----------|-------------|
| `BOT_ID` | Entra ID App Registration Client ID |
| `TEAMS_APP_ID` | Teams App ID |
| `BOT_DOMAIN` | Dev tunnel domain assigned by toolkit |
| `BOT_ENDPOINT` | Dev tunnel HTTPS endpoint |
| `TEAMS_APP_TENANT_ID` | Azure AD Tenant ID |

---

## Security Notes

- `.env`, `env/.env.local`, `env/.env.dev.user`, and `.localConfigs` are **gitignored** — never commit secrets.
- `aks-api/k8s/secret.yaml` is **gitignored** — fill in the API key locally and apply directly.
- For production:
  - Replace the `LoadBalancer` Kubernetes service type with `ClusterIP` + NGINX Ingress + TLS (cert-manager)
  - Use Azure Key Vault references instead of plain Kubernetes Secrets
  - Restrict the AKS API to private networking (VNet integration or private endpoint)
  - Add authentication to `POST /api/prompt` (managed identity or shared secret)
  - Move `AKS_ENDPOINT_URL` to a Key Vault reference rather than a plain environment variable

---

## Changelog

| Date | Version | Notes |
|------|---------|-------|
| 2026-02-24 | 0.1.0 | Initial POC plan, README, project structure |
| 2026-02-24 | 0.2.0 | Full implementation: AKS API (FastAPI), agent scaffold + AKS tool, build verified |
| 2026-02-24 | 0.2.1 | Added dedicated AKS API testing section with bash + PowerShell commands |
| 2026-02-24 | 0.2.2 | Added port conflict troubleshooting guide |
| 2026-02-24 | 0.2.3 | Added Azure Portal (GUI) deployment guide alongside CLI approach |
| 2026-02-24 | 0.3.0 | AKS API now calls Azure OpenAI via `openai` SDK (`AzureOpenAI` client) |
| 2026-02-24 | 0.3.1 | Added Kubernetes ConfigMap and Secret for Azure AI env vars |
| 2026-02-24 | 0.3.2 | Switched to `openai` SDK; fixed endpoint URL format; added `AZURE_AI_API_VERSION` |
| 2026-02-25 | 0.3.3 | Clarified architecture: AKS public endpoint vs local uvicorn |
| 2026-03-09 | 0.4.0 | Sanitized for public GitHub: removed credentials, replaced customer/agent names with generic placeholders, added Overview/Problem Statement/Solution/Requirements sections, moved AKS endpoint to `AKS_ENDPOINT_URL` env var |
