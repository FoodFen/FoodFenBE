"""seed the first quiz topics and questions (Vietnamese)

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-03
"""
from __future__ import annotations

import json
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NS = uuid.UUID("6f1d0e2a-3b4c-4d5e-8f60-7a8b9c0d1e2f")

# slug -> (label, [(question, [option a, b, c, d], correct letter, explanation)])
_SEED = {
    "macros": (
        "Đạm, tinh bột và chất béo",
        [
            ("1 gam chất đạm (protein) cung cấp khoảng bao nhiêu kcal?",
             ["2 kcal", "4 kcal", "7 kcal", "9 kcal"], "b",
             "Chất đạm và tinh bột đều cho khoảng 4 kcal mỗi gam, còn chất béo cho khoảng 9 kcal mỗi gam."),
            ("Trong ba nhóm chất sinh năng lượng chính, nhóm nào cho nhiều kcal nhất trên mỗi gam?",
             ["Chất đạm", "Tinh bột", "Chất béo", "Nước"], "c",
             "Chất béo cho khoảng 9 kcal mỗi gam, hơn gấp đôi chất đạm hoặc tinh bột (khoảng 4 kcal mỗi gam)."),
            ("Món nào sau đây là nguồn đạm thực vật?",
             ["Đậu phụ", "Thịt gà", "Cá hồi", "Trứng"], "a",
             "Đậu phụ làm từ đậu nành nên là nguồn đạm thực vật; thịt gà, cá hồi và trứng là đạm động vật."),
            ("Não bộ dùng chất nào làm nguồn năng lượng chính?",
             ["Cholesterol", "Canxi", "Vitamin C", "Glucose"], "d",
             "Não chủ yếu dùng glucose, có từ tinh bột và đường trong thức ăn, làm nhiên liệu."),
            ("Loại chất béo nào nên hạn chế nhất?",
             ["Chất béo không bão hòa trong dầu ô liu", "Omega-3 trong cá hồi",
              "Chất béo chuyển hóa (trans) trong đồ chiên rán công nghiệp", "Chất béo trong quả bơ"], "c",
             "Chất béo chuyển hóa làm tăng cholesterol xấu và nguy cơ bệnh tim mạch, nên hạn chế càng nhiều càng tốt."),
            ("Gạo lứt khác gạo trắng ở điểm nào?",
             ["Không chứa tinh bột", "Còn lớp cám nên nhiều chất xơ hơn", "Có nhiều chất béo hơn hẳn", "Không có vitamin"], "b",
             "Gạo lứt giữ lại lớp cám nên có nhiều chất xơ, vitamin nhóm B và khoáng chất hơn gạo trắng."),
            ("Vai trò chính của chất đạm trong cơ thể là gì?",
             ["Xây dựng và sửa chữa mô như cơ bắp", "Dự trữ vitamin", "Cung cấp chất xơ", "Làm giảm huyết áp trực tiếp"], "a",
             "Chất đạm cung cấp axit amin để xây dựng và sửa chữa cơ bắp, da và nhiều mô khác."),
            ("Một bữa ăn 600 kcal có 30% năng lượng từ chất béo. Lượng kcal từ chất béo là bao nhiêu?",
             ["60 kcal", "120 kcal", "180 kcal", "300 kcal"], "c",
             "600 × 30% = 180 kcal, tương đương khoảng 20 g chất béo (180 ÷ 9)."),
            ("Thực phẩm nào sau đây giàu đạm nhất tính trên cùng 100 g?",
             ["Cơm trắng", "Chuối", "Khoai lang", "Ức gà nấu chín"], "d",
             "100 g ức gà nấu chín có khoảng 30 g đạm, trong khi cơm, chuối và khoai lang chỉ có vài gam hoặc ít hơn."),
            ("Axit béo omega-3 có nhiều trong thực phẩm nào?",
             ["Cá hồi và cá thu", "Kẹo", "Bánh quy", "Nước ngọt"], "a",
             "Cá béo như cá hồi, cá thu là nguồn omega-3 tốt, có lợi cho tim mạch."),
        ],
    ),
    "vitamins-minerals": (
        "Vitamin và khoáng chất",
        [
            ("Thiếu vitamin C trong thời gian dài có thể gây bệnh nào?",
             ["Còi xương", "Quáng gà", "Bệnh scorbut (chảy máu chân răng, vết thương lâu lành)", "Bướu cổ"], "c",
             "Vitamin C cần để tạo collagen; thiếu lâu ngày gây scorbut với các dấu hiệu như chảy máu chân răng và vết thương lâu lành."),
            ("Trẻ bị còi xương thường do thiếu chất nào?",
             ["Vitamin D (và canxi)", "Vitamin C", "Vitamin B12", "Sắt"], "a",
             "Vitamin D giúp hấp thu canxi; thiếu vitamin D và canxi làm xương mềm và biến dạng."),
            ("Vitamin nào giúp mắt nhìn tốt khi thiếu sáng và có nhiều trong cà rốt (dưới dạng beta-carotene)?",
             ["Vitamin B12", "Vitamin A", "Vitamin C", "Vitamin K"], "b",
             "Cơ thể chuyển beta-carotene trong cà rốt thành vitamin A; thiếu vitamin A gây quáng gà."),
            ("Khoáng chất nào cần thiết nhất cho xương và răng chắc khỏe?",
             ["Natri", "Kali", "Iốt", "Canxi"], "d",
             "Canxi là thành phần chính của xương và răng; sữa, cá nhỏ ăn cả xương và rau lá xanh đậm là nguồn tốt."),
            ("Thiếu iốt kéo dài có thể gây bệnh nào?",
             ["Bướu cổ và rối loạn tuyến giáp", "Scorbut", "Thiếu máu do thiếu sắt", "Loãng xương"], "a",
             "Iốt cần để tuyến giáp tạo hormone; muối ăn có bổ sung iốt giúp phòng bệnh này."),
            ("Sắt có vai trò chính nào trong cơ thể?",
             ["Làm xương chắc", "Tạo hemoglobin vận chuyển oxy trong máu", "Giúp đông máu", "Tăng hấp thu canxi"], "b",
             "Sắt là thành phần của hemoglobin; thiếu sắt gây thiếu máu, mệt mỏi và da xanh xao."),
            ("Cơ thể tự tổng hợp vitamin D khi da tiếp xúc với yếu tố nào?",
             ["Nước lạnh", "Tia UVB trong ánh nắng mặt trời", "Ánh sáng đèn huỳnh quang trong nhà", "Gió mát"], "b",
             "Da tạo vitamin D khi tiếp xúc với ánh nắng; chỉ cần tiếp xúc vừa phải và tránh để bị cháy nắng."),
            ("Vitamin B12 chủ yếu có trong nhóm thực phẩm nào?",
             ["Rau muống", "Gạo", "Thịt, cá, trứng, sữa", "Trái cây"], "c",
             "B12 gần như chỉ có trong thực phẩm nguồn động vật; người ăn thuần chay cần bổ sung hoặc dùng thực phẩm tăng cường."),
            ("Thực phẩm nào sau đây là nguồn kali tốt?",
             ["Chuối", "Muối ăn", "Đường cát", "Mỡ lợn"], "a",
             "Chuối, khoai lang và rau lá xanh giàu kali, giúp cân bằng natri và hỗ trợ huyết áp."),
            ("Theo khuyến nghị của WHO, người trưởng thành nên ăn dưới bao nhiêu gam muối mỗi ngày?",
             ["Dưới 1 g", "Dưới 5 g", "Dưới 10 g", "Dưới 15 g"], "b",
             "Dưới 5 g muối (khoảng 2 g natri) mỗi ngày giúp giảm nguy cơ tăng huyết áp và bệnh tim mạch."),
        ],
    ),
    "water-fiber": (
        "Nước và chất xơ",
        [
            ("Người trưởng thành nên ăn ít nhất khoảng bao nhiêu gam chất xơ mỗi ngày?",
             ["5 g", "10 g", "25 g", "60 g"], "c",
             "Khuyến nghị phổ biến là ít nhất khoảng 25 g chất xơ mỗi ngày, tương đương khoảng 14 g cho mỗi 1000 kcal."),
            ("Thực phẩm nào là nguồn chất xơ tốt?",
             ["Dầu ăn", "Đường cát", "Đậu xanh, đậu đen", "Nước ngọt"], "c",
             "Các loại đậu, ngũ cốc nguyên hạt, rau và trái cây nguyên quả đều giàu chất xơ."),
            ("Chất xơ giúp ích gì cho hệ tiêu hóa?",
             ["Hỗ trợ nhu động ruột và phòng táo bón", "Tiêu diệt mọi vi khuẩn trong ruột",
              "Thay thế hoàn toàn nước uống", "Làm dạ dày ngừng hoạt động"], "a",
             "Chất xơ làm tăng khối lượng phân và hỗ trợ nhu động ruột, giúp phòng táo bón."),
            ("Chất xơ hòa tan (có trong yến mạch, đậu) có thể giúp điều gì?",
             ["Làm đường huyết tăng nhanh", "Làm chậm hấp thu đường và giúp giảm cholesterol", "Phá hủy vitamin", "Làm da khô"], "b",
             "Chất xơ hòa tan tạo gel trong ruột, làm chậm hấp thu đường và hỗ trợ giảm cholesterol xấu."),
            ("Dấu hiệu nào cho thấy cơ thể có thể đang thiếu nước?",
             ["Nước tiểu trong suốt", "Dễ ngủ sâu", "Ăn ngon miệng hơn", "Nước tiểu màu vàng sẫm"], "d",
             "Nước tiểu vàng sẫm, khô miệng và khát là các dấu hiệu thường gặp của thiếu nước."),
            ("Nước chiếm khoảng bao nhiêu phần trăm cơ thể người trưởng thành?",
             ["Khoảng 20%", "Khoảng 40%", "Khoảng 60%", "Khoảng 90%"], "c",
             "Nước chiếm khoảng 50–65% cơ thể, tùy tuổi, giới tính và tỷ lệ mỡ."),
            ("Vì sao ăn nguyên quả thường tốt hơn uống nước ép trái cây?",
             ["Nước ép có nhiều chất xơ hơn", "Nguyên quả không có vitamin",
              "Nguyên quả giữ lại chất xơ và no lâu hơn", "Nước ép không bao giờ có đường"], "c",
             "Khi ép, phần lớn chất xơ bị loại bỏ nên nước ép dễ uống nhiều đường hơn và ít no hơn nguyên quả."),
            ("Đồ uống nào cần hạn chế vì chứa nhiều đường bổ sung?",
             ["Nước khoáng", "Nước ngọt có ga", "Trà không đường", "Nước lọc"], "b",
             "Nước ngọt có ga cho nhiều kcal từ đường mà gần như không có chất dinh dưỡng khác."),
            ("Nhu cầu uống nước thường tăng khi nào?",
             ["Khi trời nóng hoặc vận động nhiều", "Khi đang ngủ", "Khi ngồi trong phòng lạnh", "Không bao giờ thay đổi"], "a",
             "Ra mồ hôi nhiều làm mất nước, nên cần uống thêm khi trời nóng hoặc khi tập luyện."),
            ("Vì sao nên tăng lượng chất xơ từ từ?",
             ["Chất xơ gây ngộ độc", "Tăng đột ngột có thể gây đầy hơi, khó chịu",
              "Chất xơ làm mất toàn bộ canxi", "Không cần uống thêm nước"], "b",
             "Ruột cần thời gian thích nghi; hãy tăng dần và uống đủ nước để tránh đầy hơi và khó chịu."),
        ],
    ),
    "healthy-habits": (
        "Thói quen ăn uống lành mạnh",
        [
            ("WHO khuyến nghị ăn tối thiểu bao nhiêu gam rau và trái cây mỗi ngày?",
             ["100 g", "200 g", "400 g", "1000 g"], "c",
             "Ít nhất 400 g rau và trái cây mỗi ngày (khoảng 5 phần) giúp giảm nguy cơ bệnh mạn tính."),
            ("Trên nhãn thực phẩm, thành phần thường được liệt kê theo thứ tự nào?",
             ["Theo bảng chữ cái", "Giảm dần theo khối lượng", "Tăng dần theo giá", "Ngẫu nhiên"], "b",
             "Thành phần đứng đầu danh sách có khối lượng lớn nhất trong sản phẩm."),
            ("Khi đọc bảng dinh dưỡng, vì sao cần chú ý khẩu phần (serving size)?",
             ["Số liệu thường tính trên một khẩu phần, không phải cả gói", "Khẩu phần luôn là 100 g",
              "Khẩu phần không ảnh hưởng đến kcal", "Chỉ trẻ em mới cần xem"], "a",
             "Một gói có thể chứa nhiều khẩu phần, nên ăn cả gói là nhân số kcal lên tương ứng."),
            ("Ăn chậm, nhai kỹ giúp ích gì?",
             ["Làm ăn nhiều hơn", "Giúp nhận biết cảm giác no tốt hơn", "Làm giảm hấp thu vitamin", "Không có tác dụng gì"], "b",
             "Não cần một khoảng thời gian để nhận tín hiệu no, ăn chậm giúp tránh ăn quá nhiều."),
            ("Cách chế biến nào thường ít dầu mỡ nhất?",
             ["Chiên ngập dầu", "Rán giòn", "Xào nhiều mỡ", "Hấp hoặc luộc"], "d",
             "Hấp và luộc không cần thêm dầu mỡ nên giữ món ăn nhẹ và ít kcal hơn."),
            ("Khi đi chợ, nên ưu tiên chọn loại thực phẩm nào?",
             ["Thực phẩm tươi, ít qua chế biến", "Thực phẩm chế biến sẵn nhiều muối", "Đồ uống có đường", "Bánh kẹo đóng gói"], "a",
             "Thực phẩm tươi, nguyên dạng thường ít đường, muối và chất béo bổ sung hơn đồ chế biến sẵn."),
            ("WHO khuyến nghị đường bổ sung nên chiếm dưới bao nhiêu phần trăm năng lượng mỗi ngày?",
             ["Dưới 5%", "Dưới 10%", "Dưới 25%", "Dưới 40%"], "b",
             "Dưới 10% tổng năng lượng; giảm xuống dưới 5% còn mang lại lợi ích thêm."),
            ("Chế độ ăn cân bằng nên có đặc điểm nào?",
             ["Chỉ ăn một nhóm thực phẩm", "Đa dạng: tinh bột, đạm, rau, trái cây và chất béo tốt",
              "Bỏ hết tinh bột", "Chỉ ăn rau luộc"], "b",
             "Đa dạng nhóm thực phẩm giúp cung cấp đủ các chất dinh dưỡng."),
            ("Việc ghi lại bữa ăn hằng ngày giúp ích gì?",
             ["Làm tăng cân", "Thay thế bữa ăn", "Giúp thấy rõ lượng ăn thực tế và điều chỉnh thói quen", "Không có lợi ích nào"], "c",
             "Ghi lại bữa ăn giúp bạn nhận ra mình thực sự ăn bao nhiêu và điều chỉnh dần thói quen."),
            ("Bỏ bữa có thể dẫn tới điều gì?",
             ["Luôn giảm cân nhanh", "Không ảnh hưởng gì", "Tăng cơ bắp", "Dễ đói và ăn quá nhiều ở bữa sau"], "d",
             "Bỏ bữa có thể khiến bạn quá đói và ăn nhiều hơn ở bữa sau, nên khó kiểm soát lượng kcal."),
        ],
    ),
}

