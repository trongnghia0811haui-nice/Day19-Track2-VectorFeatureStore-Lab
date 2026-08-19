# AGENTS.md — Kế hoạch xây dựng và playbook sửa lỗi

## 1. Mục tiêu của dự án

Xây dựng một lab có thể tái lập về Vector Store + Feature Store, gồm:

- Tìm kiếm keyword bằng BM25, semantic bằng embedding + Qdrant, và hybrid bằng RRF.
- FastAPI `/search` có response schema ổn định và đo được latency phía server.
- Feast với ba feature view, online lookup và point-in-time historical join.
- Các bài nâng cao về filtered search, agentic retrieval, semantic cache và feature leakage.
- Notebook đã chạy, có output và bằng chứng đúng theo `rubric.md`.

Mặc định ưu tiên **Lite path**. Chỉ dùng Docker path khi task thực sự cần Qdrant
server, Redis, Postgres hoặc embedding `bge-m3`.

## 2. Definition of Done

Một thay đổi chỉ được xem là hoàn tất khi thỏa các điều kiện liên quan sau:

- Không làm thay đổi ngẫu nhiên corpus/golden set; dữ liệu sinh lại vẫn deterministic.
- `python -m pytest -q tests` chạy đúng thư mục test và xanh.
- `python scripts/verify_lite.py` xanh cho Lite path.
- Core benchmark cho thấy hybrid Precision@10 lớn hơn keyword và semantic.
- Hybrid P99 phía server nhỏ hơn 50 ms sau warm-up.
- Feast đăng ký đủ ba feature view, materialize thành công, lookup hợp lệ và có PIT join.
- Notebook liên quan chạy từ đầu đến cuối; nếu là deliverable thì `.ipynb` giữ output.
- Không commit `.env`, API key, model cache, database/registry sinh ra hoặc dữ liệu tạm.
- Diff chỉ chứa thay đổi trong phạm vi task; không sửa threshold để che lỗi.

## 3. Kiến trúc cần giữ

```text
scripts/seed_corpus.py
        |
        v
data/corpus_vn.jsonl + data/golden_set.jsonl
        |
        +--> app/embeddings.py --> Qdrant semantic index
        |
        +--> app/search.py -----> BM25 + semantic + RRF
                                  |
                                  +--> app/main.py (FastAPI)
                                  +--> scripts/benchmark.py

Notebook 04 --> Parquet --> app/feast_repo --> registry --> SQLite/Redis

metadata.py --> filters.py --> Notebook 05
filters.py  --> agent.py   --> Notebook 06
cache.py -----------------> Notebook 07
features.py + feast_repo_ondemand -------> Notebook 08
```

Các file Jupytext `notebooks/*.py` là source dễ review. File `.ipynb` là artifact
để chạy và nộp bài; khi sửa notebook phải đồng bộ cả hai định dạng trước khi bàn giao.

## 4. Quy tắc bất biến

- RRF dùng `1 / (rrf_k + rank)` với `rank` bắt đầu từ 1.
- Embedding backend quyết định vector dimension. Đổi backend phải tạo lại index tương thích.
- Không hard-code 384 nếu code phải hỗ trợ `multilingual`, `bge-m3` hoặc `openai`.
- Không thêm lần gọi RNG vào giữa luồng sinh corpus hiện tại; việc đó làm lệch golden set.
- Metadata phải dựa trên hash ổn định, không dùng `hash()` của Python.
- `Searcher` là object nặng: khởi tạo một lần, tái sử dụng, không rebuild trong mỗi request.
- Đo latency sau warm-up và phân biệt `latency_ms` phía server với wall-clock qua HTTP.
- Feature dùng cho training phải causal; historical join phải là point-in-time join.
- Semantic cache production luôn lọc theo tenant/namespace và có TTL phù hợp.
- Không dùng demo `namespaced=False` ngoài cell minh họa lỗ hổng của Notebook 07.
- Không đổi dữ liệu, metric hoặc rubric chỉ để làm assertion hiện tại xanh.

## 5. Hiện trạng và fix ưu tiên

Checkout có thể chưa có `.venv`, `.env` và `data/`; đây là artifact sinh ra và đã
được ignore. Luôn kiểm tra trước khi kết luận code hỏng.

Một số section vẫn mang nhãn `TODO` dù bên dưới đã có implementation mẫu. Không
đánh giá hoàn thành chỉ bằng comment: chạy acceptance test/rubric tương ứng. Giữ nhãn
nếu nó phục vụ mục đích giảng dạy; chỉ đổi khi task yêu cầu làm sạch starter template.

### P0 — sửa nền tảng trước khi phát triển tính năng

