# Qwen3-Coder-30B Service

Docker setup for serving Qwen3-Coder-30B-A3B-Instruct-FP8 on NVIDIA Blackwell 7000 (96GB) with RemoteLLMconnector integration.

## Configuration

| Parameter | Value | Description |
|-----------|-------|-------------|
| Model | Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8 | FP8 quantized coding model |
| Served Name | qwen3-coder-30b-a3b-fp8 | API model identifier |
| Tensor Parallel | 1 | Single GPU |
| VRAM Utilization | 92% | ~88GB of 96GB |
| Concurrent Requests | 16 | Max simultaneous requests |
| Max Batched Tokens | 32768 | Batch processing limit |

## Quick Start

```bash
# 1. Configure environment
cp .env.example .env
nano .env  # Fill in BROKER_WS_URL and CONNECTOR_TOKEN

# 2. Start services
docker compose up -d

# 3. Monitor startup (model loading takes ~5-10 minutes)
docker compose logs -f vllm-qwen3-coder
```

## Services

### vllm-qwen3-coder (port 8000)
vLLM OpenAI-compatible API server running the Qwen3-Coder model.

### remotellm-connector
WebSocket bridge that connects the local vLLM instance to your RemoteLLMconnector broker, exposing the model externally without port forwarding.

## Local Testing

```bash
# Health check
curl http://localhost:8000/health

# List models
curl http://localhost:8000/v1/models \
  -H "Authorization: Bearer YOUR_API_KEY"

# Chat completion
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "qwen3-coder-30b-a3b-fp8",
    "messages": [{"role": "user", "content": "Write a Python function to calculate fibonacci"}],
    "max_tokens": 512
  }'
```

## Monitoring

```bash
# Service logs
docker compose logs -f

# GPU utilization
watch -n 1 nvidia-smi

# vLLM metrics
curl http://localhost:9090/metrics
```

## Troubleshooting

### Model won't load (OOM)
Reduce `GPU_MEMORY_UTILIZATION` in `.env`:
```bash
GPU_MEMORY_UTILIZATION=0.88
```

### Connector can't reach broker
Check `BROKER_WS_URL` format and `CONNECTOR_TOKEN` validity:
```bash
docker compose logs remotellm-connector
```

### Slow first response
Model loading takes 5-10 minutes. Check status:
```bash
docker compose logs vllm-qwen3-coder | grep -i "ready\|loaded"
```
