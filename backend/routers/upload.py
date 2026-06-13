"""
Upload and processing endpoints.
"""

import asyncio
import time
import sys
from pathlib import Path
from decimal import Decimal
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Query
from fastapi.responses import FileResponse

# Ensure pipeline is importable
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from api_models import UploadResponse, ProcessingRequest, ProcessingResult, TransactionOut, ReconciliationOut
from api_utils import (
    ensure_dirs, save_uploaded_file, get_upload_path, get_output_path,
    log_event, generate_file_id, get_db, save_db, UPLOAD_DIR, OUTPUT_DIR
)

router = APIRouter()
_ocr_lock = asyncio.Lock()


def _import_pipeline():
    """Lazy import to avoid startup overhead."""
    try:
        from phase3_pipeline.main import pdf_to_transactions, load_csv
        from phase3_pipeline.pipeline import run
        from phase3_pipeline.export import export
        from phase3_pipeline.qif_export import write_qif
        from phase3_pipeline.reconciliation import reconcile_transactions, StatementReconciler
        from phase3_pipeline.ledger_guard import validate_raw_transactions
        from phase3_pipeline.ml_categorizer import MLCategorizer
        from phase3_pipeline.categorizer import PriorityCategorizer
        from phase3_pipeline.profile_manager import ProfileManager
        from phase3_pipeline.config import USE_ML, OCR_CONFIG
        from phase3_pipeline.models import Transaction
        return {
            "pdf_to_transactions": pdf_to_transactions,
            "load_csv": load_csv,
            "run": run,
            "export": export,
            "write_qif": write_qif,
            "reconcile_transactions": reconcile_transactions,
            "StatementReconciler": StatementReconciler,
            "validate_raw_transactions": validate_raw_transactions,
            "MLCategorizer": MLCategorizer,
            "PriorityCategorizer": PriorityCategorizer,
            "ProfileManager": ProfileManager,
            "USE_ML": USE_ML,
            "OCR_CONFIG": OCR_CONFIG,
            "Transaction": Transaction,
        }
    except ImportError as e:
        print(f"Pipeline not available: {e}")
        return None


