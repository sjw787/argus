"""Tests for the Lambda handler (Mangum wrapper)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_lambda_handler_is_callable():
    """The module-level handler must be callable."""
    from argus.lambda_handler import handler

    assert callable(handler)


def test_lambda_handler_responds_to_api_gateway_event():
    """End-to-end: handler processes a minimal API Gateway v1 proxy event."""
    from argus.lambda_handler import handler

    event = {
        "version": "1.0",
        "httpMethod": "GET",
        "path": "/api/v1/auth/config",
        "headers": {"Host": "example.execute-api.us-east-1.amazonaws.com"},
        "multiValueHeaders": {},
        "queryStringParameters": None,
        "multiValueQueryStringParameters": None,
        "body": None,
        "isBase64Encoded": False,
        "requestContext": {
            "resourcePath": "/api/v1/auth/config",
            "httpMethod": "GET",
            "path": "/api/v1/auth/config",
            "stage": "prod",
            "requestId": "test-request-id",
            "identity": {"sourceIp": "127.0.0.1"},
        },
    }
    context = MagicMock()
    context.aws_request_id = "test-request-id"
    context.function_name = "argus"
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123:function:argus"
    context.get_remaining_time_in_millis.return_value = 30000

    response = handler(event, context)

    assert "statusCode" in response
    assert response["statusCode"] == 200


def test_lambda_handler_uses_mangum_with_lifespan_off():
    """The handler must be initialised with lifespan='off'."""
    import importlib
    import argus.lambda_handler as lh

    with patch("mangum.Mangum") as MockMangum:
        MockMangum.return_value = MagicMock()
        importlib.reload(lh)

    MockMangum.assert_called_once()
    _, kwargs = MockMangum.call_args
    assert kwargs.get("lifespan") == "off"
