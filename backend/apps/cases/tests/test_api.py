import pytest

BASE = "/api/v1/cases/"


@pytest.mark.django_db
class TestApiContract:
    def test_error_envelope_for_404(self, api, student):
        res = api(student).get(f"{BASE}999999/")
        assert res.status_code == 404
        assert res.data == {"error": {"code": "not_found", "message": "Not found.", "details": {}}}

    def test_pagination_shape(self, api, student, make_case):
        for _ in range(3):
            make_case(student)
        res = api(student).get(f"{BASE}?page_size=2")
        assert set(res.data) == {"count", "next", "previous", "results"}
        assert res.data["count"] == 3 and len(res.data["results"]) == 2 and res.data["next"]

    def test_filters(self, api, admin_user, student, make_case):
        make_case(student, title="Broken chair in lecture hall")
        make_case(student, requested_priority="urgent", case_type="suggestion")
        assert api(admin_user).get(f"{BASE}?priority=urgent").data["count"] == 1
        assert api(admin_user).get(f"{BASE}?case_type=suggestion").data["count"] == 1
        assert api(admin_user).get(f"{BASE}?search=chair").data["count"] == 1
        assert api(admin_user).get(f"{BASE}?status=submitted,closed").data["count"] == 2
        assert api(admin_user).get(f"{BASE}?status=bogus").data["count"] == 0

    def test_put_and_delete_not_allowed(self, api, admin_user, student, make_case):
        case = make_case(student)
        assert api(admin_user).delete(f"{BASE}{case.pk}/").status_code == 405
        assert api(admin_user).put(f"{BASE}{case.pk}/", {}).status_code == 405

    def test_openapi_schema_generates(self, api, student):
        res = api(student).get("/api/schema/")
        assert res.status_code == 200
        body = res.content.decode()
        for path in ("/api/v1/cases/", "/api/v1/cases/{id}/verify-resolution/", "/api/v1/cases/{id}/reopen/",
                     "/api/v1/cases/{id}/updates/"):
            assert path in body

    def test_token_login_flow(self, api, student):
        res = api().post("/api/v1/auth/token/", {"username": student.username, "password": "Synthetic-pass-123"})
        assert res.status_code == 200 and res.data["user"]["role"] == "student"
        from rest_framework.test import APIClient

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {res.data['token']}")
        assert client.get("/api/v1/auth/me/").data["id"] == student.pk
        assert client.get(BASE).status_code == 200

    def test_bad_login(self, api, student):
        res = api().post("/api/v1/auth/token/", {"username": student.username, "password": "wrong"})
        assert res.status_code == 400 and res.data["error"]["code"] == "validation_error"