# --- Fallback keyword categorizer ---
CATEGORY_KEYWORDS = {
    'payroll': ('Income:Salary', 'wages'),
    'direct deposit': ('Income:Salary', 'wages'),
    'salary': ('Income:Salary', 'wages'),
    'shell': ('Transportation:Fuel', 'fuel_expense'),
    'shell oil': ('Transportation:Fuel', 'fuel_expense'),
    'chevron': ('Transportation:Fuel', 'fuel_expense'),
    'exxon': ('Transportation:Fuel', 'fuel_expense'),
    'bp': ('Transportation:Fuel', 'fuel_expense'),
    'starbucks': ('Food:Dining Out', 'meals_expense'),
    'mcdonald': ('Food:Dining Out', 'meals_expense'),
    'subway': ('Food:Dining Out', 'meals_expense'),
    'restaurant': ('Food:Dining Out', 'meals_expense'),
    'cafe': ('Food:Dining Out', 'meals_expense'),
    'doordash': ('Food:Delivery', 'meals_expense'),
    'ubereats': ('Food:Delivery', 'meals_expense'),
    'grubhub': ('Food:Delivery', 'meals_expense'),
    'amazon': ('Shopping:General', 'supplies_expense'),
    'amazon.com': ('Shopping:General', 'supplies_expense'),
    'walmart': ('Shopping:General', 'supplies_expense'),
    'target': ('Shopping:General', 'supplies_expense'),
    'costco': ('Shopping:General', 'supplies_expense'),
    'home depot': ('Home:Improvement', 'equipment_expense'),
    'lowe': ('Home:Improvement', 'equipment_expense'),
    'netflix': ('Entertainment:Streaming', 'software_expense'),
    'spotify': ('Entertainment:Music', 'software_expense'),
    'hulu': ('Entertainment:Streaming', 'software_expense'),
    'disney': ('Entertainment:Streaming', 'software_expense'),
    'adobe': ('Software:SaaS', 'software_expense'),
    'microsoft 365': ('Software:SaaS', 'software_expense'),
    'github': ('Software:Cloud Services', 'software_expense'),
    'uber': ('Transportation:Rideshare', 'travel_expense'),
    'lyft': ('Transportation:Rideshare', 'travel_expense'),
    'taxi': ('Transportation:Rideshare', 'travel_expense'),
    'airline': ('Travel:Flights', 'travel_expense'),
    'hotel': ('Travel:Lodging', 'travel_expense'),
    'airbnb': ('Travel:Lodging', 'travel_expense'),
    'hertz': ('Travel:Car Rental', 'travel_expense'),
    'electric': ('Bills:Electricity', 'utilities_expense'),
    'water': ('Bills:Water/Sewer', 'utilities_expense'),
    'internet': ('Bills:Internet', 'utilities_expense'),
    'phone': ('Bills:Phone', 'utilities_expense'),
    'verizon': ('Bills:Phone', 'utilities_expense'),
    't-mobile': ('Bills:Phone', 'utilities_expense'),
    'rent': ('Bills:Housing', 'rent_expense'),
    'mortgage': ('Bills:Mortgage', 'rent_expense'),
    'geico': ('Transportation:Auto Insurance', 'insurance_expense'),
    'progressive': ('Transportation:Auto Insurance', 'insurance_expense'),
    'state farm': ('Bills:Insurance', 'insurance_expense'),
    'pharmacy': ('Health:Pharmacy', 'medical_expense'),
    'cvs': ('Health:Pharmacy', 'medical_expense'),
    'walgreens': ('Health:Pharmacy', 'medical_expense'),
    'doctor': ('Health:Medical', 'medical_expense'),
    'hospital': ('Health:Medical', 'medical_expense'),
    'dental': ('Health:Medical', 'medical_expense'),
    'office depot': ('Business:Office Supplies', 'office_expense'),
    'staples': ('Business:Office Supplies', 'office_expense'),
    'fedex': ('Business:Shipping', 'shipping_expense'),
    'ups': ('Business:Shipping', 'shipping_expense'),
    'venmo': ('Transfer:P2P', 'transfer'),
    'zelle': ('Transfer:P2P', 'transfer'),
    'cash app': ('Transfer:P2P', 'transfer'),
    'transfer': ('Transfer:Internal', 'transfer'),
    'fee': ('Fees:Bank', 'bank_fees'),
    'service charge': ('Fees:Bank', 'bank_fees'),
    'atm fee': ('Fees:Bank', 'bank_fees'),
    'overdraft': ('Fees:Bank', 'bank_fees'),
}


def _fallback_categorize(description: str):
    """Keyword fallback when YAML categorizer returns None."""
    desc_lower = description.lower()
    for keyword, (cat, tax) in CATEGORY_KEYWORDS.items():
        if keyword in desc_lower:
            return cat, tax
    income_kws = ['deposit', 'credit', 'refund', 'reimbursement', 'dividend', 'interest']
    for kw in income_kws:
        if kw in desc_lower:
            return 'Income:Miscellaneous', 'misc_income'
    return None, None
# --- End fallback categorizer ---


def _sanitize_path_component(path_str: str) -> str:
    """Reject path traversal attempts."""
    if not path_str:
        return ""
    if ".." in path_str or Path(path_str).is_absolute():
        raise HTTPException(400, "Invalid path: traversal or absolute path detected")
    return path_str


