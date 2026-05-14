"""
test_estate_ai.py
=================
Test suite for APDG — AI-Based Auto Property Description Generator
Victorian Institute of Technology | Group 1 | Roshan N.

How to run:
    docker run --rm -v "$(pwd):/app" estate-v2 python3 -m pytest tests/test_estate_ai.py -v
Or locally:
    pip install pytest
    pytest tests/test_estate_ai.py -v
"""

import pytest
import json
import os
import io
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ══════════════════════════════════════════════════════════════════════════════
#  FIXTURES
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def app():
    """Set up the Flask app in test mode with a fresh test database."""
    from app import app as flask_app
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret-key"
    with flask_app.app_context():
        from auth import database as db
        db.init_db()
    return flask_app


@pytest.fixture
def client(app):
    """Return a test client that can make HTTP requests without a real server."""
    return app.test_client()


@pytest.fixture
def agent_session(client):
    """
    Log in as the demo agent and return a client with an active session.
    This is used by any test that needs authentication.
    """
    client.post("/api/auth/login", json={
        "username": "agent",
        "password": "agent123"
    }, content_type="application/json")
    return client


@pytest.fixture
def admin_session(client):
    """Log in as the demo admin and return a client with an active session."""
    client.post("/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    }, content_type="application/json")
    return client


def make_test_image():
    """
    Create a tiny valid JPEG in memory for upload tests.
    We do not need a real property photo — just a valid image file.
    """
    from PIL import Image
    img = Image.new("RGB", (100, 100), color=(120, 80, 60))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf


# ══════════════════════════════════════════════════════════════════════════════
#  TC-01 to TC-05 | AUTHENTICATION TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestAuthentication:

    def test_TC01_login_valid_agent(self, client):
        """
        TC-01: Agent can log in with correct credentials.
        Expected: HTTP 200, success flag in response.
        """
        response = client.post("/api/auth/login", json={
            "username": "agent",
            "password": "agent123"
        }, content_type="application/json")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data.get("success") is True or "user" in data

    def test_TC02_login_wrong_password(self, client):
        """
        TC-02: Login fails with wrong password.
        Expected: HTTP 401 or error message in response.
        """
        response = client.post("/api/auth/login", json={
            "username": "agent",
            "password": "wrongpassword"
        }, content_type="application/json")
        assert response.status_code in [400, 401]
        data = json.loads(response.data)
        assert "error" in data or data.get("success") is False

    def test_TC03_login_unknown_user(self, client):
        """
        TC-03: Login fails for a username that does not exist.
        Expected: HTTP 401 or error response.
        """
        response = client.post("/api/auth/login", json={
            "username": "nobody",
            "password": "anything"
        }, content_type="application/json")
        assert response.status_code in [400, 401]

    def test_TC04_upload_blocked_without_login(self, client):
        """
        TC-04: The /upload endpoint should reject requests from unauthenticated users.
        Expected: HTTP 401 Unauthorized.
        """
        response = client.post("/upload", data={})
        assert response.status_code == 401

    def test_TC05_admin_login_valid(self, client):
        """
        TC-05: Admin can log in with correct credentials.
        Expected: HTTP 200, role should be admin in response.
        """
        response = client.post("/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        }, content_type="application/json")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data.get("success") is True or "user" in data


# ══════════════════════════════════════════════════════════════════════════════
#  TC-06 to TC-10 | IMAGE UPLOAD VALIDATION TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestImageUpload:

    def test_TC06_upload_with_no_images(self, agent_session):
        """
        TC-06: Upload request with no images attached should return an error.
        Expected: HTTP 400, error message in response.
        """
        response = agent_session.post("/upload", data={
            "suburb": "Adelaide",
            "tone": "professional"
        })
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data

    def test_TC07_upload_single_valid_image(self, agent_session):
        """
        TC-07: Upload one valid JPEG image with property details.
        Expected: HTTP 200, response contains listing content.
        """
        img = make_test_image()
        response = agent_session.post("/upload", data={
            "images": (img, "bedroom.jpg", "image/jpeg"),
            "suburb": "Glenelg",
            "beds": "3",
            "baths": "2",
            "tone": "professional"
        }, content_type="multipart/form-data")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "content" in data
        assert "listing" in data["content"]

    def test_TC08_upload_returns_fb_ads(self, agent_session):
        """
        TC-08: Upload should return Facebook/Instagram ad variations.
        Expected: facebook_ads key exists with at least 1 ad.
        """
        img = make_test_image()
        response = agent_session.post("/upload", data={
            "images": (img, "kitchen.jpg", "image/jpeg"),
            "suburb": "Norwood",
            "beds": "4",
            "baths": "2",
            "tone": "luxury"
        }, content_type="multipart/form-data")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "facebook_ads" in data["content"]
        assert len(data["content"]["facebook_ads"]) >= 1

    def test_TC09_upload_with_all_tones(self, agent_session):
        """
        TC-09: Each of the four tones should return a non-empty listing.
        Expected: All four tones produce a valid listing description.
        """
        tones = ["professional", "luxury", "family", "investment"]
        for tone in tones:
            img = make_test_image()
            response = agent_session.post("/upload", data={
                "images": (img, f"{tone}_test.jpg", "image/jpeg"),
                "suburb": "Unley",
                "beds": "3",
                "baths": "1",
                "tone": tone
            }, content_type="multipart/form-data")
            assert response.status_code == 200, f"Failed for tone: {tone}"
            data = json.loads(response.data)
            listing = data["content"]["listing"]
            assert listing and len(listing) > 50, f"Listing too short for tone: {tone}"

    def test_TC10_upload_non_image_file(self, agent_session):
        """
        TC-10: Uploading a non-image file (e.g. a text file) should be rejected.
        Expected: HTTP 400 or the file is marked as invalid in the response.
        """
        fake_file = io.BytesIO(b"this is not an image")
        response = agent_session.post("/upload", data={
            "images": (fake_file, "notanimage.txt", "text/plain"),
            "suburb": "Adelaide",
            "tone": "professional"
        }, content_type="multipart/form-data")
        assert response.status_code in [400, 200]
        if response.status_code == 200:
            data = json.loads(response.data)
            images = data.get("images", [])
            if images:
                assert images[0].get("is_invalid") is True


# ══════════════════════════════════════════════════════════════════════════════
#  TC-11 to TC-15 | DESCRIPTION GENERATOR UNIT TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestDescriptionGenerator:

    def test_TC11_listing_contains_suburb(self):
        """
        TC-11: Generated listing should mention the suburb that was entered.
        Expected: Suburb name appears in the listing text.
        """
        from models.yolo_model.description import generate_listing
        listing = generate_listing(
            room_type="Bedroom",
            objects=["bed", "wardrobe"],
            details={"suburb": "Glenelg", "beds": "3", "baths": "2", "tone": "professional"}
        )
        assert "Glenelg" in listing

    def test_TC12_listing_not_empty(self):
        """
        TC-12: generate_listing should always return a non-empty string.
        Expected: Result is a non-empty string regardless of input.
        """
        from models.yolo_model.description import generate_listing
        listing = generate_listing(
            room_type="Kitchen",
            objects=[],
            details={}
        )
        assert isinstance(listing, str)
        assert len(listing) > 30

    def test_TC13_luxury_tone_differs_from_professional(self):
        """
        TC-13: Luxury tone and professional tone should produce different text.
        Expected: The two listings are not identical.
        """
        from models.yolo_model.description import generate_listing
        details_base = {"suburb": "Norwood", "beds": "4", "baths": "2"}
        listing_pro = generate_listing("Living Room", ["sofa", "tv"], {**details_base, "tone": "professional"})
        listing_lux = generate_listing("Living Room", ["sofa", "tv"], {**details_base, "tone": "luxury"})
        assert listing_pro != listing_lux

    def test_TC14_facebook_ads_returns_two_variations(self):
        """
        TC-14: Facebook ad generator should always return exactly 2 variations.
        Expected: List of length 2.
        """
        from models.yolo_model.description import generate_facebook_ads
        ads = generate_facebook_ads(
            room_type="Bedroom",
            objects=["bed", "wardrobe"],
            details={"suburb": "Glenelg", "beds": "3", "tone": "professional"}
        )
        assert isinstance(ads, list)
        assert len(ads) == 2

    def test_TC15_facebook_ads_contain_hashtags(self):
        """
        TC-15: Each Facebook ad should include at least one hashtag.
        Expected: # symbol found in both ad variations.
        """
        from models.yolo_model.description import generate_facebook_ads
        ads = generate_facebook_ads(
            room_type="Kitchen",
            objects=["oven", "sink"],
            details={"suburb": "Unley", "beds": "3", "tone": "investment"}
        )
        for ad in ads:
            assert "#" in ad, f"No hashtag found in ad: {ad[:80]}"


# ══════════════════════════════════════════════════════════════════════════════
#  TC-16 to TC-20 | COMPLIANCE CHECK TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestCompliance:

    def test_TC16_clean_listing_passes_compliance(self):
        """
        TC-16: A normal, honest property listing should pass compliance with no violations.
        Expected: Empty violations list.
        """
        from auth.database import check_compliance
        clean_text = (
            "This 3-bedroom home in Glenelg offers a comfortable lifestyle. "
            "Features include a modern kitchen, spacious living area, and large backyard. "
            "Contact the agent to arrange an inspection."
        )
        violations = check_compliance(clean_text)
        assert violations == [] or len(violations) == 0

    def test_TC17_price_baiting_detected(self):
        """
        TC-17: Listings with price baiting language should trigger a compliance warning.
        Expected: At least one violation returned.
        """
        from auth.database import check_compliance
        dodgy_text = "Offers starting from just $400,000! Prices from only $350k!"
        violations = check_compliance(dodgy_text)
        assert len(violations) > 0

    def test_TC18_guaranteed_returns_flagged(self):
        """
        TC-18: Claims of guaranteed rental returns should be flagged.
        Expected: At least one violation returned.
        """
        from auth.database import check_compliance
        dodgy_text = "This investment property guarantees a 7% rental return every year."
        violations = check_compliance(dodgy_text)
        assert len(violations) > 0

    def test_TC19_compliance_returns_list(self):
        """
        TC-19: check_compliance should always return a list, never crash.
        Expected: Result is always a list (empty or not).
        """
        from auth.database import check_compliance
        result = check_compliance("")
        assert isinstance(result, list)
        result2 = check_compliance("some random text with no issues")
        assert isinstance(result2, list)

    def test_TC20_compliance_endpoint_works(self, agent_session):
        """
        TC-20: The /api/compliance/check endpoint should return violations for bad text.
        Expected: HTTP 200, violations key in response.
        """
        response = agent_session.post("/api/compliance/check", json={
            "text": "Best investment property guaranteed returns forever!"
        }, content_type="application/json")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "violations" in data


# ══════════════════════════════════════════════════════════════════════════════
#  TC-21 to TC-25 | GENERATION HISTORY TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestHistory:

    def test_TC21_history_returns_list(self, agent_session):
        """
        TC-21: The /api/my-generations endpoint should return a list.
        Expected: HTTP 200, generations key is a list.
        """
        response = agent_session.get("/api/my-generations")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "generations" in data
        assert isinstance(data["generations"], list)

    def test_TC22_history_blocked_without_login(self, client):
        """
        TC-22: History endpoint should block unauthenticated users.
        Expected: HTTP 401.
        """
        response = client.get("/api/my-generations")
        assert response.status_code == 401

    def test_TC23_generation_saved_after_upload(self, agent_session):
        """
        TC-23: After a successful upload, a new entry should appear in history.
        Expected: History count increases by 1 after generation.
        """
        before = json.loads(agent_session.get("/api/my-generations").data)
        count_before = len(before["generations"])

        img = make_test_image()
        agent_session.post("/upload", data={
            "images": (img, "lounge.jpg", "image/jpeg"),
            "suburb": "Adelaide",
            "beds": "3",
            "baths": "2",
            "tone": "professional"
        }, content_type="multipart/form-data")

        after = json.loads(agent_session.get("/api/my-generations").data)
        count_after = len(after["generations"])
        assert count_after == count_before + 1

    def test_TC24_agent_cannot_access_other_agents_generation(self, agent_session):
        """
        TC-24: An agent should not be able to access a generation ID that belongs to another user.
        Expected: HTTP 403 or 404 for an ID that does not belong to them.
        """
        response = agent_session.get("/api/generations/99999")
        assert response.status_code in [403, 404]

    def test_TC25_delete_generation(self, agent_session):
        """
        TC-25: An agent should be able to delete their own generation.
        Expected: After delete, the generation no longer appears in history.
        """
        img = make_test_image()
        agent_session.post("/upload", data={
            "images": (img, "delete_test.jpg", "image/jpeg"),
            "suburb": "Adelaide",
            "beds": "2",
            "baths": "1",
            "tone": "family"
        }, content_type="multipart/form-data")

        history = json.loads(agent_session.get("/api/my-generations").data)
        if not history["generations"]:
            pytest.skip("No generations to delete")

        gen_id = history["generations"][0]["id"]
        del_response = agent_session.delete(f"/api/generations/{gen_id}")
        assert del_response.status_code == 200

        history_after = json.loads(agent_session.get("/api/my-generations").data)
        ids_after = [g["id"] for g in history_after["generations"]]
        assert gen_id not in ids_after


# ══════════════════════════════════════════════════════════════════════════════
#  TC-26 to TC-28 | ADMIN TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestAdmin:

    def test_TC26_admin_can_list_all_users(self, admin_session):
        """
        TC-26: Admin should be able to list all registered users.
        Expected: HTTP 200, users list in response.
        """
        response = admin_session.get("/api/admin/users")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "users" in data

    def test_TC27_agent_cannot_access_admin_endpoints(self, agent_session):
        """
        TC-27: A regular agent should not be able to access admin-only endpoints.
        Expected: HTTP 403 Forbidden.
        """
        response = agent_session.get("/api/admin/users")
        assert response.status_code in [401, 403]

    def test_TC28_admin_can_view_all_generations(self, admin_session):
        """
        TC-28: Admin should be able to see all generations across all agents.
        Expected: HTTP 200, generations list in response.
        """
        response = admin_session.get("/api/admin/generations")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "generations" in data


# ══════════════════════════════════════════════════════════════════════════════
#  TC-29 to TC-30 | PERFORMANCE TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestPerformance:

    def test_TC29_upload_response_within_60_seconds(self, agent_session):
        """
        TC-29: The full generation pipeline should complete within 60 seconds.
        This tests the speed optimisation work done on CLIP and description.py.
        Expected: Response time under 60 seconds.
        """
        img = make_test_image()
        start = time.time()
        response = agent_session.post("/upload", data={
            "images": (img, "perf_test.jpg", "image/jpeg"),
            "suburb": "Adelaide",
            "beds": "3",
            "baths": "2",
            "tone": "professional"
        }, content_type="multipart/form-data")
        elapsed = time.time() - start
        assert response.status_code == 200
        assert elapsed < 60, f"Generation took {elapsed:.1f}s — should be under 60s"

    def test_TC30_login_response_within_2_seconds(self, client):
        """
        TC-30: The login endpoint should respond within 2 seconds.
        Expected: Response time under 2 seconds.
        """
        start = time.time()
        client.post("/api/auth/login", json={
            "username": "agent",
            "password": "agent123"
        }, content_type="application/json")
        elapsed = time.time() - start
        assert elapsed < 2, f"Login took {elapsed:.2f}s — should be under 2s"
