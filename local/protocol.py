"""Protocol helpers: newline-delimited JSON over asyncio streams."""
import asyncio
import json
from typing import Any, Dict, Optional


async def send_msg(writer: asyncio.StreamWriter, obj: Dict[str, Any]) -> None:
    data = json.dumps(obj, ensure_ascii=False) + "\n"
    writer.write(data.encode())
    await writer.drain()


async def recv_msg(reader: asyncio.StreamReader) -> Optional[Dict[str, Any]]:
    try:
        line = await reader.readline()
    except Exception:
        return None
    if not line:
        return None
    try:
        return json.loads(line.decode().strip())
    except Exception:
        return None


def make_msg(tipo: str, source: str, id_: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"tipo": tipo, "source": source, "id": id_, "payload": payload}
