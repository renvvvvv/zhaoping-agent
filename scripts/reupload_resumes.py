import asyncio
import json
import os
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.feishu_service import feishu_client
from app.utils.email_parser import parse_boss_subject, get_resume_source

DATA_FILE = "./data/email_history.json"
UPLOAD_DIR = "./uploads/resumes"


async def reupload():
    if not os.path.exists(DATA_FILE):
        print("No email history found")
        return

    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    emails = data.get("emails", [])
    resume_emails = [e for e in emails if e.get("email_type") == "resume" and e.get("status") == "success"]

    print(f"Found {len(resume_emails)} resume emails to re-upload\n")

    for email in resume_emails:
        email_id = email["id"]
        subject = email.get("subject", "")
        sender_email = email.get("sender_email", "")
        pdf_filename = email.get("pdf_filename", "")

        if not pdf_filename:
            print(f"[{email_id}] No PDF filename, skipping")
            continue

        # Find local PDF file
        pdf_path = os.path.join(UPLOAD_DIR, pdf_filename)
        if not os.path.exists(pdf_path):
            print(f"[{email_id}] PDF not found: {pdf_path}, skipping")
            continue

        # Parse subject
        parsed = parse_boss_subject(subject)
        candidate_name = parsed.get("candidate_name") or sender_email.split("@")[0]
        resume_source = get_resume_source(sender_email)

        print(f"Re-uploading: {candidate_name} | {parsed.get('job_title')} | {subject[:50]}")

        try:
            with open(pdf_path, 'rb') as f:
                file_content = f.read()

            result = await feishu_client.create_record_with_resume(
                candidate_name=candidate_name,
                email=sender_email,
                file_name=pdf_filename,
                file_content=file_content,
                job_title=parsed.get("job_title"),
                location=parsed.get("location"),
                salary=parsed.get("salary"),
                experience=parsed.get("experience"),
                resume_source=resume_source,
                additional_fields={
                    "邮件主题": subject,
                    "重新上传时间": "2026-05-21",
                    "原始文件名": pdf_filename
                }
            )

            record_id = result.get("data", {}).get("record", {}).get("record_id")
            print(f"  -> Success, record_id: {record_id}\n")

            # Update history with new record_id
            email["feishu_record_id"] = record_id

        except Exception as e:
            print(f"  -> Failed: {e}\n")

    # Save updated history
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("Done. Updated email_history.json with new record IDs.")


if __name__ == "__main__":
    asyncio.run(reupload())