1. **Pytest đang trỏ sai nơi**

   `pyproject.toml` cấu hình `testpaths = ["app", "scripts"]`, trong khi 41 hàm
   test hiện nằm trong `tests/`. Sửa thành `testpaths = ["tests"]`, sau đó chạy:

   ```bash
   python -m pytest --collect-only -q tests
   python -m pytest -q tests
   ```

2. **Metadata dependency chưa đồng nhất**

   `requirements.txt` cho phép `pyarrow<26`, nhưng `pyproject.toml` vẫn để
   `pyarrow<22` dù ghi là mirror của requirements. Đồng bộ upper bound và kiểm tra
   Python 3.14; không cập nhật một file dependency mà bỏ quên file còn lại.

3. **`.env` được tạo nhưng app chưa chắc đã nạp**

   `app/*.py` đọc `os.getenv`, còn `make api` không truyền `--env-file`. Một file
   `.env` tồn tại không tự động trở thành environment variable. Nên gom việc nạp và
   validate cấu hình vào một module settings dùng chung, hoặc truyền env rõ ràng cho
   mọi entry point. Sau fix, in cấu hình không nhạy cảm khi startup và xác minh rằng
   đổi `EMBEDDING_BACKEND` thực sự đổi model/dimension.

4. **Docker Feast config chưa nối với các biến FEAST trong `.env`**

   `app/feast_repo/feature_store.yaml` hiện vẫn hard-code SQLite + file store.
   `verify_docker.py` chỉ ping Redis/Postgres, chưa chứng minh Feast dùng chúng.
   Tạo cấu hình Lite/Docker rõ ràng hoặc sinh config từ một nguồn canonical, rồi bổ
   sung integration check bằng `FeatureStore` thay vì chỉ kiểm tra port.

5. **Vòng đời collection Qdrant server chưa khớp comment**

   `app/search.py` hiện xóa collection khi chạy server rồi index lại. Với server thật,
   nên reuse collection nếu model/dimension/version tương thích; rebuild chỉ qua lệnh
   reset/migrate rõ ràng. Lưu fingerprint model trong metadata hoặc dùng tên collection
   có version để tránh vừa mất dữ liệu vừa gặp lỗi dimension.

6. **README có số test cũ**

   README ghi 34 test trong khi source hiện có 41 hàm test. Sau khi sửa test discovery,
   cập nhật tài liệu theo kết quả collect thực tế hoặc tránh hard-code con số dễ cũ.

Không gộp toàn bộ P0 vào một diff nếu task chỉ liên quan một mục. Mỗi fix cần test hồi
quy mô tả đúng lỗi trước khi sửa.

## 6. Roadmap triển khai

### Giai đoạn 0 — bootstrap và baseline

1. Chọn Lite hoặc Docker; mặc định Lite.
2. Tạo môi trường, cài dependency, tạo `.env`, seed dữ liệu.
3. Xác minh có đúng 1000 corpus docs và 50 golden queries.
4. Chạy smoke test và test suite trước khi sửa code.
5. Ghi lại baseline Precision@10 và latency nếu task có tác động retrieval/performance.

### Giai đoạn 1 — NB1: embedding và vector index

1. Load corpus bằng UTF-8.
2. Khởi tạo `Embedder`; lấy dimension từ backend thay vì constant.
3. Embed `title + " " + text` theo batch 64 và upsert Qdrant.
4. Xác minh collection có 1000 vectors.
5. Chạy query exact và paraphrase; lưu top-5 cùng topic để làm bằng chứng.

Gate: count bằng 1000, payload có `doc_id`, `topic`, `title`, và query trả kết quả hợp lệ.

### Giai đoạn 2 — NB2: hybrid search

1. Xây BM25 và semantic retriever trên cùng tập doc.
2. Lấy depth đủ sâu từ mỗi retriever, mặc định `max(top_k * 5, 50)`.
3. Fuse bằng RRF 1-based, sort giảm dần, trả đúng `top_k`.
4. Đo Precision@10 toàn tập và theo `exact`, `paraphrase`, `mixed`.
5. Nếu hybrid không thắng, debug ranking trước khi đổi model hay threshold.

Gate: hybrid thắng trung bình; slice phản ánh đúng ưu/nhược điểm từng retriever.

### Giai đoạn 3 — NB3: API và latency

1. Load một `Searcher` trong lifespan của FastAPI.
2. Giữ contract `/search?q=&mode=&top_k=&rrf_k=` và validate giới hạn đầu vào.
3. Có `/healthz` phản ánh readiness và số document.
4. Warm model/index, sau đó đo 100 request mỗi mode.
5. Báo cáo P50/P95/P99 server-side; wall-clock chỉ là số phụ.

Gate: response đúng schema, không rebuild index theo request, hybrid P99 server-side < 50 ms.

### Giai đoạn 4 — NB4: Feast

