# Download integrity

Vocari pins SHA-256 checksums in application code. A downloaded file is
checked before replacing its destination; archives are checked before any
installed dependency is removed or extraction begins. A mismatched hash or
truncated response fails the operation. Never replace an expected hash with
one obtained from an untrusted download merely to make an error disappear.

Checksums were recorded on 2026-09-17 from these upstream sources:

| Asset | Source of the expected checksum |
| --- | --- |
| PyTorch CPU bundle | `digest` from the [Vocari release API](https://api.github.com/repos/sirdimitry/Vocari/releases/tags/runtime-deps-torch-cpu-v1) |
| Piper Windows, Linux x86-64, macOS x64 | SHA-256 calculated from each archive at the [official 2023.11.14-2 release](https://github.com/rhasspy/piper/releases/tag/2023.11.14-2) |
| Silero RU v4, EN v3 | SHA-256 calculated from [v4_ru.pt](https://models.silero.ai/models/tts/ru/v4_ru.pt) and [v3_en.pt](https://models.silero.ai/models/tts/en/v3_en.pt) |
| Piper voice ONNX files | LFS SHA-256 object IDs at Hugging Face revision `8914c16824264dfe6425deffca679ce9bb1ab371` |
| Piper voice JSON files | SHA-256 calculated from each JSON at that same [pinned revision](https://huggingface.co/rhasspy/piper-voices/tree/8914c16824264dfe6425deffca679ce9bb1ab371) |

The constants live in `vocari/runtime_deps.py`, `vocari/tts/silero_provider.py`
and `vocari/tts/piper_voices.py`. Changes to an upstream file require a reviewed
checksum update in Vocari; redirects and changing release assets cannot silently
change the expected bytes.

Silero no longer imports code from a remote `torch.hub` repository. It verifies
the pinned model package and loads it with `torch.package.PackageImporter`,
matching the package-loading operation in the [upstream implementation](https://github.com/snakers4/silero-models/blob/d9355348e2781dc8fa25a135d1602c530afae24c/src/silero/silero.py).
Existing Silero cache files can be reused, but only after checking their hashes.

The runtime dependency `.complete` marker now records both version and archive
checksum. Older downloaded PyTorch/Piper installations must be downloaded once
again through Settings to obtain a verified installation marker. Ordinary
Python/venv installations of PyTorch are unaffected. Existing and newly
downloaded Piper voices are considered ready only when both the `.onnx` model
and `.onnx.json` configuration match their pinned hashes. Successful checks are
cached only while both files keep the same sizes and modification timestamps.

These checks detect changes relative to the reviewed bytes, not vulnerabilities
already present in those bytes. They do not authenticate an installation that
has been modified locally after extraction. Revalidating installed native
libraries on every launch is outside this mechanism.
