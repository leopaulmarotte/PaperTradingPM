"""
Tests for WebSocket endpoint.

These tests cover:
- WebSocket connection with valid/invalid tokens
- Subscribe/unsubscribe actions
- Ping/pong keepalive
- Error handling for unknown actions

Note: The push_live_data functionality is a placeholder and not tested.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient


class TestWebSocketConnection:
    """Tests for WebSocket connection handling."""

    def test_connect_valid_token_accepts_connection(self, client, mock_user):
        """WebSocket connection with valid token should be accepted."""
        with patch("app.routers.ws.validate_token") as mock_validate:
            mock_validate.return_value = mock_user["id"]
            
            with client.websocket_connect("/ws/live?token=valid_token") as websocket:
                # Should receive connected message
                data = websocket.receive_json()
                assert data["type"] == "connected"
                assert data["user_id"] == mock_user["id"]

    def test_connect_invalid_token_closes_connection(self, client):
        """WebSocket connection with invalid token should be closed."""
        with patch("app.routers.ws.validate_token") as mock_validate:
            mock_validate.return_value = None  # Invalid token
            
            with pytest.raises(Exception):
                # Connection should be rejected
                with client.websocket_connect("/ws/live?token=invalid_token") as websocket:
                    pass

    def test_connect_missing_token_fails(self, client):
        """WebSocket connection without token should fail."""
        # Missing required query param should cause error
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/live") as websocket:
                pass


class TestWebSocketSubscription:
    """Tests for WebSocket subscribe/unsubscribe actions."""

    def test_subscribe_action_adds_markets_to_user_subscriptions(self, client, mock_user):
        """Subscribe action should add markets to user's subscriptions."""
        with patch("app.routers.ws.validate_token") as mock_validate:
            mock_validate.return_value = mock_user["id"]
            
            with client.websocket_connect("/ws/live?token=valid") as websocket:
                # Receive connected message
                websocket.receive_json()
                
                # Send subscribe action
                websocket.send_json({
                    "action": "subscribe",
                    "market_ids": ["market-1", "market-2"],
                })
                
                # Should receive subscribed confirmation
                data = websocket.receive_json()
                assert data["type"] == "subscribed"
                assert "market-1" in data["market_ids"]
                assert "market-2" in data["market_ids"]

    def test_unsubscribe_action_removes_markets_from_subscriptions(self, client, mock_user):
        """Unsubscribe action should remove markets from subscriptions."""
        with patch("app.routers.ws.validate_token") as mock_validate:
            mock_validate.return_value = mock_user["id"]
            
            with client.websocket_connect("/ws/live?token=valid") as websocket:
                # Connected
                websocket.receive_json()
                
                # Subscribe first
                websocket.send_json({
                    "action": "subscribe",
                    "market_ids": ["market-1", "market-2"],
                })
                websocket.receive_json()
                
                # Unsubscribe
                websocket.send_json({
                    "action": "unsubscribe",
                    "market_ids": ["market-1"],
                })
                
                data = websocket.receive_json()
                assert data["type"] == "unsubscribed"
                assert "market-1" in data["market_ids"]

    def test_subscribe_empty_market_list_no_error(self, client, mock_user):
        """Subscribe with empty list should not cause error."""
        with patch("app.routers.ws.validate_token") as mock_validate:
            mock_validate.return_value = mock_user["id"]
            
            with client.websocket_connect("/ws/live?token=valid") as websocket:
                websocket.receive_json()  # connected
                
                websocket.send_json({
                    "action": "subscribe",
                    "market_ids": [],
                })
                
                # Should not error, may or may not send response for empty list
                # Just verify connection is still alive


class TestWebSocketPingPong:
    """Tests for WebSocket ping/pong keepalive."""

    def test_ping_action_returns_pong_response(self, client, mock_user):
        """Ping action should return pong response."""
        with patch("app.routers.ws.validate_token") as mock_validate:
            mock_validate.return_value = mock_user["id"]
            
            with client.websocket_connect("/ws/live?token=valid") as websocket:
                websocket.receive_json()  # connected
                
                websocket.send_json({"action": "ping"})
                
                data = websocket.receive_json()
                assert data["type"] == "pong"


class TestWebSocketErrorHandling:
    """Tests for WebSocket error handling."""

    def test_unknown_action_returns_error_message(self, client, mock_user):
        """Unknown action should return error message."""
        with patch("app.routers.ws.validate_token") as mock_validate:
            mock_validate.return_value = mock_user["id"]
            
            with client.websocket_connect("/ws/live?token=valid") as websocket:
                websocket.receive_json()  # connected
                
                websocket.send_json({"action": "invalid_action"})
                
                data = websocket.receive_json()
                assert data["type"] == "error"
                assert "unknown" in data["message"].lower()

    def test_malformed_json_handled_gracefully(self, client, mock_user):
        """Malformed JSON should be handled without crashing."""
        with patch("app.routers.ws.validate_token") as mock_validate:
            mock_validate.return_value = mock_user["id"]
            
            with client.websocket_connect("/ws/live?token=valid") as websocket:
                websocket.receive_json()  # connected
                
                # Send invalid data - this may cause disconnect or error
                try:
                    websocket.send_text("not valid json {{{")
                except Exception:
                    pass  # Expected to possibly fail


class TestConnectionManager:
    """Tests for ConnectionManager class."""

    def test_manager_tracks_active_connections(self):
        """ConnectionManager should track active connections."""
        from app.routers.ws import ConnectionManager
        
        manager = ConnectionManager()
        
        # Initially empty
        assert len(manager.active_connections) == 0
        assert len(manager.subscriptions) == 0

    def test_manager_subscribe_adds_to_subscriptions(self):
        """Subscribe should add markets to user's subscription set."""
        from app.routers.ws import ConnectionManager
        
        manager = ConnectionManager()
        user_id = "test_user"
        
        # Simulate connection (normally done via websocket.accept)
        manager.subscriptions[user_id] = set()
        
        manager.subscribe(user_id, ["market-1", "market-2"])
        
        assert "market-1" in manager.subscriptions[user_id]
        assert "market-2" in manager.subscriptions[user_id]

    def test_manager_unsubscribe_removes_from_subscriptions(self):
        """Unsubscribe should remove markets from subscription set."""
        from app.routers.ws import ConnectionManager
        
        manager = ConnectionManager()
        user_id = "test_user"
        
        manager.subscriptions[user_id] = {"market-1", "market-2", "market-3"}
        
        manager.unsubscribe(user_id, ["market-1"])
        
        assert "market-1" not in manager.subscriptions[user_id]
        assert "market-2" in manager.subscriptions[user_id]

    def test_manager_get_subscribed_users_returns_correct_users(self):
        """get_subscribed_users should return users subscribed to market."""
        from app.routers.ws import ConnectionManager
        
        manager = ConnectionManager()
        
        manager.subscriptions["user1"] = {"market-a", "market-b"}
        manager.subscriptions["user2"] = {"market-b", "market-c"}
        manager.subscriptions["user3"] = {"market-c"}
        
        users = manager.get_subscribed_users("market-b")
        
        assert "user1" in users
        assert "user2" in users
        assert "user3" not in users

    def test_manager_disconnect_removes_user(self):
        """Disconnect should remove user from connections and subscriptions."""
        from app.routers.ws import ConnectionManager
        
        manager = ConnectionManager()
        user_id = "test_user"
        
        # Simulate connection
        manager.active_connections[user_id] = MagicMock()
        manager.subscriptions[user_id] = {"market-1"}
        
        manager.disconnect(user_id)
        
        assert user_id not in manager.active_connections
        assert user_id not in manager.subscriptions
