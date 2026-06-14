import csv
import io
import json
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
    statement = db.query(models.Statement).join(models.Account).filter(
        models.Statement.id == statement_id,
        models.Account.user_id == current_user.id
    ).first()
    if not statement:
        raise HTTPException(status_code=404, detail="Statement not found")
    
    transactions = db.query(models.Transaction).filter(
        models.Transaction.statement_id == statement_id
    ).all()
    
    if format == "json":
        data = [{
            "id": t.id, "date": t.date, "description": t.description,
            "amount": float(t.amount), "type": t.tx_type, "category": t.category,
            "running_balance": float(t.running_balance) if t.running_balance else None
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
                float(t.running_balance) if t.running_balance else ""
            ])
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=statement_{statement_id}.csv"}
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
        raise HTTPException(status_code=400, detail="Format must be json, csv, or qif")
