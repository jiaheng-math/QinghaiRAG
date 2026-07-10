# AutoDL runbook

## Persistent layout

Keep the repository, raw data, indexes, checkpoints, and model caches under `/root/autodl-tmp` (or the persistent data-disk mount shown by the current AutoDL image). Verify the mount rather than assuming the system disk survives instance release.

```bash
export QINGHAI_RAG_HOME=/root/autodl-tmp/QinghaiRAG
export QINGHAI_RAG_DATA_DIR=$QINGHAI_RAG_HOME/data
export QINGHAI_RAG_CACHE_DIR=$QINGHAI_RAG_DATA_DIR/cache
export QINGHAI_RAG_CHECKPOINT_DIR=$QINGHAI_RAG_CACHE_DIR/checkpoints
```

`configure_external_caches()` assigns HF Hub, Datasets, Transformers, and Sentence Transformers caches below the cache root. Explicit environment variables override these defaults.

## One-shot run

```bash
cd /root/autodl-tmp/QinghaiRAG
bash scripts/autodl_run.sh
```

The script installs the package into the **current** Python environment (AutoDL images ship a conda base with PyTorch preinstalled — reuse it instead of creating a bare venv, which would lose the CUDA-enabled torch). It exports the persistent-path variables above relative to the repository, defaults `HF_ENDPOINT=https://hf-mirror.com` so BAAI model downloads work from mainland networks, verifies CUDA (falling back to CPU with a warning), then runs validate → graph → vector index → evaluation → stats with resume enabled.

Tunables: `DEVICE=cuda|cpu`, `BATCH_SIZE=128`, `RERANK=1|0` (cross-encoder reranked evaluation modes), `RUN_DATA_STAGES=1` (also rebuild facts/entities/chunks/QA from locally collected documents), `SKIP_INSTALL=1`, `HF_ENDPOINT=...`.

## Manual first run

```bash
cd /root/autodl-tmp/QinghaiRAG
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python scripts/09_validate_release.py
python scripts/06_build_vector_index.py --device cuda --batch-size 128 --resume
python scripts/07_build_graph.py --resume
python -m qinghai_rag.rag.evaluate --device cuda --rerank
```

Reduce batch size if CUDA OOM occurs. Changing model/device parameters or chunk inputs invalidates the vector manifest; an identical restart reuses the index and weights. The BM25 index is rebuilt in-memory from the released chunks at startup (seconds even at v1.0 scale), so it needs no cache of its own. The reranker (`BAAI/bge-reranker-base` by default) downloads once into the shared Hugging Face cache and runs on the same `--device`.

## Interrupted jobs

- Collection saves each raw response atomically and checkpoints each source.
- Derived stages compare input fingerprints and parameters to checkpoint manifests.
- FAISS is written to a temporary path and renamed only when complete.
- JSON/JSONL helpers flush, fsync, and atomically replace destination files.
- Start long runs inside `tmux`; logs may be redirected to a file under `data/interim/`.

Do not delete `data/cache/checkpoints` merely to force a rebuild. Use `--no-resume`, and preserve the old manifest/output under a versioned experiment directory when comparisons matter.

## Future parameter training

The present project performs embedding inference and index construction, not model fine-tuning. A future bi-encoder/reranker training command should persist at least model weights, optimizer, scheduler, scaler, RNG states, epoch/global step, data/config fingerprint, and best metric. It should save every fixed number of optimizer steps through temporary-directory rename and accept `--resume-from-checkpoint latest|PATH`. Never store API tokens in a checkpoint or repository.
