### Text Embeddings (Vector representations for search/RAG)
- qwen3-embedding:0.6b / 4b - Comprehensive text embeddings built on Qwen3 foundation
- nomic-embed-text-v2-moe:latest - Multilingual MoE text embedding model excelling at multilingual retrieval
- nomic-embed-text:latest - High-performing open embedding model with large token context window
- mxbai-embed-large:latest - State-of-the-art large embedding model from mixedbread.ai
- embeddinggemma:latest - 300M parameter embedding model from Google
- MedAIBase/Qwen3-VL-Embedding:2b - Vision-language embedding (medical domain)

### Vision-Language Models (Multimodal) - Text + Image understanding
- llama3.2-vision:latest / 11b-instruct-q4_K_M - Instruction-tuned image reasoning, visual recognition, OCR
- gemma3:4b / 12b / 27b-cloud - Most capable single-GPU multimodal models (text + image), 128K context, 140+ languages
- qwen3-vl:235b-cloud / 235b-instruct-cloud - Most powerful vision-language model in Qwen family to date
- llava:latest - Novel end-to-end multimodal combining vision encoder + Vicuna for general visual/language understanding
- deepseek-ocr:latest - Vision-language model for token-efficient OCR
- redule26/huihui_ai_qwen2.5-vl-7b-abliterated:latest - Vision-language (Qwen2.5-VL variant)
- gemini-3-flash-preview:latest / cloud - Frontier intelligence with vision, speed-optimized
- gemini-3-pro-preview:latest - Advanced multimodal capabilities

### Image Generation
- x/z-image-turbo:latest - Image generation (Turbo variant)
- x/flux2-klein:latest - Image generation (Flux2 Klein variant)

### Reasoning & Thinking Models - Chain-of-thought, mathematical, logical reasoning
- deepseek-r1:14b / 8b - Open reasoning models approaching O3/Gemini 2.5 Pro performance (distilled variants)
- cogito:14b / sivab14/cogito-thinking:latest - Hybrid reasoning models by Deep Cogito, optimized for coding/STEM (enable with "deep thinking subroutine")
- openthinker:7b - Fully open-source reasoning models built by distilling DeepSeek-R1 (OpenThoughts-114k dataset)
- smallthinker:latest - Small reasoning model fine-tuned from Qwen 2.5 3B, designed for edge deployment and as draft model for QwQ-32B
- phi4-mini-reasoning:latest - Reasoning variant of Phi-4-mini
- kimi-k2-thinking:cloud - Moonshot AI's best open-source thinking model

### Coding & Software Engineering - Code generation, repair, reasoning
- deepcoder:latest / 1.5b - Fully open-source 14B coder model at O3-mini level (LiveCodeBench optimized)
- qwen2.5-coder:0.5b - Code-specific Qwen models for generation/repair/reasoning across 40+ languages
- qwen3-coder:480b-cloud / qwen3-coder-next:cloud - Long context models for agentic and coding tasks (Alibaba)
- devstral-2:123b-cloud / devstral-small-2:24b-cloud - Excels at using tools to explore codebases, editing multiple files, software engineering agents
- minimax-m2:cloud / m2.1 / m2.5 / m2.7 - High-efficiency LLMs built for coding and agentic workflows

### Function Calling & Agentic Tools - Tool use, agents, structured outputs
- functiongemma:latest - Specialized Gemma 3 270M model fine-tuned explicitly for function calling (lightweight, single-turn optimized)
- hermes3:8b - Generalist model with advanced agentic capabilities, function calling, structured output, roleplaying
- granite3.3:8b - IBM models with Fill-in-the-Middle (FIM) code completion, function-calling, structured reasoning, 128K context
- phi4-mini:3.8b - Lightweight model with function calling, strong reasoning (math/logic), 128K context
- nemotron-3-nano:30b-cloud / nemotron-3-super:cloud - Efficient open MoE models for agentic applications (120B Super model for complex multi-agent)
- ministral-3:3b-cloud / 8b / 14b-cloud - Designed for edge deployment, vision + tools capable
- glm-4.6:cloud / glm-4.7:cloud / glm-5:cloud / glm-5.1:cloud - Advanced agentic, reasoning and coding capabilities (Z.ai models)
- kimi-k2:1t-cloud / kimi-k2.5:cloud - State-of-the-art MoE language models, native multimodal agentic with instant/thinking modes

### Translation Specialist
- translategemma:4b - Open translation models built on Gemma 3 for 55 languages

### Medical/Domain Specific
- MedAIBase/MedGemma1.0:4b - Medical domain-specific Gemma variant

### Compact & Edge Models - Resource-constrained deployment (phones/laptops)
- gemma3n:latest / e2b / e4b - Efficient execution on everyday devices using selective parameter activation (effective 2B/4B)
- smollm2:1.7b / 360m - Compact language models for on-device deployment (135M/360M/1.7B)
- phi3:mini - Lightweight 3.8B model for memory/compute constrained environments, latency bound scenarios
- granite4:350m - IBM Granite 4 (small parameter model)
- gemma3:1b / 270m - Text-only lightweight Gemma variants

### General Purpose / Instruction-Tuned - Broad chat/assistant capabilities
- qwen3:14b - General instruction-tuned generative models
- mistral-nemo:12b - General purpose (implied by naming, Mistral's general models)
- gemma:latest - General purpose Gemma
- llama3.1:latest - State-of-the-art from Meta, multilingual, 128K context, tool use
- llama3:latest - General chat/assistant
- llama3.2:latest - 3B parameter efficient models
- 0xroyce/plutus:latest - General purpose (community model)
- gurubot/glazer:latest - General purpose (community model)
- MartinRizzo/Ayla-Light-v2:12b-q4_K_M - Conversational/assistant focused
- helpful-assistant:latest - General assistant model
- rnj-1:8b-cloud - Cloud general purpose

### Cloud-Only Large Foundation Models - Massive models only available via cloud API
- cogito-2.1:671b-cloud - Instruction-tuned generative models, MIT licensed (hybrid reasoning capable)
- gpt-oss:120b-cloud / 20b-cloud - OpenAI's open-weight models for powerful reasoning and agentic tasks
- deepseek-v3.1:671b-cloud / deepseek-v3.2:cloud - Hybrid thinking/non-thinking modes, high computational efficiency
- qwen3-next:80b-cloud - First installment in Qwen3-Next series (parameter efficiency + inference speed)
- mistral-large-3:675b-cloud - General-purpose multimodal mixture-of-experts for production-grade enterprise tasks
- qwen3.5:cloud / 397b-cloud - Open-source multimodal family with exceptional utility/performance
- gemma4:31b-cloud - Frontier-level performance at each size, suited for reasoning/agentic/coding/multimodal
- devstral-2:123b-cloud - Software engineering agent capabilities
