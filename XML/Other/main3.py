import pandas as pd
import xml.etree.ElementTree as ET
import os

# Load mapping file and data
mapping_df = pd.read_excel("XML_Mapping.xlsx")
csv_df = pd.read_csv("data.csv")

# Clean up NA values in mapping
mapping_df.fillna("", inplace=True)

# Build nested XML structure
def build_structure(mapping):
    tree = {}

    def insert(node, parent, child):
        for key in node:
            if key == parent:
                node[key].setdefault(child, {})
                return True
            if insert(node[key], parent, child):
                return True
        return False

    for _, row in mapping.iterrows():
        var = row['VariableName']
        parent = row['Parent']
        if not parent:
            tree.setdefault(var, {})
        else:
            if not insert(tree, parent, var):
                raise Exception(f"Parent '{parent}' not found for '{var}'")
    return tree

xml_structure = build_structure(mapping_df)

# Build XML element recursively
def build_element(name, children, row):
    elem = ET.Element(name)

    mapping_row = mapping_df[mapping_df["VariableName"] == name].iloc[0]
    csv_col = mapping_row["CSV_Column"]
    default_val = mapping_row["DefaultValue"]

    if not children:  # Leaf node
        value = row.get(csv_col) if csv_col else ""
        if pd.isna(value) or value == "":
            value = default_val
        elem.text = str(value)
    else:
        for child_name, sub_children in children.items():
            child_elem = build_element(child_name, sub_children, row)
            elem.append(child_elem)
    return elem

# Output directory
output_dir = "xml_output"
os.makedirs(output_dir, exist_ok=True)

# Generate individual XML files
for idx, row in csv_df.iterrows():
    for root_tag, sub_structure in xml_structure.items():
        root_elem = build_element(root_tag, sub_structure, row)

        # Create tree and save to file
        tree = ET.ElementTree(root_elem)

        # You can customize file naming with ID or index
        file_name = f"{root_tag}_{idx+1}.xml"
        file_path = os.path.join(output_dir, file_name)
        tree.write(file_path, encoding="utf-8", xml_declaration=True)

        print(f"Generated: {file_path}")
