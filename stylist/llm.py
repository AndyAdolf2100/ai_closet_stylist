import json
from pathlib import Path

import httpx
from pydantic import ValidationError

from .errors import StylistError


class LanguageModel:
    def __init__(self, settings, transport=None):
        self.settings, self.transport = settings, transport

    async def generate(self, prompt_name, payload, result_type):
        settings = self.settings
        if not (settings.llm_key and settings.llm_model and settings.llm_url):
            raise StylistError("llm_not_configured", "搭配模型尚未配置。")
        instructions = Path(__file__).with_name("prompts").joinpath(prompt_name + ".md").read_text()
        if prompt_name == "plan":
            from .models import Task
            instructions += "\nchanges每项value必须符合对应Task字段的类型与范围：\n" + json.dumps(Task.model_json_schema(), ensure_ascii=False)
        messages = [
            {"role": "system", "content": instructions + "\n输出必须是符合以下结构的JSON对象：\n" +
             json.dumps(result_type.model_json_schema(), ensure_ascii=False)},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
        ]
        async with httpx.AsyncClient(timeout=settings.llm_timeout, trust_env=False,
                                     transport=self.transport) as client:
            for attempt in range(2):
                try:
                    body = {"model": settings.llm_model, "messages": messages, "temperature": 0.3,
                            "max_completion_tokens": 6000, "response_format": {"type": "json_object"}}
                    if "volces.com" in settings.llm_url:
                        body["thinking"] = {"type": "disabled"}
                    response = await client.post(settings.llm_url + "/chat/completions",
                        headers={"Authorization": f"Bearer {settings.llm_key}"},
                        json=body)
                    response.raise_for_status()
                    value = response.json()["choices"][0]["message"]["content"]
                    if not isinstance(value, str):
                        raise ValueError("content_missing")
                    return result_type.model_validate_json(value)
                except (ValidationError, ValueError, KeyError, IndexError, TypeError):
                    if attempt == 0:
                        messages.append({"role": "user", "content": "上一次返回未通过结构校验。请重新输出完整JSON；不执行任何操作。"})
                        continue
                    raise StylistError("model_output_invalid", "这次没能把建议整理完整，可以再发一次。刚才的需求不用改，衣衣会重新帮你看看。") from None
                except httpx.TimeoutException:
                    raise StylistError("model_timeout", "这次模型整理超时，原需求已保留，请稍后重试。") from None
                except httpx.HTTPStatusError as exc:
                    raise StylistError(f"model_http_{exc.response.status_code}", "搭配模型暂时未能完成请求，原需求已保留。") from None
                except httpx.HTTPError:
                    raise StylistError("model_unavailable", "搭配模型暂时连接失败，原需求已保留，请稍后重试。") from None

    async def check(self):
        from pydantic import BaseModel

        class Ping(BaseModel):
            ok: bool

        value = await self.generate("check", {"request": "返回 {\"ok\":true}"}, Ping)
        if not value.ok:
            raise StylistError("model_check_failed", "模型响应未通过检查。")
        return {"interface": "LLM /chat/completions", "status": "ok", "code": "ok"}
