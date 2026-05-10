# AMD Developer Cloud / ROCm Feedback Draft

## What worked well

- The AMD Developer Hackathon focus on cloud GPU access fits multimodal workloads like PitchSideAI, where local hardware is often the bottleneck.
- ROCm compatibility with PyTorch and model serving stacks makes it realistic to target open-source vision-language models without changing product logic.
- High-memory AMD Instinct instances are a strong fit for football video analysis because longer clips and larger KV caches matter for temporal context.

## Friction points and suggestions

- Clearer end-to-end templates for StreamingVLM and vLLM on ROCm would help teams move faster from model selection to a public demo.
- A hackathon-specific "known good" model list for MI300X would reduce time spent testing quantization, memory settings, and serving flags.
- More examples for Hugging Face Spaces plus external AMD GPU endpoints would help teams separate UI hosting from GPU inference cleanly.

## PitchSideAI-specific learning

PitchSideAI benefited from designing a fallback chain instead of assuming one GPU target. The app can use high-memory AMD GPUs for the best vision path, while smaller environments still support frame-by-frame analysis and demo mode. That made the product more resilient and easier to present.
