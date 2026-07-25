# main.py
from config import TECH_SOURCES

from config import NOTION_TOKEN, NOTION_DATABASE_ID
from outputs.notion_writer import NotionWriter


def main():
    notion_writer = NotionWriter(NOTION_TOKEN, NOTION_DATABASE_ID)
    test_title = "Test Article"
    test_summary = "This is a test summary created by the agent."
    test_url = "https://example.com/test-article"

    response = notion_writer.create_summary_page(test_title, test_summary, test_url)
    print("Created Notion page:", response["id"])

if __name__ == "__main__":
    main()
