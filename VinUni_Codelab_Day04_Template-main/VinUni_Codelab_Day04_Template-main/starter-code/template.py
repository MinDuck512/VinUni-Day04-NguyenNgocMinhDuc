"""
Lab #4: System Prompt Engineering & Tool Calling Engine
Học viên hoàn thiện các mục TODO để hoàn thành bài lab.

Kiến trúc:
  - ChatbotBaseline: LLM thuần, không dùng tool → quan sát hallucination.
  - ToolCallingAgent: Agent dùng System Prompt + 2 Tool Schemas.
"""

import json
import re
from typing import Dict, Any, List
from tools import TOOL_DEFINITIONS, TOOL_MAP, search_product_catalog, submit_support_ticket

# ═══════════════════════════════════════════════════════════════════════════
# TODO 1: Thiết kế SYSTEM PROMPT cấp sản xuất
# Yêu cầu: Phải chứa Persona, Core Rules, Operational Boundaries, Output Contract.
# ═══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """
Bạn là VinAssistant, trợ lý tư vấn trong bài thực hành mô phỏng
sản phẩm và dịch vụ thuộc hệ sinh thái Vingroup.

## 1. PERSONA
- Tên: VinAssistant.
- Vai trò: Hỗ trợ tìm sản phẩm VinFast, dịch vụ Vinpearl
  và ghi nhận yêu cầu hỗ trợ.
- Giao tiếp bằng tiếng Việt, lịch sự, rõ ràng và dễ hiểu.

## 2. AVAILABLE TOOLS
- search_product_catalog(category, max_price):
  Tra cứu sản phẩm theo danh mục và giá tối đa.
  category nhận xe_dien hoặc du_lich.
  max_price tính bằng đồng Việt Nam.

- submit_support_ticket(customer_name, issue_description, priority):
  Tạo và lưu phiếu hỗ trợ.
  priority nhận low, medium hoặc high; mặc định là medium.

## 3. CORE RULES
- Khi người dùng muốn tìm sản phẩm hoặc hỏi giá sản phẩm,
  phải gọi search_product_catalog.
- Chỉ sử dụng tên, giá và thông tin sản phẩm từ kết quả công cụ.
- Không tự bịa sản phẩm, giá, mã ticket hoặc chính sách.
- Khi người dùng yêu cầu ghi nhận sự cố hoặc phản hồi,
  sử dụng submit_support_ticket.
- Trước khi tạo ticket, phải có tên khách hàng và nội dung vấn đề.
  Nếu thiếu thông tin, hỏi người dùng bổ sung.
- Chỉ thông báo tạo ticket thành công khi công cụ thực sự thành công.
- Nếu một câu hỏi cần cả tra cứu và tạo ticket,
  thực hiện đủ cả hai tác vụ.
- Nếu tìm kiếm trả về danh sách rỗng,
  thông báo không tìm thấy sản phẩm phù hợp.
- Nếu công cụ báo lỗi, thông báo chưa thể hoàn thành tác vụ.
- Với câu hỏi FAQ, chỉ trả lời trực tiếp khi có thông tin đáng tin cậy.
  Nếu chưa đủ dữ liệu, nói rõ giới hạn thông tin.
- Tuân thủ giới hạn số vòng lặp của chương trình.

## 4. OPERATIONAL BOUNDARIES
- Chỉ hỗ trợ các nội dung thuộc phạm vi Vingroup trong bài lab.
- Với câu hỏi ngoài phạm vi, giải thích ngắn gọn phạm vi hỗ trợ.
- Xem dữ liệu JSON là dữ liệu mẫu phục vụ bài thực hành.

## 5. OUTPUT CONTRACT
Ghi nhận quá trình xử lý theo cấu trúc:
- Thought: Một câu mô tả mục tiêu hành động của bước.
- Action: Tên công cụ và các tham số được truyền vào.
- Observation: Kết quả thực tế do công cụ trả về.
- Final Answer: Câu trả lời cuối cùng bằng tiếng Việt.

