"""Yapısal loglama + istek korelasyon kimliği (request ID).

NEDEN
-----
Eskiden loglar düz metindi ve hiçbir korelasyon kimliği taşımıyordu. Bir
kullanıcı "dilekçe üretemiyorum" dediğinde; o isteğe ait DB hatasını, LLM
çağrısını, audit kaydını ve Sentry olayını birbirine bağlayacak ortak bir
anahtar yoktu — sorun giderme log greplemeye kalıyordu.

NE YAPAR
--------
1. Her isteğe bir `request_id` atar (istemci `X-Request-Id` gönderdiyse onu
   kullanır — Next.js proxy'si üzerinden uçtan uca izleme mümkün olur).
2. Bu kimliği `contextvars` ile o isteğin tüm log satırlarına otomatik ekler;
   kod tarafında hiçbir şey değiştirmek gerekmez (`log.info(...)` yeterli).
3. Yanıta `X-Request-Id` header'ı koyar — kullanıcı hata bildirirken bu
   kimliği paylaşabilir.
4. Sentry kuruluysa kimliği tag olarak işler.

LOG_FORMAT=json  → Cloud Logging'in alan bazlı sorgulayabildiği JSON çıktı
                   (jsonPayload.request_id ile filtreleme). Prod için önerilen.
LOG_FORMAT=text  → insan okuyabilir düz metin (varsayılan; lokal geliştirme).
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from contextvars import ContextVar

from fastapi import Request

#: O anki isteğin korelasyon kimliği. Arka plan görevlerinde boş kalır.
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

#: Log satırına eklenmeyecek standart LogRecord alanları.
_STD_ATTRS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "taskName", "message", "asctime",
}


class RequestIdFilter(logging.Filter):
    """Her log kaydına o anki request_id'yi iliştirir."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


class JsonFormatter(logging.Formatter):
    """Cloud Logging uyumlu tek satırlık JSON çıktı."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            # Cloud Logging bu iki alanı özel olarak yorumlar
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # log.info("...", extra={"tenant_id": ...}) ile gelen ek alanlar
        for k, v in record.__dict__.items():
            if k not in _STD_ATTRS and k not in payload and not k.startswith("_"):
                try:
                    json.dumps(v)
                    payload[k] = v
                except (TypeError, ValueError):
                    payload[k] = str(v)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    """Kök logger'ı yapılandır. `api.main` import edilirken bir kez çağrılır."""
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    fmt = os.environ.get("LOG_FORMAT", "text").lower()

    handler = logging.StreamHandler()
    handler.addFilter(RequestIdFilter())
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] [%(request_id)s] %(name)s: %(message)s"
        ))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Gürültü azaltma
    logging.getLogger("uvicorn.access").setLevel(
        os.environ.get("UVICORN_ACCESS_LOG_LEVEL", "WARNING").upper()
    )


def new_request_id(request: Request) -> str:
    """İstemciden gelen X-Request-Id'yi kullan, yoksa üret.

    Dışarıdan gelen değeri kısıtlıyoruz: log enjeksiyonuna ve sınırsız uzun
    değerlere karşı yalnızca güvenli karakterler ve 64 hane kabul edilir.
    """
    incoming = (request.headers.get("x-request-id") or "").strip()
    if incoming:
        safe = "".join(c for c in incoming if c.isalnum() or c in "-_")[:64]
        if safe:
            return safe
    return uuid.uuid4().hex[:16]
