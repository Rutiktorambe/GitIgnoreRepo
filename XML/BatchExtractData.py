import xml.etree.ElementTree as ET
import pandas as pd

def extract_data(element, path="", sr_no=""):
    """Recursive extraction of variables, paths, and values."""
    data = []

    # Build current path
    current_path = f"{path}/{element.tag}" if path else element.tag

    # If the element has a 'value' attribute, record it
    if "value" in element.attrib:
        data.append({
            "Sr.No": sr_no,
            "VariableName": element.tag,
            "Path": current_path,
            "Value": element.attrib["value"]
        })

    # Count child tags for index tracking
    tag_counts = {}
    for child in element:
        tag_counts[child.tag] = tag_counts.get(child.tag, 0) + 1

    # Track occurrence count for each tag
    seen_counts = {}
    for child in element:
        seen_counts[child.tag] = seen_counts.get(child.tag, 0) + 1
        if tag_counts[child.tag] > 1:
            child_path = f"{current_path}/{child.tag}[{seen_counts[child.tag]}]"
        else:
            child_path = f"{current_path}/{child.tag}"
        data.extend(extract_data(child, child_path, sr_no))

    return data

# -------- MAIN ---------
input_file = "batch.xml"
tree = ET.parse(input_file)
root = tree.getroot()

rows = []
quotes = root.findall(".//Quote")

for i, quote in enumerate(quotes, start=1):
    sr_no = f"TS{i:02d}"  # TS01, TS02, ...
    rows.extend(extract_data(quote, path="Root/Quotes/Quote", sr_no=sr_no))

# Create DataFrame
df = pd.DataFrame(rows)

# Save to Excel
df.to_excel("output_batch.xlsx", index=False)

print("✅ Data extracted and saved to output.xlsx")