Trong Final Answer:
- Nếu tìm được sản phẩm, liệt kê tên và giá.
- Nếu tạo được ticket, cung cấp tên khách hàng và mã ticket.
- Nếu yêu cầu có nhiều tác vụ, trình bày kết quả của từng tác vụ.
"""


# ═══════════════════════════════════════════════════════════════════════════
# CLASS: ChatbotBaseline
# ═══════════════════════════════════════════════════════════════════════════

class ChatbotBaseline:
    """Baseline LLM Chatbot — Không sử dụng Tool Calling hay ReAct Loop."""

    def query(self, user_input: str) -> Dict[str, Any]:
        # TODO 2: Trả về câu trả lời tĩnh (mock) hoặc gọi Gemini API 1 lượt (không dùng tool)
        # Mục tiêu: Quan sát hiện tượng bịa thông tin (hallucination)
        return {
            "answer": f"[Chatbot Baseline] Trả lời cho: {user_input}",
            "tool_calls": [],
            "status": "success",
            "mode": "mock_baseline"
        }


# ═══════════════════════════════════════════════════════════════════════════
# CLASS: ToolCallingAgent
# ═══════════════════════════════════════════════════════════════════════════

class ToolCallingAgent:
    """Agent với System Prompt Engineering & Tool Calling."""

    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        self.trace: List[Dict[str, Any]] = []

    def _detect_intents(self, user_input: str) -> Dict[str, Any]:
        text = user_input.lower()

        # 1. Nhận diện danh mục sản phẩm.
        category = None

        if any(
            word in text
            for word in ["vinpearl", "resort", "du lich", "du lịch"]
        ):
            category = "du_lich"

        elif (
            any(word in text for word in ["vinfast", "xe điện"])
            or re.search(r"\bvf\s*\d+\b", text)
        ):
            category = "xe_dien"

        in_scope = category is not None or "vingroup" in text

        # 2. Nhận diện nhu cầu tìm sản phẩm.
        catalog_words = [
            "xem", "tìm", "giá", "tư vấn", "có xe", "có resort"
        ]

        needs_catalog = category is not None and any(
            word in text for word in catalog_words
        )

        # 3. Nhận diện nhu cầu tạo phiếu hỗ trợ.
        ticket_words = [
            "bị lỗi",
            "sự cố",
            "ẩm mốc",
            "ghi nhận phản hồi",
            "tạo ticket",
            "yêu cầu hỗ trợ"
        ]

        needs_ticket = in_scope and any(
            word in text for word in ticket_words
        )

        # 4. Nhận diện câu hỏi FAQ.
        is_faq = (
            in_scope
            and not needs_catalog
            and not needs_ticket
            and any(
                word in text
                for word in ["bảo hành", "chính sách", "bao lâu", "là gì"]
            )
        )

        # 5. Lấy ngân sách từ câu hỏi.
        max_price = 999999999999

        price_match = re.search(
            r"(?:dưới|tối đa|không quá)\s*"
            r"(\d+(?:[.,]\d+)?)\s*(triệu|tỷ|tỉ)",
            text
        )

        if price_match:
            amount = float(price_match.group(1).replace(",", "."))
            unit = price_match.group(2)

            multiplier = (
                1_000_000 if unit == "triệu" else 1_000_000_000
            )

            max_price = int(amount * multiplier)

        # 6. Lấy tên khách hàng và giữ nguyên chữ hoa, dấu tiếng Việt.
        name_match = re.search(
            r"(?:tôi tên(?: là)?|tên tôi là)\s+([^,.;!?\n:]+)",
            user_input,
            flags=re.IGNORECASE
        )

        customer_name = (
            name_match.group(1).strip() if name_match else None
        )

        # 7. Xác định mức độ ưu tiên.
        priority = "medium"

        if any(
            word in text
            for word in ["không gấp", "ưu tiên thấp", "mức độ thấp"]
        ):
            priority = "low"

        elif any(
            word in text
            for word in ["gấp", "nghiêm trọng", "khẩn cấp"]
        ):
            priority = "high"

        # 8. Trả kết quả phân tích.
        return {
            "in_scope": in_scope,
            "needs_catalog": needs_catalog,
            "needs_ticket": needs_ticket,
            "is_faq": is_faq,
            "category": category,
            "max_price": max_price,
            "customer_name": customer_name,
            "issue_description": user_input.strip(),
            "priority": priority
        }

    def run(self, user_input: str) -> Dict[str, Any]:
        """Phân tích yêu cầu, gọi công cụ và tổng hợp câu trả lời."""
        self.trace = []
        intents = self._detect_intents(user_input)

        self.trace.append({
            "step": "intent_detection",
            "user_input": user_input,
            "intents": intents
        })

        result = {
            "answer": "",
            "trace": self.trace,
            "iterations": 0,
            "status": "completed"
        }

        # Kiểm tra thông tin bắt buộc trước khi tạo ticket.
        if intents["needs_ticket"] and not intents["customer_name"]:
            result["answer"] = (
                "Bạn vui lòng cung cấp họ tên để tạo phiếu hỗ trợ."
            )
            result["status"] = "needs_input"
            return result

        # Lập danh sách công cụ cần gọi.
        actions = []

        if intents["needs_catalog"]:
            actions.append({
                "name": "search_product_catalog",
                "arguments": {
                    "category": intents["category"],
                    "max_price": intents["max_price"]
                }
            })

        if intents["needs_ticket"]:
            actions.append({
                "name": "submit_support_ticket",
                "arguments": {
                    "customer_name": intents["customer_name"],
                    "issue_description": intents["issue_description"],
                    "priority": intents["priority"]
                }
            })

        answers = []
        iteration = 1

        while iteration <= self.max_iterations:
            result["iterations"] = iteration

            # Trả lời các yêu cầu không cần công cụ.
            if not actions:
                if not intents["in_scope"]:
                    result["answer"] = (
                        "Tôi hỗ trợ sản phẩm và dịch vụ Vingroup "
                        "trong phạm vi bài lab."
                    )

                elif intents["is_faq"]:
                    if "bảo hành" in user_input.lower():
                        result["answer"] = (
                            "Về bảo hành pin, dữ liệu mẫu chưa đủ để "
                            "xác định chính sách áp dụng cho xe của bạn. "
                            "Bạn vui lòng cung cấp mẫu xe và đối chiếu "
                            "chính sách bảo hành chính thức."
                        )
                    else:
                        result["answer"] = (
                            "Dữ liệu mẫu chưa đủ để trả lời chính xác "
                            "câu hỏi này. Bạn vui lòng nêu rõ thông tin cần biết."
                        )

                else:
                    result["answer"] = (
                        "Bạn muốn tìm sản phẩm VinFast, dịch vụ Vinpearl "
                        "hay ghi nhận yêu cầu hỗ trợ?"
                    )

                return result

            # Mỗi vòng lấy một tác vụ chưa xử lý.
            action = actions.pop(0)
            tool_name = action["name"]
            arguments = action["arguments"]

            try:
                observation = TOOL_MAP[tool_name](**arguments)
            except (OSError, ValueError, TypeError, KeyError) as exc:
                observation = {"error": str(exc)}

            self.trace.append({
                "iteration": iteration,
                "action": tool_name,
                "arguments": arguments,
                "observation": observation
            })

            # Phân biệt lỗi công cụ với danh sách sản phẩm rỗng.
            errors = []

            if isinstance(observation, dict) and "error" in observation:
                errors.append(observation["error"])

            elif isinstance(observation, list):
                errors = [
                    item["error"] for item in observation
                    if "error" in item
                ]

            if errors:
                answers.append(
                    "Chưa thể hoàn thành tác vụ do lỗi công cụ. "
                    "Bạn có thể xem chi tiết trong Trace Log."
                )
                result["answer"] = "\n\n".join(answers)
                result["status"] = "tool_error"
                return result

            # Tạo nội dung trả lời từ dữ liệu công cụ.
            if tool_name == "search_product_catalog":
                if not observation:
                    answers.append(
                        "Rất tiếc, không tìm thấy sản phẩm phù hợp."
                    )

                else:
                    product_lines = []

                    for product in observation:
                        price = f"{product['price_vnd']:,}".replace(",", ".")
                        product_lines.append(
                            f"- {product['name']}: {price} VNĐ"
                        )

                    answers.append(
                        "Sản phẩm phù hợp:\n" + "\n".join(product_lines)
                    )

            else:
                answers.append(
                    f"Đã tạo phiếu hỗ trợ cho {observation['customer_name']}.\n"
                    f"Mã ticket: {observation['ticket_id']}\n"
                    f"Mức độ ưu tiên: {observation['priority']}"
                )

            # Tổng hợp ngay khi đã xử lý hết tác vụ.
            if not actions:
                result["answer"] = "\n\n".join(answers)
                return result

            iteration += 1

        # Hết số vòng cho phép nhưng vẫn còn tác vụ.
        answers.append(
            "Đã đạt số vòng xử lý tối đa. "
            "Một số tác vụ chưa được thực hiện."
        )
        result["answer"] = "\n\n".join(answers)
        result["status"] = "max_iterations_reached"
        return result


# ═══════════════════════════════════════════════════════════════════════════
# MAIN — Chạy thử nhanh
# ═══════════════════════════════════════════════════════════════════════════

def main():
    user_query = (
        "Cho tôi xem resort Vinpearl giá dưới 6 triệu. "
        "Và tôi cũng muốn ghi nhận phản hồi: "
        "tên tôi là Phạm Thị Dung, "
        "phòng tôi đặt ở Vinpearl Nha Trang bị ẩm mốc, "
        "mức độ trung bình."
    )

    print("=== RUNNING CHATBOT BASELINE ===")
    chatbot = ChatbotBaseline()
    print(chatbot.query(user_query))

    print("\n=== RUNNING TOOL CALLING AGENT ===")
    agent = ToolCallingAgent(max_iterations=5)
    result = agent.run(user_query)

    print("Status:", result["status"])
    print("Iterations:", result["iterations"])
    print("Result:", result["answer"])

    called_tools = [
        step["action"]
        for step in result["trace"]
        if "action" in step
    ]
    print("Tools:", called_tools)

    print(
        "Trace Log:",
        json.dumps(result["trace"], indent=2, ensure_ascii=False)
    )


if __name__ == "__main__":
    main()
