#!/usr/bin/env python3
"""
Train offline ML categorizer from HomeBank CSV export.
Usage: python -m phase3_pipeline.train_categorizer training_data.csv
"""
import sys
import pandas as pd
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import cross_val_predict
from sklearn.metrics import accuracy_score
import numpy as np
from .text_utils import clean_text

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    csv_path = sys.argv[1]
    df = pd.read_csv(csv_path)
    
    # Required columns: 'Date', 'Payee', 'Description', 'Category', 'Amount'
    df['text'] = df['Payee'].fillna('') + " " + df['Description'].fillna('')
    df['text'] = df['text'].apply(clean_text)
    
    X = df['text']
    y = df['Category']
    
    # Pipeline
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(ngram_range=(1,2), max_features=5000)),
        ('clf', LogisticRegression(max_iter=1000, class_weight='balanced'))
    ])
    
    # Cross-validated predictions to estimate real performance
    y_pred = cross_val_predict(pipeline, X, y, cv=5)
    acc = accuracy_score(y, y_pred)
    print(f"Cross‑validation accuracy: {acc:.3f}")
    
    # Train on full data
    pipeline.fit(X, y)
    
    # Determine optimal confidence threshold (simplified – you can adjust)
    threshold = 0.7
    
    # Save model
    model_data = {
        'pipeline': pipeline,
        'classes': pipeline.classes_,
        'threshold': threshold
    }
    joblib.dump(model_data, "ml_model.pkl")
    print(f"Model saved to ml_model.pkl (threshold={threshold})")

if __name__ == "__main__":
    main()