1. Sinh ba Parquet source với timestamp timezone-aware.
2. Chạy `feast apply`, kiểm tra đúng ba feature view.
3. Materialize đến thời điểm bao phủ dữ liệu.
4. Lookup `u_001`, đo 100 lần và báo P50/P95/P99.
5. Chạy historical lookup với ba entity rows và xác minh PIT semantics.

Gate: apply/materialize thành công, lookup có giá trị, PIT join không dùng tương lai.

### Giai đoạn 5 — NB5 đến NB8

- NB5: so sánh pre-filter, post-filter và filtered ANN; đo recall theo selectivity.
- NB6: giữ tổng retrieval budget bằng nhau; planner tách compound query và agent relax
  filter khi thiếu evidence.
- NB7: sweep threshold theo cả hit saving và false hit; test TTL và tenant isolation.
- NB8: feature phải causal; chứng minh target-encoding leakage, latest-vs-PIT join và ODFV.

Gate: chạy các test tương ứng trong `tests/` và tạo đúng bảng/trace mà rubric yêu cầu.

### Giai đoạn 6 — hoàn thiện bài nộp

1. Chạy notebook headless theo thứ tự 01 đến 08 cần thiết.
2. Giữ output trong `.ipynb`, thêm screenshot vào `submission/screenshots/`.
3. Điền `submission/REFLECTION.md` không quá 200 từ.
4. Chạy lại test, smoke, benchmark và kiểm tra git diff.
5. Chỉ push khi không có secret và repo chứa đủ artifact được rubric yêu cầu.

## 7. Lệnh chuẩn

### POSIX, WSL hoặc Git Bash

```bash
bash setup-lite.sh
source .venv/bin/activate

python -m pytest -q tests
python scripts/verify_lite.py
python scripts/benchmark.py

make api
make lab
make notebooks
```

Docker path:

```bash
bash scripts/runtime-check.sh
bash setup-docker.sh
python scripts/verify_docker.py
```

Không chạy `docker compose down -v` hoặc `make clean-lite` chỉ để thử sửa lỗi;
đó là thao tác xóa state. Chỉ dùng khi task yêu cầu reset và đã xác nhận target.

### Windows PowerShell native

Makefile và setup script dùng POSIX path `.venv/bin`, nên ưu tiên WSL/Git Bash.
Nếu chạy native, dùng Python 3.12/3.13 và gọi executable trong venv trực tiếp:

```powershell
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -U pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env

& .\.venv\Scripts\python.exe scripts\seed_corpus.py
& .\.venv\Scripts\python.exe scripts\gen_agent_queries.py
& .\.venv\Scripts\python.exe scripts\gen_spend.py
& .\.venv\Scripts\python.exe scripts\verify_lite.py
& .\.venv\Scripts\python.exe -m pytest -q tests
```

Nếu dùng Python 3.14, phải áp dụng ràng buộc `overrides-py314.txt` theo logic trong
`setup-lite.sh`; không ép Feast dùng bản `dill` cũ đã biết là lỗi trên 3.14.

## 8. Quy trình làm một thay đổi

1. Đọc `README.md`, `rubric.md`, file code và test gần nhất với task.
2. Chạy `git status --short`; bảo toàn mọi thay đổi có sẵn của người dùng.
3. Viết acceptance criteria đo được trước khi code.
4. Tạo hoặc sửa test để tái hiện lỗi bằng case nhỏ nhất.
5. Sửa tối thiểu tại source dùng chung; tránh copy logic sang notebook.
6. Chạy test hẹp, rồi test suite, smoke, benchmark/notebook theo mức ảnh hưởng.
7. Review `git diff --check` và `git diff`; kiểm tra secret, generated file và scope.
8. Bàn giao gồm: file đã đổi, nguyên nhân gốc, lệnh đã chạy, kết quả và phần chưa xác minh.

Không được báo “đã fix” nếu chỉ sửa code mà chưa có lệnh xác minh, trừ khi môi trường
thiếu dependency; trường hợp đó phải ghi rõ giới hạn và lệnh người dùng cần chạy.

## 9. Playbook chẩn đoán và sửa lỗi

