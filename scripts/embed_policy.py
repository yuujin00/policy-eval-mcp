# embed_policy.py
# 정책 문서를 임베딩하고 Qdrant에 업로드 -> 유사도를 위한 검색 준비이지만, 이를 메모리에만 둘거면 필요 없음.
import os
import json
from tqdm import tqdm
from fastembed.embedding import DefaultEmbedding
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct, VectorParams, Distance

# ✅ 루트 기준 경로 설정
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
INPUT_DIR = os.path.join(ROOT_DIR, "data", "evaluation_structured")

# 벡터 설정
VECTOR_NAME = "default"

# Qdrant 연결 (localhost Docker 기준)
client = QdrantClient(host="localhost", port=6333)

# 임베딩 모델
model = DefaultEmbedding(model_name="intfloat/multilingual-e5-large", cache_dir=".cache")

# 문서별 임베딩 & 업로드
for filename in os.listdir(INPUT_DIR):
    if not filename.endswith(".jsonl"):
        continue

    collection_name = "policy-eval-" + filename.replace(".jsonl", "").lower()  # 예: policy-eval-naver
    path = os.path.join(INPUT_DIR, filename)
    print(f"\n📄 처리 시작: {filename}")
    print(f"  └ 대상 컬렉션: {collection_name}")

    # 컬렉션이 없다면 생성
    if not client.collection_exists(collection_name):
        print(f"  └ 컬렉션 생성 중...")
        client.create_collection(
            collection_name=collection_name,
            vectors_config={VECTOR_NAME: VectorParams(size=1024, distance=Distance.COSINE)},
        )
    else:
        print(f"  └ 기존 컬렉션 사용")

    # JSONL 로딩
    with open(path, "r", encoding="utf-8") as f:
        items = [json.loads(line) for line in f if line.strip()]

    texts = [item["text"] for item in items]
    print(f"  └ 문장 수: {len(texts)}")

    # 임베딩 생성
    print("  └ 임베딩 생성 중...")
    embeddings = list(tqdm(model.embed(texts), total=len(texts)))

    # Qdrant 포인트 준비
    print("  └ Qdrant 업로드 중...")
    points = [
        PointStruct(
            id=i,
            vector={VECTOR_NAME: embedding},
            payload={"text": texts[i]}
        )
        for i, embedding in enumerate(embeddings)
    ]

    client.upsert(collection_name=collection_name, points=points)
    print(f"✅ 업로드 완료: {len(points)}개 → {collection_name}")

print("\n🎉 전체 문서 임베딩 및 업로드 완료")
