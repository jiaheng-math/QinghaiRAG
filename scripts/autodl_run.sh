#!/usr/bin/env bash
# One-shot QinghaiRAG pipeline for AutoDL GPU instances.
#
# Usage (inside the Python environment you want to use, e.g. the AutoDL conda base):
#   bash scripts/autodl_run.sh
#
# Tunables (environment variables):
#   DEVICE=cuda|cpu          embedding/reranker device        (default: cuda, auto-falls back to cpu)
#   BATCH_SIZE=128           embedding batch size             (default: 128)
#   RERANK=1|0               evaluate cross-encoder reranked modes (default: 1)
#   RUN_DATA_STAGES=1|0      rebuild facts/entities/chunks/qa from local documents (default: 0)
#   SKIP_INSTALL=1|0         skip `pip install -e .[dev]`     (default: 0)
#   HF_ENDPOINT=...          Hugging Face mirror; defaults to https://hf-mirror.com for mainland networks
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export QINGHAI_RAG_HOME="${QINGHAI_RAG_HOME:-$REPO_ROOT}"
export QINGHAI_RAG_DATA_DIR="${QINGHAI_RAG_DATA_DIR:-$QINGHAI_RAG_HOME/data}"
export QINGHAI_RAG_CACHE_DIR="${QINGHAI_RAG_CACHE_DIR:-$QINGHAI_RAG_DATA_DIR/cache}"
export QINGHAI_RAG_CHECKPOINT_DIR="${QINGHAI_RAG_CHECKPOINT_DIR:-$QINGHAI_RAG_CACHE_DIR/checkpoints}"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"

DEVICE="${DEVICE:-cuda}"
BATCH_SIZE="${BATCH_SIZE:-128}"
RERANK="${RERANK:-1}"
RUN_DATA_STAGES="${RUN_DATA_STAGES:-0}"
SKIP_INSTALL="${SKIP_INSTALL:-0}"

cd "$REPO_ROOT"
echo "== QinghaiRAG on AutoDL: home=$QINGHAI_RAG_HOME device=$DEVICE =="

if [ "$SKIP_INSTALL" != "1" ]; then
  python -m pip install --upgrade pip
  python -m pip install -e ".[dev]"
fi

if [ "$DEVICE" = "cuda" ] && ! python -c "import torch; raise SystemExit(0 if torch.cuda.is_available() else 1)" 2>/dev/null; then
  echo "WARN: CUDA is not available in this environment; falling back to cpu."
  DEVICE=cpu
fi

if [ "$RUN_DATA_STAGES" = "1" ]; then
  python scripts/02_extract_facts.py --resume
  python scripts/03_build_entities.py --resume
  python scripts/04_build_chunks.py --resume
  python scripts/05_build_qa_eval.py --minimum 300 --resume
fi

python scripts/09_validate_release.py
python scripts/07_build_graph.py --resume
python scripts/06_build_vector_index.py --device "$DEVICE" --batch-size "$BATCH_SIZE" --resume

RERANK_FLAG=--rerank
if [ "$RERANK" != "1" ]; then RERANK_FLAG=--no-rerank; fi
python -m qinghai_rag.rag.evaluate --device "$DEVICE" "$RERANK_FLAG"

python scripts/11_dataset_stats.py

echo "== Done. Reports: =="
echo "  $QINGHAI_RAG_DATA_DIR/interim/eval_report.md"
echo "  $QINGHAI_RAG_DATA_DIR/interim/dataset_stats.md"
echo "  $QINGHAI_RAG_DATA_DIR/release/validation_report.md"
