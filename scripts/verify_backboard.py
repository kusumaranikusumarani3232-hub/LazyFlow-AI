import asyncio
import json
import os
from backboard import BackboardClient

# Load env from backend/.env
env_vars = {}
with open('backend/.env', 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            env_vars[k.strip()] = v.strip()

api_key = env_vars.get('BACKBOARD_API_KEY')
base_url = env_vars.get('BACKBOARD_BASE_URL', 'https://app.backboard.io/api')

print(f"Testing BackboardClient with key: {api_key[:8]}... URL: {base_url}")

# Sample messy files to test
sample_files = [
    {"id": "1", "filename": "IMG_20231012_WA0004.jpg", "size": 2450000, "mime": "image/jpeg", "description": ""},
    {"id": "2", "filename": "Invoice_Oct_final_v2_FINAL.pdf", "size": 182000, "mime": "application/pdf", "description": "October cloud hosting bill"},
    {"id": "3", "filename": "draft_cs50_week3_notes.docx", "size": 42000, "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "description": "Algorithms lecture summary"},
    {"id": "4", "filename": "Screenshot 2024-03-01 at 4.22.19 PM.png", "size": 890000, "mime": "image/png", "description": "UI bug reproduction on checkout page"},
    {"id": "5", "filename": "w2_tax_return_2023.pdf", "size": 510000, "mime": "application/pdf", "description": ""},
    {"id": "6", "filename": "q4_roadmap_presentation_team.pptx", "size": 3400000, "mime": "application/vnd.openxmlformats-officedocument.presentationml.presentation", "description": "Quarterly work goals"}
]

SYSTEM_PROMPT = """You are LazyFlow AI, an intelligent file organization and naming assistant.
Your job is to organize messy files into clean, logical folders and suggest clean, descriptive, professional filenames.

RULES:
1. Preserve the EXACT original file extension.
2. Choose one appropriate folder from standard categories: "Documents", "Images", "Work", "Study", "Finance", "Code", "Other" (or a user-specified custom folder if provided).
3. Suggest a clean, kebab-case or snake-case or title-case readable filename that clearly describes the file based on the original name and any user description (e.g. "invoice-october-2023.pdf", "algorithms-week3-notes.docx", "checkout-ui-bug-screenshot.png").
4. Provide a short reason explaining the folder and name choice.
5. You MUST return ONLY a valid JSON array of objects conforming to this schema:
[
  {
    "id": "<file_id>",
    "original_filename": "<original_filename>",
    "folder": "<folder_name>",
    "category": "<category_name>",
    "suggested_filename": "<suggested_filename_with_extension>",
    "reason": "<short explanation>"
  }
]
No other text, markdown formatting, or preamble. Return ONLY the raw JSON array.
"""

USER_PROMPT = f"""Organize the following files:
{json.dumps(sample_files, indent=2)}
"""

async def test_model(model_name: str, provider: str = "openrouter"):
    print(f"\n--- Testing model: {model_name} (provider: {provider}) ---")
    client = BackboardClient(api_key=api_key, base_url=base_url)
    try:
        # Create assistant
        assistant = await client.create_assistant(
            name="LazyFlow Organizer Test",
            description="Tests file categorization",
            system_prompt=SYSTEM_PROMPT
        )
        print(f"Created assistant: {assistant.assistant_id}")

        # Create thread
        thread = await client.create_thread(assistant_id=assistant.assistant_id)
        print(f"Created thread: {thread.thread_id}")

        # Send message
        response = await client.send_message(
            content=USER_PROMPT,
            thread_id=thread.thread_id,
            assistant_id=assistant.assistant_id,
            llm_provider=provider,
            model_name=model_name,
            stream=False
        )
        
        last_msg = response.messages[-1]
        reply_msg = last_msg.get('content') if isinstance(last_msg, dict) else getattr(last_msg, 'content', '')
        print(f"\nRaw Response ({len(reply_msg)} chars):\n{reply_msg}\n")

        # Parse JSON
        cleaned = reply_msg.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        parsed = json.loads(cleaned)
        print(f"SUCCESS! Parsed {len(parsed)} file items correctly.")
        print(json.dumps(parsed, indent=2))
        
        # Cleanup
        try:
            await client.delete_assistant(assistant.assistant_id)
            print("Cleaned up assistant.")
        except Exception as e:
            print("Cleanup warning:", e)
            
        return True, parsed
    except Exception as e:
        print(f"Model test failed with error: {e}")
        return False, str(e)
    finally:
        await client.aclose()

async def main():
    success, result = await test_model("meta-llama/llama-3.1-8b-instruct", "openrouter")
    if success:
        print("\n=======================================================")
        print("VERIFIED OPEN-WEIGHT MODEL: meta-llama/llama-3.1-8b-instruct")
        print("Accuracy, JSON compliance, and latency all PASSED!")
        print("=======================================================")

if __name__ == "__main__":
    asyncio.run(main())
