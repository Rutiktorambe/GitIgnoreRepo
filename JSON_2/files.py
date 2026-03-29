import ijson
import json
import pandas as pd

def remove_deleted_quotes_stream(json_path, excel_path, output_path):
    deleted_df = pd.read_excel(excel_path, sheet_name="Main", usecols=["QuoteID"])
    deleted_ids = set(deleted_df["QuoteID"].astype(str).str.strip().tolist())

    filtered_quotes = []
    with open(json_path, "r", encoding="utf-8") as f:
        for quote in ijson.items(f, "Quotes.item"):
            qid = str(quote.get("QuoteID", "")).strip()
            if qid not in deleted_ids:
                filtered_quotes.append(quote)

    data = {"Quotes": filtered_quotes}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ Filtered JSON written to {output_path}")
    print(f"Removed {len(deleted_ids)} potential quotes (matched count may be lower).")


excel_path = "CC_File.xlsx"


remove_deleted_quotes_stream(
    "quote.json",
    "CC_File.xlsx",
    "filtered_output.json"
)