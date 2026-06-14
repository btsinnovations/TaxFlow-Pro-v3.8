import csv
import io
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from ..database import get_db
from .. import models
from .auth import get_current_user

router = APIRouter(prefix="/export", tags=["export"])

@router.get("/statement/{statement_id}")
def export_statement(statement_id: int,
                     format: str = "csv",
                     db: Session = Depends(get_db),
                     current_user: models.User = Depends(get_current_user)):
    statement = db.query(models.Statement).join(models.Account).filter(
        models.Statement.id == statement_id,
        models.Account.user_id == current_user.id
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
                dt = datetime.strptime(t.date, "%Y-%m-%d")
                qbo_date = dt.strftime("%m/%d/%Y")
            except (ValueError, TypeError):
                qbo_date = t.date
                
            amount = float(t.amount)
            withdrawals = abs(amount) if amount < 0 else ""
            deposits = amount if amount > 0 else ""
            
            writer.writerow([qbo_date, t.description, withdrawals, deposits])
            
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
            amount = float(t.amount)
            writer.writerow([t.date, t.description, t.category, t.id, amount])
            
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=statement_{statement_id}_xero.csv"}
        )
        
    elif format == "excel":
        wb = Workbook()
        ws = wb.active
        ws.title = "Transactions"
        
        headers = ["Date", "Description", "Category", "Amount", "Type", "Running Balance"]
        ws.append(headers)
        
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        for col in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col)
            cell.font = header_font
            cell.fill = header_fill
            
        for t in transactions:
            ws.append([
                t.date,
                t.description,
                t.category,
                float(t.amount),
                t.tx_type,
                float(t.running_balance) if t.running_balance is not None else None
            ])
            
        for row in range(2, ws.max_row + 1):
            ws.cell(row=row, column=4).number_format = '"$"#,##0.00'
            ws.cell(row=row, column=6).number_format = '"$"#,##0.00'
            
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except Exception:
                    pass
            ws.column_dimensions[column].width = max_length + 2

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        
        return Response(
            content=output.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=statement_{statement_id}.xlsx"}
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
        raise HTTPException(status_code=400, detail="Format must be json, csv, qif, excel, qbo, or xero")
