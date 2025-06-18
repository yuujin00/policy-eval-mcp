import os
import json
from tqdm import tqdm
from fastembed.embedding import DefaultEmbedding
from qdrant_client import QdrantClient
from qdrant_client.http.models import NamedVector

# ✅ 루트 기준 경로 설정
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
INPUT_DIR = os.path.join(ROOT_DIR, "data", "evaluation_structured")
OUTPUT_DIR = os.path.join(ROOT_DIR, "results")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 설정
REFERENCE_COLLECTIONS = ["privacy-law", "privacy-decree", "privacy-notification"]
TOP_K = 15

# 모델 및 Qdrant 클라이언트
embedder = DefaultEmbedding(model_name="intfloat/multilingual-e5-large", cache_dir=".cache")
client = QdrantClient(host="localhost", port=6333)

# 🔁 모든 평가 문서 처리
for filename in os.listdir(INPUT_DIR):
    if not filename.endswith(".jsonl"):
        continue

    collection_eval = filename.replace(".jsonl", "")
    input_path = os.path.join(INPUT_DIR, filename)
    output_path = os.path.join(OUTPUT_DIR, f"{collection_eval}_cross_reference.json")

    with open(input_path, "r", encoding="utf-8") as f:
        items = [json.loads(line) for line in f if line.strip()]

    print(f"\n📄 평가 문서 처리 시작: {collection_eval} (총 문장 {len(items)}개)")

    results = []
    for item in tqdm(items, desc=f"🔍 유사도 검색 중: {collection_eval}"):
        text = item["text"]
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

        # 상위 TOP_K만 유지
        related_hits_sorted = sorted(related_hits, key=lambda x: -x["score"])[:TOP_K]

        results.append({
            "eval_text": text,
            "references": related_hits_sorted
        })

    with open(output_path, "w", encoding="utf-8") as f_out:
        json.dump(results, f_out, ensure_ascii=False, indent=2)

    print(f"✅ 완료: {output_path}")
print("\n🎉 모든 평가 문서의 교차 참조 완료")