import pandas as pd
import xml.etree.ElementTree as ET

# Load files
mapping_df = pd.read_excel("XML_Mapping.xlsx")
csv_df = pd.read_csv("data.csv")

# Replace NaNs with empty strings
mapping_df.fillna("", inplace=True)

# Function to convert value to correct DataType
def convert_value(value, data_type, default_val, field_name):
    if value == "" or pd.isna(value):
        value = default_val

    try:
        if data_type.lower() == "integer":
            return str(int(value))
        elif data_type.lower() == "float":
            return str(float(value))
        elif data_type.lower() == "boolean":
            return str(value).lower() in ["true", "1", "yes"]
        elif data_type.lower() == "string":
            return str(value)
        else:
            raise ValueError(f"Unsupported datatype '{data_type}' for field '{field_name}'")
    except Exception as e:
        raise ValueError(f"Value error for field '{field_name}': {e}")

# Build XML structure tree
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

# Recursive XML builder with validation
def build_element(var_name, children, row):
    elem = ET.Element(var_name)

    mapping_row = mapping_df[mapping_df["VariableName"] == var_name].iloc[0]
    csv_col = mapping_row["CSV_Column"]
    default_val = mapping_row["DefaultValue"]
    data_type = mapping_row["DataType"]
    
    if not children:  # Leaf
        raw_val = row.get(csv_col, "") if csv_col else ""
        converted_val = convert_value(raw_val, data_type, default_val, var_name)
        elem.text = converted_val
    else:
        for child_var, child_children in children.items():
            child_elem = build_element(child_var, child_children, row)
            elem.append(child_elem)
    return elem

# Build final XML
root = ET.Element("Root")

for idx, row in csv_df.iterrows():
    for top_var, sub_children in xml_structure.items():
        try:
            elem = build_element(top_var, sub_children, row)
            root.append(elem)
        except ValueError as ve:
            print(f"[Row {idx+1} Error] {ve}")

# Write to XML
tree = ET.ElementTree(root)
tree.write("output2.xml", encoding="utf-8", xml_declaration=True)
