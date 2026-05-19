from urllib.parse import parse_qs, urlparse

from app.config import Settings
from app.services.deepgram_streaming_service import DeepgramStreamingService


def test_stream_url_uses_patient_endpointing_window():
    service = DeepgramStreamingService(
        Settings(
            deepgram_api_key="test-key",
            deepgram_endpointing_ms=3000,
        )
    )

    url = service._stream_url(sample_rate=16000)
    query = parse_qs(urlparse(url).query)

    assert query["endpointing"] == ["3000"]
    assert query["interim_results"] == ["true"]
    assert query["vad_events"] == ["true"]
