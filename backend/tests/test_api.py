import os


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == "3.8.0"


def test_api_health_endpoint(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == "3.8.0"


def test_cors_preflight(client):
    resp = client.options(
        "/api/auth/register",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert resp.status_code == 200
    assert "localhost:5173" in resp.headers.get("access-control-allow-origin", "")


def test_register_and_login(client):
    resp = client.post("/api/auth/register", json={
        "username": "alice",
        "email": "alice@example.com",
        "password": "secret123"
    })
    assert resp.status_code == 200
    user = resp.json()
    assert user["username"] == "alice"

    resp = client.post("/api/auth/login", data={
        "username": "alice",
        "password": "secret123"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_auth_secret_key_from_env(monkeypatch):
    """Verify SECRET_KEY can be overridden via environment variable."""
    monkeypatch.setenv("TAXFLOW_SECRET_KEY", "test-secret-key")
    # Force reimport to pick up env var
    import importlib
    from backend.routers import auth as auth_module
    importlib.reload(auth_module)
    assert auth_module.SECRET_KEY == "test-secret-key"


def test_protected_endpoint_requires_auth(client):
    resp = client.get("/api/clients/")
    assert resp.status_code == 401


def test_client_crud(auth_client):
    c = auth_client
    # Create
    resp = c.post("/api/clients/", json={
        "name": "Test Client",
        "email": "client@example.com",
        "tax_id": "123-45-6789"
    })
    assert resp.status_code == 200
    client_data = resp.json()
    assert client_data["name"] == "Test Client"
    client_id = client_data["id"]

    # List
    resp = c.get("/api/clients/")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # Update
    resp = c.patch(f"/api/clients/{client_id}", json={
        "name": "Updated Client",
        "email": "updated@example.com"
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Client"

    # Delete
    resp = c.delete(f"/api/clients/{client_id}")
    assert resp.status_code == 200


def test_account_crud(auth_client):
    c = auth_client
    # Create client first
    resp = c.post("/api/clients/", json={"name": "Acct Client"})
    assert resp.status_code == 200
    client_id = resp.json()["id"]

    # Create account
    resp = c.post("/api/accounts/", json={
        "name": "Checking",
        "institution": "Big Bank",
        "client_id": client_id,
        "type": "checking"
    })
    assert resp.status_code == 200
    account = resp.json()
    assert account["name"] == "Checking"
    account_id = account["id"]

    # List by client
    resp = c.get(f"/api/accounts/?client_id={client_id}")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # Update
    resp = c.patch(f"/api/accounts/{account_id}", json={"name": "Updated Checking"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Checking"

    # Delete
    resp = c.delete(f"/api/accounts/{account_id}")
    assert resp.status_code == 200


def test_export_formats(auth_client):
    resp = auth_client.get("/api/export/formats")
    assert resp.status_code == 200
    formats = resp.json()
    names = {f["id"] for f in formats}
    assert "csv" in names
    assert "qif" in names


def test_ml_status(auth_client):
    resp = auth_client.get("/api/ml/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "enabled" in data


def test_tests_runner(auth_client):
    resp = auth_client.post("/api/tests/run")
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert isinstance(data["results"], list)


def test_upload_rejects_non_pdf(auth_client):
    resp = auth_client.post(
        "/api/upload/",
        files={"file": ("statement.txt", b"not a pdf", "text/plain")}
    )
    assert resp.status_code == 400
    assert "Only PDF files are accepted" in resp.json()["detail"]


def test_upload_pdf_parser_returns_meta(client):
    """GenericPDFParser should include period_start/period_end in meta when present."""
    from backend.parsers.generic_pdf import GenericPDFParser
    import tempfile
    from fpdf import FPDF

    class StmtPDF(FPDF):
        def header(self):
            self.set_font("Helvetica", "B", 12)
            self.cell(0, 10, "Big Bank Statement", ln=True)
            self.cell(0, 10, "Statement Period: 01/01/2025 to 01/31/2025", ln=True)
            self.cell(0, 10, "Opening Balance: $100.00", ln=True)
            self.cell(0, 10, "Closing Balance: $100.00", ln=True)

    pdf = StmtPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 10, "01/15/2025 Coffee Shop $5.00 $95.00", ln=True)
    pdf.cell(0, 10, "01/20/2025 Salary Deposit $50.00 $100.00", ln=True)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        pdf.output(tmp.name)
        tmp_path = tmp.name

    try:
        parser = GenericPDFParser(tmp_path)
        result = parser.parse()
        assert result["meta"]["period_start"] == "2025-01-01"
        assert result["meta"]["period_end"] == "2025-01-31"
    finally:
        os.unlink(tmp_path)


def test_ml_toggle_changes_state(auth_client):
    c = auth_client
    resp = c.get("/api/ml/status")
    assert resp.status_code == 200
    initial = resp.json()
    assert "ml_enabled_flag" in initial

    resp = c.post("/api/ml/toggle")
    assert resp.status_code == 200
    toggled = resp.json()
    assert toggled["enabled"] is not initial["ml_enabled_flag"]

    resp = c.get("/api/ml/status")
    assert resp.status_code == 200
    assert resp.json()["ml_enabled_flag"] == toggled["enabled"]


def test_sse_endpoint_returns_stream(client):
    resp = client.get(
        "/api/events?heartbeat=1&count=1",
        headers={"Accept": "text/event-stream"},
        timeout=10,
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
    assert "heartbeat" in resp.text


def test_upload_process_enriches_transactions(auth_client):
    c = auth_client
    import tempfile
    from fpdf import FPDF

    class StmtPDF(FPDF):
        def header(self):
            self.set_font("Helvetica", "B", 12)
            self.cell(0, 10, "Big Bank Statement", ln=True)
            self.cell(0, 10, "Statement Period: 01/01/2025 to 01/31/2025", ln=True)
            self.cell(0, 10, "Opening Balance: $0.00", ln=True)
            self.cell(0, 10, "Closing Balance: $-80.00", ln=True)

    pdf = StmtPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 10, "01/15/2025 WALMART Cash Back $20.00 $-80.00", ln=True)
    pdf.cell(0, 10, "01/20/2025 Salary Deposit $100.00 $20.00", ln=True)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        pdf.output(tmp.name)
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as f:
            resp = c.post(
                "/api/upload/",
                files={"file": ("statement.pdf", f, "application/pdf")},
            )
        assert resp.status_code == 200, resp.text
        file_id = resp.json()["file_id"]

        resp = c.post("/api/upload/process", json={
            "file_id": file_id,
            "output_format": "json",
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["success"] is True
        assert data["transaction_count"] >= 1
        assert "transactions" in data
        tx_fields = {k for tx in data["transactions"] for k in tx.keys()}
        assert "split_id" in tx_fields
        assert "parent_id" in tx_fields
        assert "memo" in tx_fields
        assert "graph_edges" in tx_fields
    finally:
        os.unlink(tmp_path)
