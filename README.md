# 🧠 Qdrant 벡터 DB 복원 가이드

이 프로젝트는 Qdrant 벡터 DB를 사용하여 사전 임베딩된 데이터를 저장합니다. 다른 컴퓨터나 환경에서도 동일한 벡터 데이터를 재사용하려면 아래 절차를 따라 복원할 수 있습니다.

---

## 📁 사전 준비

- `qdrant_backup.tar.gz` 파일이 프로젝트 루트 디렉토리에 있어야 합니다.
- Docker가 설치되어 있어야 합니다.  
  [Docker Desktop 설치 가이드](https://www.docker.com/products/docker-desktop)

---

## 🔄 복원 절차

### 1. Qdrant용 Docker 볼륨 생성

```bash
docker volume create qdrant_storage
```

### 2. 백업 데이터 복원

#### ✅ macOS / Linux

```bash
docker run --rm -v qdrant_storage:/volume -v ${PWD}:/backup alpine sh -c "tar xzf /backup/qdrant_backup.tar.gz -C /volume"
```

#### ✅ Windows PowerShell

```powershell
docker run --rm -v qdrant_storage:/volume -v "$(Get-Location):/backup" alpine sh -c "tar xzf /backup/qdrant_backup.tar.gz -C /volume"
```

---

### 3. Qdrant 컨테이너 실행

```bash
docker run -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant
```

Qdrant 서버는 기본적으로 포트 `6333`에서 실행되며, 브라우저에서 다음 주소로 확인 가능합니다:

```
http://localhost:6333/collections
```

---

## 📌 참고 사항

- 이 백업은 `qdrant_storage`라는 Docker 볼륨명을 기준으로 만들어졌습니다. 다른 이름을 사용할 경우 명령어 내 볼륨명을 수정하세요.
- 복원된 Qdrant 인스턴스는 이전에 임베딩된 벡터들을 그대로 유지합니다. 따라서 추가 임베딩 없이 바로 검색에 사용할 수 있습니다.
- LangGraph 또는 MCP 서버와 연결 시 `collection_name`, `vector_name` 등이 기존과 일치해야 정상 작동합니다.

---

&nbsp;

# 🧠 MCP 사용 방법

### 0. Qdrant 벡터 DB 연결

-  Qdrant 벡터 DB 복원 가이드 참고.
-  환경 설정.
```bash
pip install -r requirements.txt
```

### 1. MCP 서버 로컬 실행

```bash
set QDRANT_URL=http://localhost:6333
set EMBEDDING_MODEL=intfloat/multilingual-e5-large
uvx mcp-server-qdrant --transport sse
```

### 2. LangGraph UI 실행

```bash
set PYTHONPATH=src
fastmcp dev src/mcp_server_qdrant/server.py
```

---

&nbsp;

# 🖥️ Streamlit UI 사용 방법

### 3. Streamlit UI 실행

> **사전 조건**  
> - 앞 단계(0 ~ 2)에서 Qdrant 벡터 DB + MCP 서버가 **실행 중**이어야 합니다.  
> - `requirements.txt`에 포함된 Streamlit 관련 의존성이 이미 설치돼 있어야 합니다.

```bash
# Streamlit 앱 실행
streamlit run streamlit_ui.py --server.port 8501
