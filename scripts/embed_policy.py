# 평가 문서 임베딩 및 Qdrant 업로드
import os
import json
from tqdm import tqdm
from fastembed.embedding import DefaultEmbedding
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct, VectorParams, Distance

# 설정
COLLECTION_NAME = "policy-eval"
VECTOR_NAME = "default"
INPUT_DIR = "data/evaluation_split"

# Qdrant 연결 (localhost Docker 기준)
client = QdrantClient(host="localhost", port=6333)

# 컬렉션 생성 (없을 때만)
if not client.collection_exists(COLLECTION_NAME):
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={VECTOR_NAME: VectorParams(size=512, distance=Distance.COSINE)},
    )

# 임베딩 모델
model = DefaultEmbedding(model_name="intfloat/multilingual-e5-large", cache_dir=".cache")

# 문서별 업로드
for filename in os.listdir(INPUT_DIR):
    if not filename.endswith(".jsonl"):
        continue

    path = os.path.join(INPUT_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        items = [json.loads(line) for line in f]

    texts = [item["text"] for item in items]
    embeddings = list(model.embed(texts))

    points = [
        PointStruct(id=i, vector=embedding, payload={"text": items[i]["text"]})
        for i, embedding in enumerate(embeddings)
    ]
    client.upsert(collection_name=COLLECTION_NAME, points=points)
    print(f"📄 업로드 완료: {filename} → {len(points)}개")
