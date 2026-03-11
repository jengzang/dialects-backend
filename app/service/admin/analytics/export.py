"""
Data Export Module

Exports analytics data in various formats (CSV, Excel, JSON).
"""

import csv
import json
import io
from typing import List, Dict, Any, Optional
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from fastapi.responses import StreamingResponse


def export_to_csv(data: List[Dict[str, Any]], filename: str) -> StreamingResponse:
    """
    Export data to CSV format.

    Args:
        data: List of dictionaries to export
        filename: Output filename

    Returns:
        StreamingResponse with CSV data
    """
    if not data:
        # Return empty CSV
        output = io.StringIO()
        output.write("No data available\n")
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    # Create CSV
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=data[0].keys())
    writer.writeheader()
    writer.writerows(data)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


def export_to_excel(data: List[Dict[str, Any]], filename: str, sheet_name: str = "Data") -> StreamingResponse:
    """
    Export data to Excel format.

    Args:
        data: List of dictionaries to export
        filename: Output filename
        sheet_name: Excel sheet name

    Returns:
        StreamingResponse with Excel data
    """
    # Create workbook
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name

    if not data:
        ws.append(["No data available"])
    else:
        # Write headers
        headers = list(data[0].keys())
        ws.append(headers)

        # Style headers
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center")

        # Write data
        for row in data:
            ws.append([row.get(key, "") for key in headers])

        # Auto-adjust column widths
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width

    # Save to bytes
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


def export_to_json(data: Any, filename: str) -> StreamingResponse:
    """
    Export data to JSON format.

    Args:
        data: Data to export (can be dict or list)
        filename: Output filename

    Returns:
        StreamingResponse with JSON data
    """
    json_str = json.dumps(data, ensure_ascii=False, indent=2)

    return StreamingResponse(
        iter([json_str]),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


def flatten_dict(d: Dict[str, Any], parent_key: str = '', sep: str = '_') -> Dict[str, Any]:
    """
    Flatten nested dictionary for CSV/Excel export.

    Args:
        d: Dictionary to flatten
        parent_key: Parent key for recursion
        sep: Separator for nested keys

    Returns:
        Flattened dictionary
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            # Convert list to string
            items.append((new_key, str(v)))
        else:
            items.append((new_key, v))
    return dict(items)


def export_data(
    data: Any,
    export_format: str,
    filename: str,
    flatten: bool = False
) -> StreamingResponse:
    """
    Export data in specified format.

    Args:
        data: Data to export
        export_format: 'csv', 'xlsx', or 'json'
        filename: Output filename (without extension)
        flatten: Whether to flatten nested structures for CSV/Excel

    Returns:
        StreamingResponse with exported data
    """
    # Ensure filename has correct extension
    if not filename.endswith(f".{export_format}"):
        if export_format == "xlsx":
            filename = f"{filename}.xlsx"
        elif export_format == "csv":
            filename = f"{filename}.csv"
        elif export_format == "json":
            filename = f"{filename}.json"

    # Handle different data types
    if isinstance(data, dict):
        # If dict has a 'users' or similar key with list, use that
        if "users" in data and isinstance(data["users"], list):
            export_list = data["users"]
        elif "segments" in data and isinstance(data["segments"], list):
            export_list = data["segments"]
        elif "trends" in data and isinstance(data["trends"], list):
            export_list = data["trends"]
        elif "apis" in data and isinstance(data["apis"], list):
            export_list = data["apis"]
        else:
            # Export the dict as-is for JSON, or convert to single-row list for CSV/Excel
            if export_format == "json":
                return export_to_json(data, filename)
            else:
                export_list = [data]
    elif isinstance(data, list):
        export_list = data
    else:
        # Unsupported data type
        export_list = [{"data": str(data)}]

    # Flatten if requested and format is CSV/Excel
    if flatten and export_format in ["csv", "xlsx"]:
        export_list = [flatten_dict(item) if isinstance(item, dict) else item for item in export_list]

    # Export based on format
    if export_format == "csv":
        return export_to_csv(export_list, filename)
    elif export_format == "xlsx":
        return export_to_excel(export_list, filename)
    elif export_format == "json":
        return export_to_json(data, filename)
    else:
        raise ValueError(f"Unsupported export format: {export_format}")
