## 임베딩 초기 테스트 스크립트


import os
import json
from tqdm import tqdm
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from fastembed.embedding import TextEmbedding

# 환경변수 불러오기
COLLECTION_NAME = os.environ.get("COLLECTION_NAME", "policy-guidelineset")
MODEL_NAME = os.environ.get("EMBEDDING_MODEL", "intfloat/multilingual-e5-large")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")

# 경로 설정
JSONL_PATH = "data/jsonl/law_privacy.jsonl"  # ← 필요한 경우 경로 수정

print(f"[INFO] COLLECTION_NAME = {COLLECTION_NAME}")
print(f"[INFO] MODEL_NAME = {MODEL_NAME}")
print(f"[INFO] QDRANT_URL = {QDRANT_URL}")
print(f"[INFO] JSONL_PATH = {JSONL_PATH}")

# Qdrant 클라이언트 연결
client = QdrantClient(url=QDRANT_URL)

# 임베딩 모델 초기화
embedder = TextEmbedding(MODEL_NAME)
embed_dim = 1024  # intfloat/multilingual-e5-large

# 컬렉션 생성 또는 초기화
client.recreate_collection(
    collection_name=COLLECTION_NAME,
    vectors_config=VectorParams(
        size=embed_dim,
        distance=Distance.COSINE
    )
)

# JSONL 파일 읽기 및 디버깅 출력
with open(JSONL_PATH, "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"[DEBUG] 총 JSONL 라인 수: {len(lines)}")

# json 파싱
data = [json.loads(line) for line in lines if line.strip()]

print(f"[DEBUG] JSON 디코딩 완료: {len(data)}개 항목")

# text 필드가 존재하는 문서만 필터링
valid_entries = [entry for entry in data if entry.get("text")]

print(f"[DEBUG] 유효한 문서 수 (text 포함): {len(valid_entries)}")
if valid_entries:
    print("[DEBUG] 샘플 문서:", valid_entries[0])

# 텍스트만 추출
texts = [entry["text"] for entry in valid_entries]

# 임베딩
print("[DEBUG] 임베딩 시작")
embeddings = list(embedder.embed(texts))

# Qdrant에 업로드할 포인트 구성
points = [
    PointStruct(
        id=i,
        vector=vector,
        payload=valid_entries[i]  # 메타데이터 그대로 보존
    )
    for i, vector in enumerate(tqdm(embeddings))
]

client.upsert(collection_name=COLLECTION_NAME, points=points)
print(f"✅ 업로드 완료: {len(points)}개 문서")
