import json
import os
from typing import List, Dict, Any
from datetime import datetime

RAW_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "raw-data")

# ---------------------------------------------------------------------------
# Tool #1: search_product_catalog
# TODO: Hoàn thiện hàm này — đọc file product_catalog.json, lọc theo category và max_price.
# ---------------------------------------------------------------------------

def search_product_catalog(
    category: str,
    max_price: int = 999999999999
) -> List[Dict[str, Any]]:
    """Đọc danh mục và trả về sản phẩm đúng loại, trong ngân sách."""

    # 1. Xác định đường dẫn tới file dữ liệu.
    catalog_file = os.path.join(
        RAW_DATA_DIR,
        "product_catalog.json"
    )

    # 2. Kiểm tra file có tồn tại không.
    if not os.path.exists(catalog_file):
        return [{"error": "Không tìm thấy file danh mục sản phẩm."}]

    # 3. Đọc JSON thành danh sách Python.
    with open(catalog_file, "r", encoding="utf-8") as f:
        products = json.load(f)

    # 4. Lọc các sản phẩm phù hợp.
    results = []

    for product in products:
        same_category = (
            product["category"].lower() == category.lower()
        )
        within_budget = product["price_vnd"] <= max_price

        if same_category and within_budget:
            results.append(product)

    # 5. Trả về danh sách sau khi đã kiểm tra hết sản phẩm.
    return results


# ---------------------------------------------------------------------------
# Tool #2: submit_support_ticket
# TODO: Hoàn thiện hàm này — tạo ticket mới và lưu vào support_tickets.json.
# ---------------------------------------------------------------------------
def submit_support_ticket(
    customer_name: str,
    issue_description: str,
    priority: str = "medium"
) -> Dict[str, Any]:
    """Tạo phiếu hỗ trợ và lưu vào danh sách ticket."""

    # 1. Xác định file lưu ticket.
    tickets_file = os.path.join(
        RAW_DATA_DIR,
        "support_tickets.json"
    )

    # 2. Đọc danh sách ticket hiện có.
    existing_tickets = []

    if os.path.exists(tickets_file):
        with open(tickets_file, "r", encoding="utf-8") as f:
            existing_tickets = json.load(f)

    # 3. Tạo mã ticket theo ngày và số thứ tự.
    now = datetime.now().astimezone()
    today = now.strftime("%Y%m%d")
    seq = len(existing_tickets) + 1
    ticket_id = f"TK-{today}-{seq:03d}"

    # 4. Tạo thông tin ticket mới.
    new_ticket = {
        "ticket_id": ticket_id,
        "customer_name": customer_name,
        "issue_description": issue_description,
        "priority": priority.lower(),
        "status": "open",
        "created_at": now.isoformat(),
        "category": "general"
    }

    # 5. Thêm ticket mới vào danh sách.
    existing_tickets.append(new_ticket)

    # 6. Lưu cả danh sách vào file.
    with open(tickets_file, "w", encoding="utf-8") as f:
        json.dump(
            existing_tickets,
            f,
            indent=2,
            ensure_ascii=False
        )

    # 7. Trả thông tin ticket vừa tạo.
    return new_ticket


# ---------------------------------------------------------------------------
# TOOL_DEFINITIONS — JSON Schemas mô tả cho LLM
# TODO: Định nghĩa JSON Schema cho từng tool (name, description, parameters).
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "name": "search_product_catalog",
        "description": (
            "Tra cứu sản phẩm và dịch vụ Vingroup "
            "theo danh mục và giá tối đa."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": (
                        "Danh mục sản phẩm: xe_dien cho xe điện "
                        "VinFast, du_lich cho dịch vụ Vinpearl."
                    ),
                    "enum": ["xe_dien", "du_lich"]
                },
                "max_price": {
                    "type": "integer",
                    "description": "Giá tối đa tính bằng đồng Việt Nam.",
                    "minimum": 0
                }
            },
            "required": ["category"]
        }
    },
    {
        "name": "submit_support_ticket",
        "description": (
            "Tạo và lưu phiếu hỗ trợ khi khách hàng "
            "yêu cầu ghi nhận sự cố hoặc phản hồi."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "Họ và tên khách hàng."
                },
                "issue_description": {
                    "type": "string",
                    "description": "Mô tả sự cố hoặc nội dung cần hỗ trợ."
                },
                "priority": {
                    "type": "string",
                    "description": (
                        "Mức độ ưu tiên: low là thấp, "
                        "medium là trung bình, high là cao."
                    ),
                    "enum": ["low", "medium", "high"]
                }
            },
            "required": [
                "customer_name",
                "issue_description"
            ]
        }
    }
]


# ---------------------------------------------------------------------------
# TOOL_MAP — Ánh xạ tên tool → hàm thực thi
# ---------------------------------------------------------------------------

TOOL_MAP = {
    "search_product_catalog": search_product_catalog,
    "submit_support_ticket": submit_support_ticket
}
