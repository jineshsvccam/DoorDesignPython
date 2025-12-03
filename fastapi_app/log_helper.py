"""
Log parsing helper functions for app.log analysis.

This module contains utility functions for parsing and processing
application logs to extract execution summaries and file generation statistics.
"""

import json
import os
import re
from typing import Optional


def extract_timestamp(line: str) -> str:
    """Extract timestamp from log line (first 19 characters for YYYY-MM-DD HH:MM:SS)."""
    # Handle both formats: "2025-12-01 11:18:23" and "2025-12-01 11:18:23,123456"
    # Extract first 19 chars which gives us "YYYY-MM-DD HH:MM:SS"
    return line[:19] if len(line) >= 19 else line


def extract_time_only(timestamp: str) -> str:
    """Extract time portion from full timestamp (HH:MM:SS)."""
    return timestamp[11:19] if len(timestamp) > 19 else timestamp


def parse_json_log_entry(line: str) -> Optional[dict]:
    """Parse JSON log entry from line, return None if invalid."""
    if "{" not in line or "}" not in line:
        return None
    try:
        json_start = line.index("{")
        json_str = line[json_start:]
        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        return None


def extract_filename_from_path(line: str, pattern: str) -> Optional[str]:
    """Extract filename using regex pattern."""
    match = re.search(pattern, line)
    return os.path.basename(match.group(1)) if match else None


def is_file_in_time_range(file_time: str, start_time: str, end_time: Optional[str]) -> bool:
    """Check if file timestamp falls within session time range."""
    if end_time:
        return start_time <= file_time <= end_time
    return file_time >= start_time


def process_request_start(log_entry: dict, line: str, single_dxf_sessions: dict, 
                         bulk_sessions: dict, counters: dict):
    """Process request.start event and update session tracking."""
    request_id = log_entry.get("request_id")
    path = log_entry.get("path", "")
    timestamp = log_entry.get("timestamp") or extract_timestamp(line)
    
    if "/generate-single-dxf" in path:
        counters["total_requests"] += 1
        single_dxf_sessions[request_id] = {
            "request_id": request_id,
            "start_time": timestamp,
            "dxf_file": None,
            "pdf_file": None,
            "execution_time": None,
            "status": "Pending"
        }
    elif "/generate-dxf/" in path:
        counters["total_requests"] += 1
        counters["bulk_executions"] += 1
        bulk_sessions[request_id] = {
            "request_id": request_id,
            "start_time": timestamp,
            "end_time": None,
            "files": [],
            "execution_time": None,
            "status": "Pending"
        }


def process_request_finish(log_entry: dict, line: str, single_dxf_sessions: dict, 
                          bulk_sessions: dict):
    """Process request.finish event and update execution status."""
    request_id = log_entry.get("request_id")
    process_time = log_entry.get("process_time_s")
    status_code = log_entry.get("status_code")
    timestamp = log_entry.get("timestamp") or extract_timestamp(line)
    
    status = "Success" if status_code == 200 else "Error"
    execution_time = f"{process_time}s"
    
    if request_id in single_dxf_sessions:
        single_dxf_sessions[request_id]["execution_time"] = execution_time
        single_dxf_sessions[request_id]["status"] = status
    
    if request_id in bulk_sessions:
        bulk_sessions[request_id]["execution_time"] = execution_time
        bulk_sessions[request_id]["status"] = status
        bulk_sessions[request_id]["end_time"] = timestamp


def process_dxf_generation(line: str, single_dxf_sessions: dict, all_dxf_files: list, 
                          counters: dict):
    """Process DXF file generation log entry."""
    counters["dxf_files"] += 1
    timestamp = extract_timestamp(line)
    filename = extract_filename_from_path(line, r"'([^']+\.dxf)'")
    
    if filename:
        all_dxf_files.append({"timestamp": timestamp, "filename": filename})
        
        # Associate with single DXF session by matching timestamp
        for session in single_dxf_sessions.values():
            if session["dxf_file"] is None and session["start_time"][:16] == timestamp[:16]:
                session["dxf_file"] = filename
                break


def process_response_log(line: str, all_dxf_files: list):
    """Process 'Response logged to' entries for bulk executions."""
    timestamp = extract_timestamp(line)
    # Match filename before _response.json
    # Pattern matches: .../_P 51.dxf_response.json -> P 51.dxf
    # Uses [_\\/] to match underscore or path separator before filename
    match = re.search(r'[_\\/]([^_\\/]+\.dxf)_response\.json', line)
    
    if match:
        filename = match.group(1)
        # Avoid duplicates
        if not any(f["filename"] == filename for f in all_dxf_files):
            all_dxf_files.append({"timestamp": timestamp, "filename": filename})


def process_pdf_generation(line: str, single_dxf_sessions: dict, counters: dict):
    """Process PDF file generation log entry."""
    counters["pdf_files"] += 1
    timestamp = extract_timestamp(line)
    filename = extract_filename_from_path(line, r"'([^']+\.pdf)'")
    
    if filename:
        # Associate with single DXF session by matching timestamp
        for session in single_dxf_sessions.values():
            if session["pdf_file"] is None and session["start_time"][:16] == timestamp[:16]:
                session["pdf_file"] = filename
                break


def build_single_executions(single_dxf_sessions: dict) -> tuple:
    """Convert single DXF sessions to execution list and return set of single files."""
    executions = []
    single_files_set = set()
    
    for session in single_dxf_sessions.values():
        if session["dxf_file"] or session["status"] != "Pending":
            # Track files from this session
            if session["dxf_file"]:
                single_files_set.add(session["dxf_file"])
            if session["pdf_file"]:
                single_files_set.add(session["pdf_file"])
            
            executions.append({
                "time": extract_time_only(session["start_time"]),
                "dxf_file": session["dxf_file"] or "Not generated",
                "pdf_file": session["pdf_file"] or "❌ Not requested",
                "status": session["status"],
                "execution_time": session["execution_time"] or "N/A",
                "is_bulk": False
            })
    
    return executions, single_files_set


def associate_bulk_files(all_dxf_files: list, single_files_set: set, bulk_sessions: dict):
    """Associate DXF files with bulk execution sessions based on timestamp ranges."""
    for dxf_entry in all_dxf_files:
        if dxf_entry["filename"] in single_files_set:
            continue
        
        # Find matching bulk session (iterate from most recent)
        for session in sorted(bulk_sessions.values(), key=lambda x: x["start_time"], reverse=True):
            if is_file_in_time_range(dxf_entry["timestamp"], session["start_time"], 
                                    session.get("end_time")):
                session["files"].append(dxf_entry["filename"])
                break


def build_bulk_executions(bulk_sessions: dict) -> list:
    """Convert bulk sessions to execution list."""
    executions = []
    
    for session in bulk_sessions.values():
        if session["files"] or session["execution_time"]:
            executions.append({
                "time": extract_time_only(session["start_time"]),
                "file_count": len(session["files"]),
                "files": session["files"],
                "status": session["status"],
                "execution_time": session["execution_time"] or "N/A",
                "is_bulk": True
            })
    
    return executions