| Triệu chứng | Chẩn đoán trước | Cách sửa ưu tiên | Xác minh |
|---|---|---|---|
| `collected 0 items` | Kiểm tra `testpaths` và thư mục `tests/` | Đổi pytest `testpaths` sang `tests`; vẫn gọi explicit `pytest tests` | `pytest --collect-only -q tests` |
| Thiếu `data/corpus_vn.jsonl` | Checkout sạch chưa seed | Chạy `scripts/seed_corpus.py`; không commit file sinh ra | Count 1000 docs, 50 golden queries |
| `python3: command not found` trên Windows | Setup script cần POSIX Python | Dùng WSL/Git Bash hoặc quy trình PowerShell native | Venv Python nằm trong 3.10–3.14 |
| Qdrant báo sai vector dimension | Backend đổi nhưng index cũ giữ dimension cũ | Kiểm tra model/dim, tạo lại collection có version đúng | Embed một câu và so `len(vector)` với schema |
| Sửa `.env` nhưng app vẫn dùng default | Process chưa load/export `.env` | Nạp settings tập trung hoặc truyền env rõ cho entry point | Startup log hiển thị backend/mode mong đợi |
| API startup rất lâu mỗi lần | Server collection bị xóa và embed lại | Reuse collection tương thích; reset chỉ qua lệnh explicit | Restart không upsert lại 1000 vectors |
| Qdrant server timeout | Sai mode/URL hoặc service chưa healthy | Kiểm tra `QDRANT_MODE`, URL, health và port 6333 | `verify_docker.py` và một query thật |
| Indexed count khác 1000 | Seed/index dở hoặc upsert sai ID | Seed lại, index theo batch, kiểm tra exception từng batch | `client.count(...).count == 1000` |
| Hybrid không thắng | RRF rank 0-based, depth quá nông hoặc doc ID lệch | So hai ranked list, dùng rank 1-based và cộng theo `doc_id` | Benchmark toàn tập và theo slice |
| API trả 503 | Lifespan chưa xong hoặc corpus thiếu | Kiểm tra log startup, seed data, chờ `/healthz.ready=true` | `/healthz` báo 1000 docs |
| Port 8000 bận | Process cũ chưa dừng | Xác định đúng PID hoặc dùng port 8001; không kill hàng loạt | `/healthz` của process mới |
| Hybrid P99 > 50 ms | Cold model, rebuild, đo wall-clock hoặc máy đang tải | Warm-up, reuse Searcher, đo server-side, profile trước khi tối ưu | Lặp benchmark và lưu P50/P95/P99 |
| `feast apply` lỗi | Parquet/schema/registry cũ không khớp | Đọc stderr; sửa schema/timestamp. Chỉ xóa registry generated khi cần rebuild | `feast feature-views list` đủ ba view |
| Feast lookup trả `None` | Chưa materialize, timestamp ngoài TTL hoặc entity key sai | Kiểm tra end time, TTL và `user_id`/`doc_id` | Lookup `u_001` có feature hợp lệ |
| Docker chạy nhưng Feast vẫn là SQLite | YAML vẫn là cấu hình Lite | Chọn/generate Docker config và test bằng FeatureStore | Integration test đọc/ghi qua Redis/Postgres |
| Historical feature đẹp bất thường | Có thể dùng latest join và đọc tương lai | Dùng as-of/PIT join theo entity + timestamp, direction backward | Không row nào nhận feature sau event time |
| Semantic cache lộ tenant | Query Qdrant thiếu tenant filter | Bật namespace và bắt buộc filter tenant trong cả get/peek | Cross-tenant request phải MISS |
| Notebook `.py` đúng nhưng `.ipynb` cũ | Chưa đồng bộ Jupytext | Convert/update rồi chạy lại notebook | `.ipynb` chứa code mới và output mới |
| Notebook 03 để lại uvicorn | Cell lỗi trước cleanup | Dùng `try/finally` hoặc context manager quản lý subprocess | Không còn process giữ port sau notebook |

## 10. Ma trận test theo phạm vi

| Phạm vi thay đổi | Test tối thiểu |
|---|---|
| `embeddings.py`, `search.py` | `test_embeddings.py`, smoke Lite, benchmark |
| `filters.py`, `metadata.py` | `test_filters.py test_metadata.py`, Notebook 05 |
| `agent.py` | `test_agent.py`, Notebook 06, kiểm tra budget |
| `cache.py` | `test_cache.py`, Notebook 07, cross-tenant test |
| `features.py`, Feast ODFV | `test_features.py`, Notebook 08 |
| `main.py` | API health/search test, benchmark NB3 |
| Feast definitions/config | `feast apply`, materialize, online + historical lookup |
| setup/dependencies | checkout sạch hoặc venv mới, smoke, test suite |
| Docker/Compose | health cả ba service và integration thật với Qdrant/Feast |

## 11. Checklist bàn giao

- [ ] Task và acceptance criteria đã được ghi rõ.
- [ ] Không ghi đè thay đổi không liên quan của người dùng.
- [ ] Test hẹp và test rộng phù hợp đã chạy.
- [ ] Benchmark được chạy lại nếu đụng retrieval hoặc latency.
- [ ] Notebook/Jupytext đã đồng bộ nếu có thay đổi.
- [ ] Không có `.env`, key, registry DB, model cache hoặc dữ liệu tạm trong diff.
- [ ] README/rubric không mâu thuẫn với behavior mới.
- [ ] Báo rõ mọi test chưa chạy và lý do.
