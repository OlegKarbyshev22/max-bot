import json
from datetime import datetime
from pathlib import Path

from agent.src.logging.models import AgentTrace


class AgentLogger:
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def save_batch(self, traces: list[AgentTrace]) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = (self.log_dir/ f"run_{timestamp}.json")

        # На случай двух запусков в одну секунду
        counter = 1

        while file_path.exists():
            file_path = (self.log_dir / f"run_{timestamp}_{counter}.json")
            counter += 1

        results = []
        for trace in traces:
            item = trace.model_dump(mode="json", by_alias=True)
            # Keep operational routing/gate data, but never persist free-form
            # user text or generated text that may contain personal details.
            item["question"] = "[redacted]"
            item["question_spec"] = {"entities": {}}
            if item.get("outcome"):
                item["outcome"]["user_message"] = None
            results.append(item)

        payload = {
            "schema": "course_agent_batch_v1",
            "questions_count": len(traces),
            "results": results,
        }

        with file_path.open("x", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2,)
        return file_path
