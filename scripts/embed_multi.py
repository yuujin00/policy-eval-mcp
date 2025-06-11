import os
import json
from tqdm import tqdm
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from fastembed.embedding import TextEmbedding

# 모델 설정
MODEL_NAME = "intfloat/multilingual-e5-large"
VECTOR_NAME = f"fast-{MODEL_NAME.split('/')[-1].lower()}"
EMBED_DIM = 1024
QDRANT_URL = "http://localhost:6333"

# 임베딩 대상 파일 및 컬렉션 이름 매핑
FILES = {
    "law_privacy.jsonl": "privacy-law",
    "decree_privacy.jsonl": "privacy-decree",
    "notice_privacy.jsonl": "privacy-notification"
}

# 경로
DATA_DIR = "data/jsonl"

# 모델 로드
embedder = TextEmbedding(MODEL_NAME)
client = QdrantClient(url=QDRANT_URL)

# 파일별 업로드 수행
for filename, collection_name in FILES.items():
    path = os.path.join(DATA_DIR, filename)
    print(f"\n📄 처리 중: {filename} → 컬렉션: {collection_name}")

    with open(path, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]

    valid_entries = [entry for entry in lines if entry.get("text")]
    texts = [entry["text"] for entry in valid_entries]

    print(f"  └ 문서 수: {len(valid_entries)}")

    print("  └ 임베딩 생성 중...")
    embeddings = list(embedder.embed(texts))

    print("  └ 컬렉션 생성 또는 초기화...")
    client.recreate_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=EMBED_DIM,
            distance=Distance.COSINE
        )
    )

    print("  └ Qdrant에 업로드 중...")
    points = [
        PointStruct(id=i, vector=embeddings[i], payload=valid_entries[i])
        for i in range(len(embeddings))
    ]
    client.upsert(collection_name=collection_name, points=points)
    print(f"✅ 완료: {len(points)}개 업로드됨")

print("\n🎉 전체 임베딩 및 업로드 완료")
