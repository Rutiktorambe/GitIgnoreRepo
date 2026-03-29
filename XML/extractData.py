import xml.etree.ElementTree as ET
import pandas as pd

def extract_data(element, path=""):
    """Recursive extraction of variables, paths, and values."""
    data = []

    # If this is the first level, don't add slash
    current_path = f"{path}/{element.tag}" if path else element.tag

    # If the element has a 'value' attribute, record it
    if "value" in element.attrib:
        data.append({
            "VariableName": element.tag,
            "Path": current_path,
            "Value": element.attrib["value"]
        })

    # Count occurrences of each child tag for indexing
    tag_counts = {}
    for child in element:
        tag_counts[child.tag] = tag_counts.get(child.tag, 0) + 1

    # Track how many times we've seen each tag while iterating
    seen_counts = {}
    for child in element:
        seen_counts[child.tag] = seen_counts.get(child.tag, 0) + 1
        if tag_counts[child.tag] > 1:
            child_path = f"{current_path}/{child.tag}[{seen_counts[child.tag]}]"
        else:
            child_path = f"{current_path}/{child.tag}"
        data.extend(extract_data(child, child_path))

    return data

# -------- MAIN ---------
input_file = "updated_output.xml"
tree = ET.parse(input_file)
root = tree.getroot()

rows = extract_data(root)

# Save to Excel
df = pd.DataFrame(rows)
df.to_excel("output.xlsx", index=False)

print("✅ Data extracted and saved to output.xlsx")
