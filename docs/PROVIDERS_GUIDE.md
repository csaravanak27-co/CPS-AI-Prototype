# C.P.S. — Model & Provider Configuration Guide

C.P.S. implements a modular provider architecture allowing seamless switching between local private models and hosted cloud providers.

---

## 1. Local Inference: Ollama & Gemma 4 (Recommended for Privacy)

Run 100% private models on your local hardware with zero data transmission to external servers.

### Step 1: Install Ollama
Download and install Ollama from [ollama.com](https://ollama.com). Verify installation:
```powershell
ollama --version
```

### Step 2: Pull the Gemma 4 Model
```powershell
ollama pull gemma4:e2b-it-q4_K_M
```
*Note:* The quantized Gemma 4 E2B model requires approximately ~4.6 GB of storage and runs smoothly on machines with 8 GB+ RAM. Alternatively, any installed Ollama model (e.g. `llama3.2`, `codellama`, `qwen2.5-coder`) can be configured by setting `OLLAMA_MODEL` or configuring it in the desktop Model Manager.

### Step 3: Run Ollama Server
Ensure the Ollama daemon is active (starts automatically on Windows boot, or execute `ollama serve`).

---

## 2. Hosted Providers

### A. Groq (Ultra-Fast Hosted Inference)
- **Model:** `llama-3.3-70b-versatile`
- **Setup:**
  1. Generate a free API key at [console.groq.com/keys](https://console.groq.com/keys).
  2. Set your environment variable:
     ```powershell
     $env:GROQ_API_KEY="gsk_your_key_here"
     ```
     Or paste it into `.env`:
     ```env
     GROQ_API_KEY=gsk_your_key_here
     ```

### B. Google Gemini API
- **Model:** `gemini-2.0-flash`
- **Setup:**
  1. Generate an API key at [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey).
  2. Configure via `.env`:
     ```env
     GEMINI_API_KEY=your_gemini_key_here
     ```

### C. OpenRouter Gateway
- **Model:** `meta-llama/llama-3.3-70b-instruct:free`
- **Setup:**
  1. Obtain a free key at [openrouter.ai/keys](https://openrouter.ai/keys).
  2. Configure via `.env`:
     ```env
     OPENROUTER_API_KEY=sk-or-v1-your_key_here
     ```

---

## 3. Mock / Offline Mode (Deterministic)
- Requires **no API keys, no Ollama, and no internet access**.
- Provides deterministic, pre-computed high-quality solutions and security remediations.
- Ideal for offline testing, CI/CD automated test pipelines, and quick demos.
