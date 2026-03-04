import csv, io
from typing import Any

def generate_csv(data: list[dict[str, Any]]) -> io.BytesIO:
    if not data:
        buffer = io.BytesIO()
        buffer.write(b"No data available")
        buffer.seek(0)
        return buffer
    
    string_buffer = io.StringIO()
    headers = list(data[0].keys())
    writer = csv.DictWriter(string_buffer, fieldnames=headers)
    writer.writeheader()
    writer.writerows(data)

    byte_buffer = io.BytesIO(string_buffer.getvalue().encode("utf-8"))
    byte_buffer.seek(0)
    return byte_buffer