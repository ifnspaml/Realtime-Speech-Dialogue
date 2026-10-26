# Citation and upstream references

This repository supplies the shared demonstration UI, protocol adapters and
backend integration. Cite the upstream model and pipeline implementations
when using them, alongside this repository where appropriate. GitHub's
"Cite this repository" entry reads CITATION.cff; no DOI or publication is claimed
for this integration.

## Moshi and Mimi

Use the citation supplied by [Kyutai's official repository](https://github.com/kyutai-labs/moshi#citation):

```bibtex
@techreport{kyutai2024moshi,
  title={Moshi: a speech-text foundation model for real-time dialogue},
  author={Alexandre D{\'e}fossez and Laurent Mazar{\'e} and Manu Orsini and
          Am{\'e}lie Royer and Patrick P{\'e}rez and Herv{\'e} J{\'e}gou and
          Edouard Grave and Neil Zeghidour},
  year={2024},
  eprint={2410.00037},
  archivePrefix={arXiv},
  primaryClass={eess.AS},
  url={https://arxiv.org/abs/2410.00037}
}
```

## Modular pipeline and model components

Acknowledge [Hugging Face Speech-to-Speech](https://github.com/huggingface/speech-to-speech),
frozen here at `81b688b452ee6b64ff5745b91985e9eb653fcc9f`. Its current upstream
defaults may differ from this repository's pinned model configuration.
Follow the relevant model cards' citation guidance for Parakeet, Qwen3,
Qwen3-TTS, Silero VAD and Smart Turn. Links and exact revisions are in
[Models](models.md) and config/models.json. Converted TTS weights also retain
Serveurperso's GGUF conversion attribution.

See [Third-party notices](../THIRD_PARTY_NOTICES.md) for software/model terms.
Model licenses are separate from the Apache-2.0 license on project-owned code.