_UUID = postgresql.UUID(as_uuid=True)
_topics = sa.table(
    "quiz_topics", sa.column("id", _UUID), sa.column("slug", sa.String), sa.column("label", sa.String)
)
_questions = sa.table(
    "quiz_questions",
    sa.column("id", _UUID),
    sa.column("topic_id", _UUID),
    sa.column("text", sa.Text),
    sa.column("options", postgresql.JSON),
    sa.column("correct_option_id", sa.String),
    sa.column("explanation", sa.Text),
)


def upgrade() -> None:
    topic_rows, question_rows = [], []
    for slug, (label, questions) in _SEED.items():
        topic_id = uuid.uuid5(_NS, slug)
        topic_rows.append({"id": topic_id, "slug": slug, "label": label})
        for index, (text, options, correct, explanation) in enumerate(questions):
            question_rows.append(
                {
                    "id": uuid.uuid5(_NS, f"{slug}:{index}"),
                    "topic_id": topic_id,
                    "text": text,
                    # CAST: asyncpg binds a str as VARCHAR, which Postgres rejects for a json column, and
                    # `--sql` cannot render a JSON literal; a cast of a string works for both.
                    "options": sa.cast(
                        sa.literal(
                            json.dumps(
                                [{"id": "abcd"[i], "text": o} for i, o in enumerate(options)],
                                ensure_ascii=False,
                            ),
                            sa.Text,
                        ),
                        postgresql.JSON,
                    ),
                    "correct_option_id": correct,
                    "explanation": explanation,
                }
            )
    op.bulk_insert(_topics, topic_rows)
    for row in question_rows:  # insert(), not bulk_insert(): bulk_insert would not honour the CAST
        op.execute(_questions.insert().values(**row))


def downgrade() -> None:
    pass  # content is data: migration 0016's downgrade drops the tables it lives in
