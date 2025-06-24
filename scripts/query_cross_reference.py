# scripts/query_cross_reference.py
# 평가 문장과 법령 문서 간 유사도 검색 (FastEmbed + Qdrant)

import os
import json
from tqdm import tqdm
from fastembed.embedding import DefaultEmbedding
from qdrant_client import QdrantClient

# ✅ 고정 경로 (Streamlit 연동용)
FILENAME = "uploaded_policy_structured.jsonl"
INPUT_PATH = f"data/evaluation_structured/{FILENAME}"
OUTPUT_PATH = f"results/policy_structured_cross_reference.jsonl"

REFERENCE_COLLECTIONS = ["privacy-law", "privacy-decree", "privacy-notification"]
TOP_K = 15

embedder = DefaultEmbedding(model_name="intfloat/multilingual-e5-large", cache_dir=".cache")
client = QdrantClient(host="localhost", port=6333)

def generate_cross_reference(input_path: str = INPUT_PATH, output_path: str = OUTPUT_PATH):
    with open(input_path, "r", encoding="utf-8") as f:
        items = [json.loads(line) for line in f if line.strip()]

    print(f"\n평가 문서 처리 시작: {input_path} (총 {len(items)}개)")

    with open(output_path, "w", encoding="utf-8") as f_out:
        for idx, item in enumerate(tqdm(items, desc="🔍 유사도 검색 중"), 1):
            text = item["text"]
            title = item.get("title", "")
            query_vector = list(embedder.embed([text]))[0]

            related_hits = []
            for ref_collection in REFERENCE_COLLECTIONS:
                hits = client.search(
                    collection_name=ref_collection,
                    query_vector=query_vector,
                    limit=TOP_K,
                    with_payload=True,
                )
                for hit in hits:
                    related_hits.append({
                        "ref_collection": ref_collection,
                        "score": hit.score,
                        "text": hit.payload["text"]
                    })

            related_hits_sorted = sorted(related_hits, key=lambda x: -x["score"])[:TOP_K]

            f_out.write(json.dumps({
                "eval_id": f"{idx:03}",
                "eval_title": title,
                "eval_sentence": text,
                "similar_laws": related_hits_sorted
            }, ensure_ascii=False) + "\n")

    print(f" 완료: {output_path}")

if __name__ == "__main__":
    generate_cross_reference()