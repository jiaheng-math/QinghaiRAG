from __future__ import annotations

import argparse

import gradio as gr

from qinghai_rag.rag.answer import EvidenceAnswerer, OpenAICompatibleBackend
from qinghai_rag.rag.retriever import build_hybrid_retriever


def create_app(
    use_llm: bool = False, device: str | None = None, rerank: bool | None = None
) -> gr.Blocks:
    retriever = build_hybrid_retriever(device=device, rerank=rerank)
    modes = retriever.available_modes()
    if not modes:
        raise FileNotFoundError("Build the vector index, chunks, or graph before the demo")
    backend = OpenAICompatibleBackend() if use_llm else None
    answerer = EvidenceAnswerer(backend=backend)

    def respond(question: str, mode: str):
        if not question.strip():
            return "请输入问题。", []
        evidence = retriever.retrieve(question, mode=mode, top_k=5, budget=10)
        result = answerer.answer(question, evidence)
        rows = [
            [
                item.get("kind"),
                item.get("text"),
                item.get("source_id"),
                item.get("source_title", ""),
                item.get("source_url"),
                round(float(item.get("score", 0)), 4),
            ]
            for item in result["evidence"]
        ]
        return result["answer"], rows

    default_mode = "hybrid" if "hybrid" in modes else modes[0]
    with gr.Blocks(title="QinghaiRAG") as app:
        gr.Markdown(
            "# QinghaiRAG\n可溯源的青海非遗与地域文化检索基线。默认只展示证据，不调用大模型。"
        )
        question = gr.Textbox(label="问题", placeholder="例如：塔尔寺酥油花属于哪一类别？")
        mode = gr.Radio(modes, value=default_mode, label="检索模式")
        submit = gr.Button("检索并回答", variant="primary")
        answer = gr.Markdown(label="回答")
        evidence = gr.Dataframe(
            headers=["类型", "证据", "source_id", "来源标题", "来源 URL", "分数"],
            interactive=False,
            label="Top evidence",
        )
        submit.click(respond, [question, mode], [answer, evidence])
        question.submit(respond, [question, mode], [answer, evidence])
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the QinghaiRAG Gradio demo")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--share", action="store_true")
    parser.add_argument("--use-llm", action="store_true")
    parser.add_argument("--device", default=None, help="Override embedding/reranker device")
    parser.add_argument(
        "--rerank",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable cross-encoder reranked modes (defaults to configs/rag.yaml)",
    )
    args = parser.parse_args()
    create_app(use_llm=args.use_llm, device=args.device, rerank=args.rerank).launch(
        server_name=args.host, server_port=args.port, share=args.share
    )


if __name__ == "__main__":
    main()
