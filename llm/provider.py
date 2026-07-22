"""LLM provider abstraction — Anthropic ve Gemini arası geçiş.

Kullanım:
  from llm.provider import generate

  text = generate(
      system="Sen bir Türk hukuk uzmanısın...",
      user="İcra takibinde emekli maaşı haczedilebilir mi?",
      provider="anthropic",  # veya "gemini" veya None (default)
      max_tokens=1500,
  )

API key'ler .env dosyasından okunur.
"""
from __future__ import annotations
import os
import sys
from typing import Literal

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

Provider = Literal["anthropic", "gemini"]


def _get_default_provider() -> Provider:
    p = (os.environ.get("LLM_DEFAULT_PROVIDER") or "anthropic").lower()
    return "anthropic" if p == "anthropic" else "gemini"


def _anthropic_call(system: str, user: str, max_tokens: int,
                    model: str | None = None,
                    temperature: float = 0.3) -> str:
    import anthropic
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY yok. .env dosyasına ekle.")
    client = anthropic.Anthropic(api_key=api_key)
    model = model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    parts = []
    for block in msg.content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return "".join(parts).strip()


def _gemini_call(system: str, user: str, max_tokens: int,
                 model: str | None = None,
                 temperature: float = 0.3) -> str:
    import google.generativeai as genai
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY yok. .env dosyasına ekle.")
    genai.configure(api_key=api_key)
    model_name = model or os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
    gen_model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system,
    )
    response = gen_model.generate_content(
        user,
        generation_config=genai.types.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
        ),
    )
    return (response.text or "").strip()


def generate(
    system: str,
    user: str,
    *,
    provider: Provider | None = None,
    max_tokens: int = 1500,
    temperature: float = 0.3,
    model: str | None = None,
    fallback: bool = True,
) -> str:
    """LLM çağrısı. provider None ise default seçilir.

    fallback=True ise birincil sağlayıcı başarısız olursa diğerine geçer.
    """
    primary = provider or _get_default_provider()
    secondary: Provider = "gemini" if primary == "anthropic" else "anthropic"

    callers = {
        "anthropic": _anthropic_call,
        "gemini": _gemini_call,
    }

    try:
        return callers[primary](system, user, max_tokens, model, temperature)
    except Exception as e:
        if not fallback:
            raise
        print(f"[LLM] {primary} hatası: {e}; {secondary}'a fallback",
              file=sys.stderr)
        return callers[secondary](system, user, max_tokens, None, temperature)


def is_available(provider: Provider | None = None) -> bool:
    """API key'ı set edilmiş mi kontrol et — UI'da uyarı için.

    Belirli bir provider istenmediyse (None), `generate()`'in davranışıyla
    tutarlı olarak İKİ sağlayıcıdan HERHANGİ biri yeterlidir — `generate()`
    birincil başarısız olursa otomatik ikinciye düşer. Yalnızca varsayılan
    sağlayıcının key'ine bakmak, ikinci sağlayıcı yapılandırılmışken bile
    yanlışlıkla "demo modu"na düşülmesine yol açıyordu.
    """
    if provider is not None:
        if provider == "anthropic":
            return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
        return bool(os.environ.get("GOOGLE_API_KEY", "").strip())
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip()) or bool(
        os.environ.get("GOOGLE_API_KEY", "").strip()
    )


def status() -> dict:
    """UI'da göstermek için providers durum özeti."""
    return {
        "default": _get_default_provider(),
        "anthropic": is_available("anthropic"),
        "gemini": is_available("gemini"),
    }


# -----------------------------------------------------------------------------
# Streaming — token-token üretim (SSE endpoint'leri için)
# -----------------------------------------------------------------------------

def _anthropic_stream(system: str, user: str, max_tokens: int,
                      model: str | None = None,
                      temperature: float = 0.3):
    """Anthropic streaming — text delta'ları yield eder."""
    import anthropic
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY yok. .env dosyasına ekle.")
    client = anthropic.Anthropic(api_key=api_key)
    model = model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        for text in stream.text_stream:
            if text:
                yield text


def _gemini_stream(system: str, user: str, max_tokens: int,
                   model: str | None = None,
                   temperature: float = 0.3):
    """Gemini streaming — text delta'ları yield eder."""
    import google.generativeai as genai
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY yok. .env dosyasına ekle.")
    genai.configure(api_key=api_key)
    model_name = model or os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
    gen_model = genai.GenerativeModel(
        model_name=model_name, system_instruction=system,
    )
    response = gen_model.generate_content(
        user,
        generation_config=genai.types.GenerationConfig(
            max_output_tokens=max_tokens, temperature=temperature,
        ),
        stream=True,
    )
    for chunk in response:
        text = getattr(chunk, "text", "") or ""
        if text:
            yield text


def generate_stream(
    system: str,
    user: str,
    *,
    provider: Provider | None = None,
    max_tokens: int = 1500,
    temperature: float = 0.3,
    model: str | None = None,
    fallback: bool = True,
):
    """Streaming LLM çağrısı — text parçalarını yield eder.

    İlk parça gelmeden hata olursa fallback sağlayıcıya geçer; ilk parçadan
    SONRA hata olursa exception yükselir (yarım çıktı + fallback karışmasın).
    """
    primary = provider or _get_default_provider()
    secondary: Provider = "gemini" if primary == "anthropic" else "anthropic"
    streamers = {"anthropic": _anthropic_stream, "gemini": _gemini_stream}

    started = False
    try:
        for piece in streamers[primary](system, user, max_tokens, model, temperature):
            started = True
            yield piece
        return
    except Exception as e:
        if started or not fallback:
            raise
        print(f"[LLM] {primary} stream hatası: {e}; {secondary}'a fallback",
              file=sys.stderr)
    for piece in streamers[secondary](system, user, max_tokens, None, temperature):
        yield piece
