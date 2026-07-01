import hashlib
import json
import mimetypes
import os
import re
import zipfile
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"
REGISTRY_PATH = DATA_DIR / "hash_registry.json"
DISCUSSION_REGISTRATIONS_PATH = DATA_DIR / "discussion_registrations.json"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8091


def ensure_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for path in (REGISTRY_PATH, DISCUSSION_REGISTRATIONS_PATH):
        if not path.exists():
            path.write_text("[]", encoding="utf-8")


def read_registry() -> list[dict]:
    ensure_storage()
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def write_registry(records: list[dict]) -> None:
    ensure_storage()
    REGISTRY_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def read_discussion_registrations() -> list[dict]:
    ensure_storage()
    return json.loads(DISCUSSION_REGISTRATIONS_PATH.read_text(encoding="utf-8"))


def write_discussion_registrations(records: list[dict]) -> None:
    ensure_storage()
    DISCUSSION_REGISTRATIONS_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def calculate_sha256(path: Path) -> str:
    sha256_hash = hashlib.sha256()
    with path.open("rb") as file:
        for byte_block in iter(lambda: file.read(1024 * 1024), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def normalize_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def sentence_count(text: str) -> int:
    sentences = re.split(r"(?<=[.!?…])\s+", text)
    return len([sentence for sentence in sentences if len(sentence.strip()) > 5])


def first_annotation_candidate(paragraphs: list[str]) -> str | None:
    for paragraph in paragraphs:
        cleaned = normalize_text(paragraph)
        if len(cleaned) >= 80 and sentence_count(cleaned) >= 2:
            return cleaned[:1200]
    return None


def xml_text_values(xml_data: bytes) -> list[str]:
    root = ElementTree.fromstring(xml_data)
    values = []
    for element in root.iter():
        if element.text and element.text.strip():
            values.append(element.text.strip())
    return values


def extract_docx_paragraphs(path: Path) -> list[str]:
    paragraphs = []
    with zipfile.ZipFile(path) as archive:
        document_xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(document_xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    for paragraph in root.findall(".//w:p", namespace):
        texts = [
            node.text
            for node in paragraph.findall(".//w:t", namespace)
            if node.text
        ]
        if texts:
            paragraphs.append("".join(texts))
    return paragraphs


def extract_pptx_paragraphs(path: Path) -> list[str]:
    paragraphs = []
    with zipfile.ZipFile(path) as archive:
        slide_names = sorted(name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml"))
        for slide_name in slide_names[:5]:
            values = xml_text_values(archive.read(slide_name))
            if values:
                paragraphs.append(" ".join(values))
    return paragraphs


def extract_opendocument_paragraphs(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        values = xml_text_values(archive.read("content.xml"))
    return [" ".join(values)]


def extract_rtf_paragraphs(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    raw = re.sub(r"\\par[d]?", "\n", raw)
    raw = re.sub(r"\\'[0-9a-fA-F]{2}", " ", raw)
    raw = re.sub(r"\\[a-zA-Z]+-?\d* ?", " ", raw)
    raw = raw.replace("{", " ").replace("}", " ")
    return [part.strip() for part in raw.splitlines() if part.strip()]


def extract_plain_paragraphs(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    paragraphs = re.split(r"\n\s*\n|\r\n\s*\r\n", text)
    if len(paragraphs) == 1:
        paragraphs = text.splitlines()
    return paragraphs


def extract_annotation(path: Path) -> dict:
    extension = path.suffix.lower()
    extractors = {
        ".docx": extract_docx_paragraphs,
        ".pptx": extract_pptx_paragraphs,
        ".odt": extract_opendocument_paragraphs,
        ".odp": extract_opendocument_paragraphs,
        ".rtf": extract_rtf_paragraphs,
        ".txt": extract_plain_paragraphs,
        ".md": extract_plain_paragraphs,
        ".csv": extract_plain_paragraphs,
    }

    extractor = extractors.get(extension)
    if not extractor:
        return {
            "status": "unsupported",
            "text": None,
            "message": f"Автоматическая аннотация для формата {extension or 'без расширения'} пока не поддерживается.",
        }

    try:
        paragraphs = extractor(path)
        annotation = first_annotation_candidate(paragraphs)
        if annotation:
            return {
                "status": "found",
                "text": annotation,
                "message": "Аннотация найдена автоматически.",
            }
        return {
            "status": "not_found",
            "text": None,
            "message": "Подходящий фрагмент для аннотации не найден.",
        }
    except Exception as error:
        return {
            "status": "error",
            "text": None,
            "message": f"Не удалось извлечь аннотацию: {error}",
        }


def safe_file_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = PROJECT_DIR / path

    resolved = path.resolve()
    project_root = PROJECT_DIR.resolve()
    if project_root not in resolved.parents and resolved != project_root:
        raise ValueError("Файл должен находиться внутри папки work.")
    if not resolved.exists() or not resolved.is_file():
        raise FileNotFoundError("Файл не найден.")
    return resolved


def build_record(payload: dict) -> dict:
    file_path = safe_file_path(str(payload.get("file_path", "")))
    file_hash = calculate_sha256(file_path)
    records = read_registry()
    existing = next((item for item in records if item["sha256"] == file_hash), None)
    now = datetime.now().isoformat(timespec="seconds")
    annotation = existing.get("annotation") if existing else extract_annotation(file_path)

    record = {
        "id": existing["id"] if existing else f"hash-{int(datetime.now().timestamp())}",
        "sha256": file_hash,
        "status": "duplicate" if existing else "registered",
        "registered_at": existing["registered_at"] if existing else now,
        "checked_at": now,
        "file_name": payload.get("file_name") or file_path.name,
        "file_path": str(file_path.relative_to(PROJECT_DIR)),
        "file_size": file_path.stat().st_size,
        "mime_type": mimetypes.guess_type(file_path.name)[0] or "application/octet-stream",
        "author": payload.get("author"),
        "telegram_user_id": payload.get("telegram_user_id"),
        "telegram_username": payload.get("telegram_username"),
        "branch": payload.get("branch"),
        "source": payload.get("source", "unknown"),
        "submission_id": payload.get("submission_id"),
        "annotation": annotation,
    }

    if existing:
        return record

    records.append(record)
    write_registry(records)
    return record


def save_discussion_registration(payload: dict) -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    registration = {
        "telegram_user_id": payload.get("telegram_user_id"),
        "telegram_username": payload.get("telegram_username"),
        "fio": payload.get("fio"),
        "source": payload.get("source", "discussion_bot"),
        "registered_at": payload.get("registered_at") or now,
        "synced_at": now,
    }
    records = [
        item for item in read_discussion_registrations()
        if item.get("telegram_user_id") != registration["telegram_user_id"]
    ]
    records.append(registration)
    write_discussion_registrations(records)
    return registration


class HashApiHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, data: dict | list) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self._send_json(200, {"ok": True})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if parsed.path == "/health":
            self._send_json(200, {"ok": True, "service": "dp-hash-service"})
            return

        if parsed.path == "/api/v1/records":
            limit = int(query.get("limit", ["20"])[0])
            records = sorted(read_registry(), key=lambda item: item["registered_at"], reverse=True)
            self._send_json(200, records[:limit])
            return

        if parsed.path == "/api/v1/records/by-hash":
            value = query.get("sha256", [""])[0].strip().lower()
            record = next((item for item in read_registry() if item["sha256"] == value), None)
            self._send_json(200, {"found": bool(record), "record": record})
            return

        if parsed.path == "/api/v1/discussion-registrations":
            limit = int(query.get("limit", ["50"])[0])
            records = sorted(
                read_discussion_registrations(),
                key=lambda item: item["registered_at"],
                reverse=True,
            )
            self._send_json(200, records[:limit])
            return

        self._send_json(404, {"error": "Маршрут не найден."})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in ("/api/v1/documents/register", "/api/v1/discussion-registrations"):
            self._send_json(404, {"error": "Маршрут не найден."})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            record = (
                build_record(payload)
                if parsed.path == "/api/v1/documents/register"
                else save_discussion_registration(payload)
            )
            self._send_json(200, record)
        except Exception as error:
            self._send_json(400, {"error": str(error)})


def main() -> None:
    ensure_storage()
    host = os.getenv("HASH_SERVICE_HOST", DEFAULT_HOST)
    port = int(os.getenv("HASH_SERVICE_PORT", str(DEFAULT_PORT)))
    server = ThreadingHTTPServer((host, port), HashApiHandler)
    print(f"Hash API started: http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
