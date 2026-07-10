from __future__ import annotations

import argparse
import logging

from qinghai_rag.config import PATHS
from qinghai_rag.graph_builder import build_graph, save_graph
from qinghai_rag.io_utils import read_jsonl
from qinghai_rag.schemas import EntityRecord, FactRecord, SourceRecord
from qinghai_rag.state import stage_state


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the evidence-backed NetworkX graph")
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    facts = PATHS.release / "qinghai_facts.jsonl"
    entities = PATHS.release / "qinghai_entities.jsonl"
    sources = PATHS.release / "qinghai_sources.jsonl"
    output = PATHS.cache / "qinghai_graph.json"
    state = stage_state("07_build_graph", [facts, entities, sources], [output])
    if args.resume and state.is_current():
        print("Resume: graph inputs are unchanged.")
        return
    graph = build_graph(
        read_jsonl(facts, FactRecord),
        read_jsonl(entities, EntityRecord),
        read_jsonl(sources, SourceRecord),
    )
    save_graph(graph, output)
    state.commit()
    print(
        f"Built graph with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges: {output}"
    )


if __name__ == "__main__":
    main()