@router.post("/", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    client_id: str = Form("default"),
    save_folder: Optional[str] = Form(None),
):
    """Upload a PDF or CSV bank statement. Optional save_folder overrides default."""
    if save_folder:
        _sanitize_path_component(save_folder)
    custom_folder = Path(save_folder) if save_folder else None
    ensure_dirs(upload_dir=custom_folder)

    if not file.filename:
        raise HTTPException(400, "No file provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in (".pdf", ".csv"):
        raise HTTPException(400, f"Unsupported file type: {ext}. Only .pdf and .csv allowed.")

    file_id = generate_file_id()
    saved_path = save_uploaded_file(file_id, file, save_folder=custom_folder)

    log_event(
        "INFO",
        "FILE_UPLOAD",
        f"Uploaded {file.filename} to {saved_path} ({saved_path.stat().st_size} bytes)",
        client_id=client_id,
        details={"file_id": file_id, "filename": file.filename, "size": saved_path.stat().st_size, "folder": str(saved_path.parent)},
    )

    return UploadResponse(
        success=True,
        file_id=file_id,
        filename=file.filename,
        file_type=ext.replace(".", ""),
        size_bytes=saved_path.stat().st_size,
        message=f"File uploaded successfully. Use file_id '{file_id}' to process.",
    )


@router.post("/process", response_model=ProcessingResult)
async def process_file(req: ProcessingRequest):
    """Process an uploaded file through the ETL pipeline."""
    start_time = time.time()
    
    if req.source_folder:
        _sanitize_path_component(req.source_folder)
    if req.output_folder:
        _sanitize_path_component(req.output_folder)
    
    custom_output = Path(req.output_folder) if req.output_folder else None
    custom_source = Path(req.source_folder) if req.source_folder else None
    
    ensure_dirs(upload_dir=custom_source or UPLOAD_DIR, output_dir=custom_output or OUTPUT_DIR)

    input_path = get_upload_path(req.file_id, search_folder=custom_source)
    if not input_path:
        raise HTTPException(404, f"File with id '{req.file_id}' not found. Upload first.")

    return await _run_pipeline(req, input_path, custom_output, start_time)


@router.post("/process-local", response_model=ProcessingResult)
async def process_local_file(
    file_path: str = Form(..., description="Absolute path to existing PDF/CSV on server"),
    client_id: str = Form("default"),
    output_format: str = Form("qif"),
    output_folder: Optional[str] = Form(None),
    use_fast: bool = Form(False),
    use_ml: bool = Form(False),
):
    """
    Process a file already on disk (CLI-style). No upload step needed.
    """
    start_time = time.time()
    
    if ".." in file_path:
        raise HTTPException(400, "Invalid file_path: traversal detected")
    
    input_path = Path(file_path).resolve()
    if not input_path.exists():
        raise HTTPException(404, f"File not found: {file_path}")
    
    if input_path.suffix.lower() not in (".pdf", ".csv"):
        raise HTTPException(400, f"Unsupported file type: {input_path.suffix}")

    if output_folder:
        _sanitize_path_component(output_folder)
    custom_output = Path(output_folder) if output_folder else None
    ensure_dirs(output_dir=custom_output or OUTPUT_DIR)

    req = ProcessingRequest(
        file_id=generate_file_id(),
        client_id=client_id,
        output_format=output_format,
        use_fast=use_fast,
        use_ml=use_ml,
        output_folder=output_folder,
    )
    
    return await _run_pipeline(req, input_path, custom_output, start_time)


@router.post("/parse-pdf", response_model=ProcessingResult)
async def parse_pdf_statement(
    file: UploadFile = File(...),
    client_id: str = Form("default"),
):
    """
    Parse a generic PDF bank statement using template-based detection.
    Covers 95% of US institutions via 4 master templates.
    """
    start_time = time.time()
    
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(400, "Only PDF files accepted")
    
    ensure_dirs(upload_dir=UPLOAD_DIR)
    
    file_id = generate_file_id()
    temp_path = UPLOAD_DIR / f"{file_id}.pdf"
    
    try:
        with open(temp_path, "wb") as f:
            f.write(await file.read())
        
        try:
            from backend.parsers.generic_pdf import GenericPDFParser
        except ImportError:
            try:
                from parsers.generic_pdf import GenericPDFParser
            except ImportError as e:
                raise HTTPException(500, f"PDF parser not available: {e}")
        
        parser = GenericPDFParser(str(temp_path))
        
        try:
            result = await asyncio.to_thread(parser.parse)
        except Exception as e:
            raise HTTPException(400, f"PDF parsing failed: {e}")
        
        if "error" in result:
            raise HTTPException(400, result["error"])
        
        transactions = result.get("transactions", [])
        total_credits = sum(float(t.get("amount", 0)) for t in transactions if float(t.get("amount", 0)) > 0)
        total_debits = sum(float(t.get("amount", 0)) for t in transactions if float(t.get("amount", 0)) < 0)
        net_change = total_credits + total_debits
        
        txn_outs = []
        for idx, t in enumerate(transactions):
            amount = float(t.get("amount", 0))
            desc = t.get("description", "")
            
            cat = t.get("category", "uncategorized")
            tax_cat = "uncategorized"
            tax_ded = False
            if cat == "uncategorized":
                cat, tax_cat = _fallback_categorize(desc)
                if cat:
                    tax_ded = tax_cat in (
                        'fuel_expense', 'meals_expense', 'travel_expense', 'office_expense',
                        'shipping_expense', 'medical_expense', 'equipment_expense', 'software_expense',
                        'utilities_expense', 'rent_expense', 'insurance_expense', 'bank_fees', 'misc_income'
                    )
            
            txn_outs.append(TransactionOut(
                date=t.get("date", ""),
                description=desc,
                amount=str(amount),
                category=cat or "uncategorized",
                payee=desc[:20] if desc else "unknown",
                institution=result.get("template", "Unknown"),
                txn_uid=f"pdf-{file_id}-{idx}",
                tax_category=tax_cat or "uncategorized",
                tax_deductible=tax_ded,
            ))
        
        db = get_db()
        db.setdefault("processed_files", {})
        db["processed_files"][file_id] = {
            "client_id": client_id,
            "institution": result.get("template", "Unknown"),
            "transaction_count": len(txn_outs),
            "template": result.get("template", "Unknown"),
            "account_info": result.get("account_info", {}),
            "processed_at": datetime.now().isoformat(),
        }
        save_db(db)
        
        elapsed = int((time.time() - start_time) * 1000)
        
        log_event(
            "INFO",
            "PDF_PARSE_COMPLETE",
            f"Parsed {len(txn_outs)} transactions from {file.filename}",
            client_id=client_id,
            details={
                "file_id": file_id,
                "template": result.get("template"),
                "transaction_count": len(txn_outs),
            },
        )
        
        return ProcessingResult(
            success=True,
            file_id=file_id,
            client_id=client_id,
            institution=result.get("template", "Unknown"),
            transaction_count=len(txn_outs),
            transactions=txn_outs[:100],
            reconciliation=ReconciliationOut(
                status="PARTIAL",
                message=f"PDF parsed using {result.get('template', 'Unknown')} template",
                transaction_count=len(txn_outs),
                total_credits=f"{total_credits:.2f}",
                total_debits=f"{abs(total_debits):.2f}",
                net_change=f"{net_change:.2f}",
                variance="0.00",
            ),
            output_file=None,
            processing_time_ms=elapsed,
            warnings=[],
        )
    
    finally:
        if temp_path.exists():
            temp_path.unlink()


async def _run_pipeline(req: ProcessingRequest, input_path: Path, output_folder: Optional[Path], start_time: float):
    """Shared pipeline runner for both upload/process and process-local."""
    
    pipeline = _import_pipeline()
    if pipeline is None:
        return await asyncio.to_thread(_mock_process, req, start_time)

    try:
        mod = pipeline
        prof_manager = mod["ProfileManager"]()
        profile = prof_manager.resolve_profile(filename=input_path.name)

        if input_path.suffix.lower() == ".pdf":
            if req.use_fast:
                async with _ocr_lock:
                    original_prefer = mod["OCR_CONFIG"].get("prefer_digital")
                    try:
                        mod["OCR_CONFIG"]["prefer_digital"] = True
                        transactions, raw_text = await asyncio.to_thread(
                            mod["pdf_to_transactions"], input_path, profile=profile
                        )
                    finally:
                        if original_prefer is not None:
                            mod["OCR_CONFIG"]["prefer_digital"] = original_prefer
                        else:
                            mod["OCR_CONFIG"].pop("prefer_digital", None)
            else:
                transactions, raw_text = await asyncio.to_thread(
                    mod["pdf_to_transactions"], input_path, profile=profile
                )
        else:
            transactions = await asyncio.to_thread(mod["load_csv"], input_path, profile=profile)
            raw_text = ""

        seen_uids = set()
        unique_txns = []
        for txn in transactions:
            if txn.txn_uid not in seen_uids:
                seen_uids.add(txn.txn_uid)
                unique_txns.append(txn)
        transactions = unique_txns

        is_valid = await asyncio.to_thread(mod["validate_raw_transactions"], transactions)
        if not is_valid:
            raise HTTPException(400, "Raw transaction validation failed")

        graph = await asyncio.to_thread(mod["run"], transactions)

        ml_cat = None
        if req.use_ml and mod["USE_ML"]:
            try:
                ml_cat = await asyncio.to_thread(mod["MLCategorizer"])
            except Exception as e:
                log_event("WARNING", "ML_INIT_FAILED", str(e), req.client_id)

        rule_cat = None
        if ml_cat is None:
            yaml_path = PROJECT_ROOT / "categories.yaml"
            if yaml_path.exists():
                rule_cat = mod["PriorityCategorizer"](str(yaml_path))

        live_txns = graph.live()
        for txn in live_txns:
            cat = None
            method = "none"
            conf = 0.0
            
            if ml_cat and ml_cat.enabled:
                cat, conf, method = ml_cat.predict(txn.description, getattr(txn, 'payee', ''))
            
            if not cat and rule_cat:
                cat = rule_cat.categorize(txn.description, getattr(txn, 'payee', ''))
                if cat:
                    method = "rule"
                    conf = 1.0
            
            if not cat:
                cat, tax_cat = _fallback_categorize(txn.description)
                if cat:
                    method = "fallback"
                    conf = 0.85
                    txn.tax_category = tax_cat
            
            if cat and not txn.category:
                txn.category = cat
            if txn.tax_category == "uncategorized" and txn.category:
                txn.tax_category = txn.category

        for txn in live_txns:
            txn.payee = prof_manager.normalize_payee(txn.description, profile)

        ext_map = {"qif": "qif", "csv": "csv", "excel": "xlsx", "json": "json"}
        actual_ext = ext_map.get(req.output_format, req.output_format)
        output_path = get_output_path(req.file_id, actual_ext, output_folder=output_folder)
        
        if req.output_format == "qif":
            def _write_qif():
                with open(output_path, "w", encoding="utf-8") as f:
                    mod["write_qif"](graph, f)
            await asyncio.to_thread(_write_qif)
        else:
            out_data = mod["export"](graph)
            if out_data:
                import csv
                def _write_csv():
                    with open(output_path, "w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=out_data[0].keys())
                        writer.writeheader()
                        writer.writerows(out_data)
                await asyncio.to_thread(_write_csv)
            else:
                def _touch():
                    with open(output_path, "w", encoding="utf-8") as f:
                        pass
                await asyncio.to_thread(_touch)

        def _reconcile():
            opening, closing = mod["StatementReconciler"].extract_balances_from_text(raw_text)
            return mod["reconcile_transactions"](live_txns, opening, closing)
        
        report = await asyncio.to_thread(_reconcile)

        txn_outs = []
        for t in live_txns:
            txn_outs.append(TransactionOut(
                date=t.date,
                description=t.description,
                raw_description=getattr(t, 'raw_description', ''),
                amount=str(t.amount),
                category=t.category,
                payee=t.payee or "unknown",
                institution=t.institution or "unknown",
                txn_uid=t.txn_uid,
                tax_category=getattr(t, 'tax_category', 'uncategorized'),
                tax_deductible=getattr(t, 'tax_deductible', False),
                memo=getattr(t, 'memo', ''),
            ))

        elapsed = int((time.time() - start_time) * 1000)

        db = get_db()
        db.setdefault("processed_files", {})
        db["processed_files"][req.file_id] = {
            "client_id": req.client_id,
            "profile": profile,
            "institution": live_txns[0].institution or "unknown" if live_txns else "unknown",
            "transaction_count": len(live_txns),
            "output_file": str(output_path) if output_path.exists() else None,
            "output_format": req.output_format,
            "processed_at": datetime.now().isoformat(),
        }
        save_db(db)

        log_event(
            "INFO",
            "PROCESSING_COMPLETE",
            f"Processed {len(live_txns)} transactions from {input_path.name}",
            client_id=req.client_id,
            details={
                "file_id": req.file_id,
                "institution": live_txns[0].institution or "unknown" if live_txns else "unknown",
                "transaction_count": len(live_txns),
                "reconciliation": report.status,
                "time_ms": elapsed,
            },
        )

        return ProcessingResult(
            success=True,
            file_id=req.file_id,
            client_id=req.client_id,
            institution=live_txns[0].institution or "unknown" if live_txns else "unknown",
            transaction_count=len(live_txns),
            transactions=txn_outs[:100],
            reconciliation=ReconciliationOut(
                status=report.status,
                message=report.message,
                opening_balance=f"{report.opening_balance:.2f}" if report.opening_balance else None,
                closing_balance=f"{report.closing_balance:.2f}" if report.closing_balance else None,
                transaction_count=report.transaction_count,
                total_credits=f"{report.total_credits:.2f}",
                total_debits=f"{report.total_debits:.2f}",
                net_change=f"{report.net_change:.2f}",
                calculated_ending=f"{report.calculated_ending:.2f}" if report.calculated_ending else None,
                variance=f"{report.variance:.2f}",
            ),
            output_file=str(output_path) if output_path.exists() else None,
            processing_time_ms=elapsed,
            warnings=[],
        )

    except HTTPException:
        raise
    except Exception as e:
        log_event("ERROR", "PROCESSING_FAILED", str(e), client_id=req.client_id, details={"file_id": req.file_id})
        raise HTTPException(500, f"Processing failed: {str(e)}")


def _mock_process(req: ProcessingRequest, start_time: float) -> ProcessingResult:
    """Mock processing when pipeline is not installed."""
    elapsed = int((time.time() - start_time) * 1000)

    mock_txns = [
        TransactionOut(date="2026-06-01", description="SHELL OIL", raw_description="Shell Oil Station #123", amount="-45.00", category="Fuel", payee="Shell", institution="Chase", txn_uid="abc123", tax_category="fuel_expense", tax_deductible=True, memo="tax:fuel_expense | (deductible)"),
        TransactionOut(date="2026-06-02", description="UBER", raw_description="UBER TRIP 06/02", amount="-25.50", category="Transport", payee="Uber", institution="Amex", txn_uid="def456", tax_category="uncategorized", tax_deductible=False, memo=""),
    ]

    return ProcessingResult(
        success=True,
        file_id=req.file_id,
        client_id=req.client_id,
        institution="Demo Bank (pipeline not installed)",
        transaction_count=2,
        transactions=mock_txns,
        reconciliation=ReconciliationOut(
            status="PARTIAL",
            message="Mock reconciliation - pipeline not installed",
            opening_balance=None,
            closing_balance=None,
            transaction_count=2,
            total_credits="0.00",
            total_debits="70.50",
            net_change="-70.50",
            calculated_ending=None,
            variance="0.00",
        ),
        output_file=None,
        processing_time_ms=elapsed,
        warnings=["Pipeline modules not found. Running in demo mode."],
    )


@router.get("/status/{file_id}")
async def get_status(file_id: str):
    """Get processing status for a file."""
    db = get_db()
    db.setdefault("processed_files", {})
    info = db.get("processed_files", {}).get(file_id)
    if not info:
        return {"status": "pending", "file_id": file_id}
    return {"status": "completed", "file_id": file_id, **info}


@router.get("/download/{file_id}")
async def download_result(file_id: str, format: str = "qif"):
    """Download the processed output file."""
    ext_map = {"qif": "qif", "csv": "csv", "excel": "xlsx", "json": "json"}
    ext = ext_map.get(format, format)
    
    output_path = get_output_path(file_id, format)
    if not output_path.exists():
        output_path = get_output_path(file_id, ext)
    if not output_path.exists():
        alt_path = Path("data/output") / f"{file_id}.{ext}"
        if alt_path.exists():
            output_path = alt_path
    
    if not output_path.exists():
        raise HTTPException(404, f"Output file not found for {file_id} (looked for {output_path})")
    
    media_type = {
        "qif": "application/qif",
        "csv": "text/csv",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "json": "application/json"
    }.get(ext, "application/octet-stream")
    
    return FileResponse(
        output_path,
        filename=f"processed_{file_id}.{ext}",
        media_type=media_type
    )
