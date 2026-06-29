#!/usr/bin/env python3
"""
Watchdog – monitors a folder for new PDF/CSV files and runs the pipeline.
Usage: python -m phase3_pipeline.watchdog --input-dir <dir> --output-dir <dir> --format qif
"""
import time
import argparse
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import subprocess
import sys

class PDFHandler(FileSystemEventHandler):
    def __init__(self, output_dir, output_format):
        self.output_dir = Path(output_dir)
        self.output_format = output_format
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() in ['.pdf', '.csv']:
            print(f"New file detected: {path}")
            out_file = self.output_dir / f"{path.stem}_processed.{self.output_format}"
            cmd = [
                sys.executable, "-m", "phase3_pipeline.main",
                str(path), str(out_file), self.output_format
            ]
            print(f"Running: {' '.join(cmd)}")
            subprocess.run(cmd)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True, help="Folder to watch")
    parser.add_argument("--output-dir", default="./output", help="Output folder")
    parser.add_argument("--format", default="qif", choices=["qif", "csv"])
    args = parser.parse_args()
    
    event_handler = PDFHandler(args.output_dir, args.format)
    observer = Observer()
    observer.schedule(event_handler, args.input_dir, recursive=False)
    observer.start()
    print(f"Watching {args.input_dir} for new PDF/CSV files...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()