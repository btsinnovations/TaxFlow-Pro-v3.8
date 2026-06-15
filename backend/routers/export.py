import csv
import io
import json
from collections import defaultdict
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models
from .auth import get_current_user

router = APIRouter(prefix="/export", tags=["export"])

@router.get("/statement/{statement_id}")
def export_statement(statement_id: int,
                     format: str = "csv",
                     db: Session = Depends(get_db),
                     current_user: models.User = Depends(get_current_user)):
    statement = db.query(models.Statement).filter(
        models.Statement.id == statement_id,
        models.Statement.user_id == current_user.id
    ).first()
    if not statement:
        raise HTTPException(status_code=404, detail="Statement not found")
    
    transactions = db.query(models.Transaction).filter(
        models.Transaction.statement_id == statement_id
    ).order_by(models.Transaction.date.asc()).all()
    
    if format == "json":
        data = [{
            "id": t.id, "date": t.date, "description": t.description,
            "amount": float(t.amount), "type": t.tx_type, "category": t.category,
            "running_balance": float(t.running_balance) if t.running_balance is not None else None
        } for t in transactions]
        return Response(
            content=json.dumps(data, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=statement_{statement_id}.json"}
        )
    
    elif format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id","date","description","amount","type","category","running_balance"])
        for t in transactions:
            writer.writerow([
                t.id, t.date, t.description,
                float(t.amount), t.tx_type, t.category,
                float(t.running_balance) if t.running_balance is not None else ""
            ])
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=statement_{statement_id}.csv"}
        )
        
    elif format == "qbo":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Date", "Description", "Withdrawals", "Deposits"])
        for t in transactions:
            try:
                qbo_date = datetime.strptime(t.date, "%Y-%m-%d").strftime("%m/%d/%Y")
            except (ValueError, TypeError):
                qbo_date = t.date
            amount = float(t.amount)
            writer.writerow([qbo_date, t.description, abs(amount) if amount < 0 else "", amount if amount > 0 else ""])
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=statement_{statement_id}_qbo.csv"}
        )

    elif format == "xero":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Date", "Payee", "Description", "Reference", "Amount"])
        for t in transactions:
            writer.writerow([t.date, t.description, t.category, t.id, float(t.amount)])
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=statement_{statement_id}_xero.csv"}
        )
        
    elif format == "excel":
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        
        wb = Workbook()
        ws = wb.active
        ws.title = "Transactions"
        headers = ["Date", "Description", "Category", "Amount", "Type", "Running Balance"]
        ws.append(headers)
        for col in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        for t in transactions:
            ws.append([
                t.date, t.description, t.category, float(t.amount),
                t.tx_type, float(t.running_balance) if t.running_balance is not None else None
            ])
        for row in range(2, ws.max_row + 1):
            ws.cell(row=row, column=4).number_format = '"$"#,##0.00'
            ws.cell(row=row, column=6).number_format = '"$"#,##0.00'
        for col in ws.columns:
            max_length = max((len(str(cell.value)) for cell in col if cell.value is not None), default=0)
            ws.column_dimensions[col[0].column_letter].width = min(max_length + 2, 50)
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return Response(
            content=output.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=statement_{statement_id}.xlsx"}
        )

    elif format == "pdf":
        from fpdf import FPDF
        
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "TaxFlow Pro - Statement Summary", ln=True, align="C")
        pdf.ln(10)
        pdf.set_font("Helvetica", "B", 12)
        pdf.multi_cell(0, 8, f"Statement: {statement.filename}")
        pdf.multi_cell(0, 8, f"Period: {statement.period_start or 'N/A'} to {statement.period_end or 'N/A'}")
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Reconciliation", ln=True)
        pdf.set_font("Helvetica", "", 12)
        open_bal = float(statement.opening_balance) if statement.opening_balance is not None else 0.0
        close_bal = float(statement.closing_balance) if statement.closing_balance is not None else 0.0
        variance = float(statement.variance) if statement.variance is not None else 0.0
        pdf.cell(90, 8, f"Opening Balance: ${open_bal:,.2f}", ln=True)
        pdf.cell(90, 8, f"Closing Balance: ${close_bal:,.2f}", ln=True)
        pdf.cell(90, 8, f"Variance: ${variance:,.2f}", ln=True)
        pdf.cell(90, 8, f"Balanced: {'Yes' if statement.is_balanced else 'No'}", ln=True)
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Category Summary", ln=True)
        pdf.set_font("Helvetica", "", 12)
        cat_totals = defaultdict(float)
        for t in transactions:
            cat_totals[t.category] += float(t.amount)
        for cat, total in sorted(cat_totals.items(), key=lambda x: abs(x[1]), reverse=True):
            pdf.multi_cell(0, 8, f"{cat}: ${total:,.2f}")
        return Response(
            content=pdf.output(dest='B'),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=statement_{statement_id}_summary.pdf"}
        )

    elif format == "parquet":
        try:
            import pandas as pd
        except ImportError:
            raise HTTPException(status_code=500, detail="pandas not installed")
        data = [{
            "id": t.id, "date": t.date, "description": t.description,
            "amount": float(t.amount), "tx_type": t.tx_type, "category": t.category,
            "running_balance": float(t.running_balance) if t.running_balance is not None else None
        } for t in transactions]
        df = pd.DataFrame(data)
        output_parquet = io.BytesIO()
        df.to_parquet(output_parquet, engine="pyarrow", index=False)
        output_parquet.seek(0)
        return Response(
            content=output_parquet.getvalue(),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename=statement_{statement_id}.parquet"}
        )

    elif format == "qif":
        lines = ["!Account", "NExported", "^", "!Type:Bank"]
        for t in transactions:
            lines.append(f"D{t.date}")
            lines.append(f"P{t.description}")
            lines.append(f"T{t.amount}")
            lines.append(f"L{t.category}")
            lines.append("^")
        return Response(
            content="\n".join(lines),
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename=statement_{statement_id}.qif"}
        )
    
    else:
        raise HTTPException(status_code=400, detail="Format must be json, csv, qbo, xero, excel, pdf, parquet, or qif")
