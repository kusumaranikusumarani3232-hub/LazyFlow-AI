import os

os.makedirs('sample_data', exist_ok=True)

samples = {
    'Invoice_Oct_final_v2_FINAL.pdf': b'%PDF-1.4 Mock Cloud Hosting Invoice $149.00 October 2023',
    'IMG_20231012_WA0004.jpg': b'\xff\xd8\xff\xe0\x00\x10JFIF Mock WhatsApp Photo from holiday',
    'draft_cs50_week3_notes.docx': b'PK\x03\x04 Mock CS50 Lecture 3 Algorithms and Binary Search Notes',
    'Screenshot 2024-03-01 at 4.22.19 PM.png': b'\x89PNG\r\n\x1a\n Mock UI Bug Screenshot on checkout button',
    'w2_tax_return_2023.pdf': b'%PDF-1.4 Mock 2023 W2 Wage and Tax Statement Form',
    'q4_roadmap_presentation_team.pptx': b'PK\x03\x04 Mock Q4 Company Roadmap & Milestone Slide Deck',
    'dump_users_export_v1_backup.csv': b'id,name,role,department\n1,Alice,Dev,Engineering\n2,Bob,PM,Product\n',
    'meeting_notes_sync_standup.txt': b'Monday Standup:\n- Shipped bugfix\n- Planning file organizer app',
    'app_config_staging_debug.json': b'{"env": "staging", "debug": true, "version": "1.0.0"}\n'
}

for fname, content in samples.items():
    path = os.path.join('sample_data', fname)
    with open(path, 'wb') as fp:
        fp.write(content)

print(f'Generated {len(samples)} realistic sample files in sample_data/')
