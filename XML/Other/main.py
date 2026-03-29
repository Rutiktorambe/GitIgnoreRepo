import pandas as pd
import xml.etree.ElementTree as ET

# Load files
mapping_df = pd.read_excel("XML_Mapping.xlsx")
csv_df = pd.read_csv("data.csv")

# Clean up NA values
mapping_df.fillna("", inplace=True)

# Build XML tree structure from mapping
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

# Structure like: {'Employee': {'ID': {}, 'Address': {'City': {}, 'Pincode': {}, 'Location': {'Region': {}}}}}
structure = build_structure(mapping_df)

# Recursive function to build XML element
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

# Generate XML
root = ET.Element("Root")
for _, row in csv_df.iterrows():
    for top_level, sub in structure.items():
        elem = build_element(top_level, sub, row)
        root.append(elem)

# Write to file
tree = ET.ElementTree(root)
tree.write("output.xml", encoding="utf-8", xml_declaration=True)
