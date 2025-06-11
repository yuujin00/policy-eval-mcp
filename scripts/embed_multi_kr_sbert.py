import os
import json
from tqdm import tqdm
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from sentence_transformers import SentenceTransformer

# 모델 설정
MODEL_NAME = "snunlp/KR-SBERT-V40K-klueNLI-augSTS"
VECTOR_NAME = f"fast-{MODEL_NAME.split('/')[-1].lower()}"
EMBED_DIM = 768
QDRANT_URL = "http://localhost:6333"

# 업로드할 파일명 → 컬렉션명 매핑
FILES = {
    "law_privacy.jsonl": "privacy-law",
    "decree_privacy.jsonl": "privacy-decree",
    "notice_privacy.jsonl": "privacy-notification"
}

# 경로 설정
DATA_DIR = "data/jsonl"

# 모델 로드
embedder = SentenceTransformer(MODEL_NAME)
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
    embeddings = embedder.encode(texts, convert_to_numpy=True, show_progress_bar=True)

    print("  └ 컬렉션 생성 또는 초기화...")
    client.recreate_collection(
        collection_name=collection_name,
        vectors_config={
            VECTOR_NAME: VectorParams(
                size=EMBED_DIM,
                distance=Distance.COSINE
            )
        }
    )

    print("  └ Qdrant에 업로드 중...")
    points = [
        PointStruct(id=i, vector={VECTOR_NAME: embeddings[i]}, payload=valid_entries[i])
        for i in range(len(embeddings))
    ]
    client.upsert(collection_name=collection_name, points=points)
    print(f"✅ 완료: {len(points)}개 업로드됨")

print("\n🎉 전체 임베딩 및 업로드 완료")
