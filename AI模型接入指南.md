# AI 模型接入指南

本文档说明如何为 AutoPentestAI 配置不同的 AI 大模型。

## 配置文件位置

编辑项目根目录下的 `.env` 文件：

```bash
AI_PROVIDER=openai          # 模型提供商
OPENAI_API_KEY=your-key     # API Key
OPENAI_BASE_URL=api-endpoint # API 端点
AI_MODEL=model-name         # 模型名称
```

---

## 支持的模型

### 1. DeepSeek（默认）

| 配置项 | 值 |
|--------|-----|
| AI_PROVIDER | `deepseek` |
| AI_MODEL | `deepseek-reasoner` 或 `deepseek-chat` |
| DEEPSEEK_API_KEY | 你的 DeepSeek API Key |

```bash
AI_PROVIDER=deepseek
AI_MODEL=deepseek-reasoner
DEEPSEEK_API_KEY=sk-xxxx
```

---

### 2. OpenAI

| 配置项 | 值 |
|--------|-----|
| AI_PROVIDER | `openai` |
| AI_MODEL | `gpt-4o`、`gpt-4o-mini` 等 |
| OPENAI_API_KEY | 你的 OpenAI API Key |
| OPENAI_BASE_URL | `https://api.openai.com/v1` |

```bash
AI_PROVIDER=openai
AI_MODEL=gpt-4o
OPENAI_API_KEY=sk-xxxx
OPENAI_BASE_URL=https://api.openai.com/v1
```

---

### 3. Kimi K2.5（Moonshot AI）

| 配置项 | 值 |
|--------|-----|
| AI_PROVIDER | `openai` |
| AI_MODEL | `kimi-k2.5` |
| OPENAI_API_KEY | 你的 Kimi API Key |
| OPENAI_BASE_URL | `https://api.moonshot.cn/v1` |

```bash
AI_PROVIDER=openai
AI_MODEL=kimi-k2.5
OPENAI_API_KEY=你的Kimi_API_Key
OPENAI_BASE_URL=https://api.moonshot.cn/v1
```

> Kimi API 申请地址：https://platform.moonshot.cn/

---

### 4. GLM-5（智谱 AI）

| 配置项 | 值 |
|--------|-----|
| AI_PROVIDER | `openai` |
| AI_MODEL | `glm-5` |
| OPENAI_API_KEY | 你的 GLM API Key |
| OPENAI_BASE_URL | `https://open.bigmodel.cn/api/paas/v4` |

```bash
AI_PROVIDER=openai
AI_MODEL=glm-5
OPENAI_API_KEY=你的GLM_API_Key
OPENAI_BASE_URL=https://open.bigmodel.cn/api/pais/v4
```

> GLM API 申请地址：https://open.bigmodel.cn/

---

### 5. Ollama（本地模型）

| 配置项 | 值 |
|--------|-----|
| AI_PROVIDER | `openai` |
| AI_MODEL | `llama3`、`qwen2.5` 等 |
| OPENAI_API_KEY | `ollama`（任意值） |
| OPENAI_BASE_URL | `http://localhost:11434/v1` |

```bash
AI_PROVIDER=openai
AI_MODEL=llama3
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://localhost:11434/v1
```

> 确保本地已安装 Ollama 并运行 `ollama serve`

---

### 6. Anthropic Claude

| 配置项 | 值 |
|--------|-----|
| AI_PROVIDER | `openai` |
| AI_MODEL | `claude-3-5-sonnet-20241022` 等 |
| OPENAI_API_KEY | 你的 Anthropic API Key |
| OPENAI_BASE_URL | `https://api.anthropic.com/v1` |

```bash
AI_PROVIDER=openai
AI_MODEL=claude-3-5-sonnet-20241022
OPENAI_API_KEY=sk-ant-xxxx
OPENAI_BASE_URL=https://api.anthropic.com/v1
```

> 注意：Anthropic API 需要额外配置，请确保模型支持 OpenAI 兼容格式。

---

### 7. Google Gemini

| 配置项 | 值 |
|--------|-----|
| AI_PROVIDER | `openai` |
| AI_MODEL | `gemini-2.0-flash` 等 |
| OPENAI_API_KEY | 你的 Google AI API Key |
| OPENAI_BASE_URL | `https://generativelanguage.googleapis.com/v1` |

```bash
AI_PROVIDER=openai
AI_MODEL=gemini-2.0-flash
OPENAI_API_KEY=你的Google_API_Key
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1
```

---

### 8. Together AI

| 配置项 | 值 |
|--------|-----|
| AI_PROVIDER | `openai` |
| AI_MODEL | `meta-llama/Llama-3.3-70B-Instruct-Turbo` 等 |
| OPENAI_API_KEY | 你的 Together AI API Key |
| OPENAI_BASE_URL | `https://api.together.ai/v1` |

```bash
AI_PROVIDER=openai
AI_MODEL=meta-llama/Llama-3.3-70B-Instruct-Turbo
OPENAI_API_KEY=你的Together_API_Key
OPENAI_BASE_URL=https://api.together.ai/v1
```

---

### 9. OpenRouter（聚合多模型）

| 配置项 | 值 |
|--------|-----|
| AI_PROVIDER | `openai` |
| AI_MODEL | `openai/gpt-4o`、`anthropic/claude-3.5-sonnet` 等 |
| OPENAI_API_KEY | 你的 OpenRouter API Key |
| OPENAI_BASE_URL | `https://openrouter.ai/api/v1` |

```bash
AI_PROVIDER=openai
AI_MODEL=openai/gpt-4o
OPENAI_API_KEY=你的OpenRouter_API_Key
OPENAI_BASE_URL=https://openrouter.ai/api/v1
```

> OpenRouter 可访问数百种模型，支持 OpenAI 兼容格式。

---

## 通用配置模板

```bash
# ========== AI 模型配置 ==========
AI_PROVIDER=openai          # 可选: deepseek, openai
AI_MODEL=                   # 模型名称，根据提供商选择

# DeepSeek 配置
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# OpenAI 兼容格式配置（用于其他模型）
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1

# ========== 其他配置 ==========
PROXY_URL=                  # 可选：代理地址
```

---

## 注意事项

1. **API Key 安全**：不要将包含真实 Key 的 `.env` 文件提交到 Git
2. **模型兼容性**：项目使用 OpenAI SDK，理论上任何支持 `/v1/chat/completions` 接口的模型都可以接入
3. **本地模型**：Ollama 需要先在本地安装并启动服务
4. **网络问题**：国内访问部分海外 API 可能需要代理

---

## 相关文件

- `.env` - 环境变量配置文件
- `.env.example` - 环境变量配置示例
- `src/agent/core.py` - AI 客户端初始化代码
