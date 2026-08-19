# Reflection — Lab 19

**Tên:** Track2_Day19_2A202601370_TranTrongNghia
**Path đã chạy:** lite

## Câu hỏi (≤ 200 chữ)

> Trên golden set 50 queries, mode nào thắng ở loại query nào (`exact` /
> `paraphrase` / `mixed`), và tại sao? Khi nào bạn **không** dùng hybrid
> (i.e. khi nào pure BM25 hoặc pure vector là lựa chọn đúng)?

Trên golden set 50 queries, BM25 và hybrid đều thắng ở nhóm exact (96,7%) vì query chứa thuật ngữ xuất hiện trực tiếp trong tài liệu. Hybrid thắng nhóm mixed (100%) nhờ kết hợp khớp từ khóa và ngữ nghĩa. Ở nhóm paraphrase, BM25 đạt 33,3%, hybrid 32%, vector 24%; vector thấp do Lite path dùng model thiên về tiếng Anh. Với model multilingual hoặc bge-m3, vector thường phù hợp hơn.
Không dùng hybrid khi truy vấn cần khớp chính xác mã hoặc thuật ngữ; pure BM25 nhanh và dễ giải thích hơn. Pure vector phù hợp cho câu hỏi diễn đạt đa dạng khi embedding model hỗ trợ tốt ngôn ngữ của dữ liệu.
---

## Điều ngạc nhiên nhất khi làm lab này

Điều ngạc nhiên nhất là máy vẫn có thể tìm đúng tài liệu dù câu hỏi không dùng đúng từ khóa trong bài. Em cũng bất ngờ khi kết hợp tìm kiếm từ khóa và tìm kiếm theo ý nghĩa lại cho kết quả tốt hơn.

---

## Bonus challenge

- [x] Đã làm bonus (xem `bonus/`)
- [ ] Pair work với: _<tên đồng đội nếu có>_
