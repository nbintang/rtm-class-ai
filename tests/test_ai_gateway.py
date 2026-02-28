from src.ai.gateway import AIGateway, EchoProvider


def test_ai_gateway_echo_provider() -> None:
    gateway = AIGateway(provider=EchoProvider())
    result = gateway.generate("Hello class")
    assert "Hello class" in result

