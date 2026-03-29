import pandas as pd
import json
import random
import numpy as np
from datetime import datetime, timedelta
import copy
import os

# ===== CONFIG =====
excel_path = "Template.xlsx"         # Excel file
input_json_path = "inputTemplate.json"
batch_size =         12             # Number of records per batch
output_full = "BatchOutput_Full.json"
output_mandatory = "BatchOutput_Mandatory.json"

# Define list nodes (relative to "quote")
list_nodes = [
    ["a", "e", "t"],
    ["c", "d"]
]

# ---- Helper Functions ----
def to_date_str(val):
    if pd.isna(val) or val == "":
        return None
    if isinstance(val, datetime):
        return val.strftime("%d-%m-%Y")
    try:
        return pd.to_datetime(str(val)).strftime("%d-%m-%Y")
    except:
        return None

def random_date(start, end):
    start_dt = datetime.strptime(start, "%d-%m-%Y")
    end_dt = datetime.strptime(end, "%d-%m-%Y")
    delta = end_dt - start_dt
    if delta.days <= 0:
        return start_dt.strftime("%d-%m-%Y")
    rand_days = random.randint(0, delta.days)
    return (start_dt + timedelta(days=rand_days)).strftime("%d-%m-%Y")

# ---- Global Tracker for used AnswerList values ----
used_answerlist_tracker = {}

def get_random_value(row, answerlist_dict, current_json_value=None):
    """Choose value from AnswerList → Min/Max → Default → otherwise keep input JSON value"""
    dtype = str(row.get('datatype', '')).strip().lower()
    random_type = str(row.get('Randomation', '')).strip().lower()
    min_val = row.get('min')
    max_val = row.get('max')
    default = row.get('Default')
    ans_flag = str(row.get('AnswerList', '')).strip().upper()
    var_name = row.get('variableName', '')

    # 1️⃣ Unique AnswerList Value
    if ans_flag == "Y" and var_name in answerlist_dict and answerlist_dict[var_name]:
        all_vals = answerlist_dict[var_name]
        used_vals = used_answerlist_tracker.get(var_name, set())
        remaining_vals = [v for v in all_vals if v not in used_vals]

        if remaining_vals:
            chosen = random.choice(remaining_vals)  # change to remaining_vals[0] for sequential order
            used_vals.add(chosen)
            used_answerlist_tracker[var_name] = used_vals
        else:
            # All values used once → reset tracker and reuse
            used_answerlist_tracker[var_name] = {random.choice(all_vals)}
            chosen = list(used_answerlist_tracker[var_name])[0]

        return chosen

    # 2️⃣ Min/Max randomization
    if pd.notna(min_val) or pd.notna(max_val):
        if dtype == "number":
            min_val = float(min_val) if pd.notna(min_val) else 0
            max_val = float(max_val) if pd.notna(max_val) else min_val + 100
            if random_type == "poisson":
                lam = max((min_val + max_val)/2, 1)
                return int(np.random.poisson(lam=lam))
            elif random_type == "gaussian":
                mu = (min_val + max_val)/2
                sigma = (max_val - min_val)/6 if max_val > min_val else 1
                val = np.random.normal(mu, sigma)
                return int(max(min_val, min(max_val, val)))
            elif random_type == "bernoulli":
                return int(np.random.binomial(1, 0.5))
            else:
                return int(random.uniform(min_val, max_val))
        elif dtype == "date":
            min_str = to_date_str(min_val)
            max_str = to_date_str(max_val)
            if min_str and max_str:
                return random_date(min_str, max_str)

    # 3️⃣ Default
    if pd.notna(default) and default != "":
        if dtype in ["boolen", "boolean"]:
            return str(default).strip().lower() in ["true", "1", "yes", "y"]
        return default

    # 4️⃣ Otherwise keep input JSON value as-is
    return current_json_value

def set_nested_value(data, keys, value):
    cur = data
    for k in keys[:-1]:
        if k not in cur or not isinstance(cur[k], dict):
            cur[k] = {}
        cur = cur[k]
    cur[keys[-1]] = value

def get_nested_value(data, keys):
    cur = data
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur

def prune_json_to_mandatory(data, allowed_paths, current_path=None, is_root=True):
    """Recursively remove keys not in allowed_paths, but preserve top-level 'quote' key"""
    if current_path is None:
        current_path = []

    if isinstance(data, dict):
        keys_to_delete = []
        for k, v in data.items():
            full_path = current_path + [k]
            if any(ap[:len(full_path)] == full_path for ap in allowed_paths):
                prune_json_to_mandatory(v, allowed_paths, full_path, is_root=False)
            else:
                if not (is_root and k == "quote"):  # always keep top-level "quote"
                    keys_to_delete.append(k)
        for k in keys_to_delete:
            del data[k]
    elif isinstance(data, list):
        for item in data:
            prune_json_to_mandatory(item, allowed_paths, current_path, is_root=False)

# ---- Load Files ----
main_df = pd.read_excel(excel_path, sheet_name='Main')
answer_df = pd.read_excel(excel_path, sheet_name='AnswerList')

with open(input_json_path) as f:
    input_template = json.load(f)

# Prepare AnswerList dictionary
answerlist_dict = {}
for col in answer_df.columns:
    vals = [v for v in answer_df[col].dropna().tolist()]
    if vals:
        answerlist_dict[col] = vals

# ---- Prepare list node rows ----
def prepare_list_node_rows(df):
    list_node_rows = {}
    for ln in list_nodes:
        ln_tuple = tuple(ln)
        list_node_rows[ln_tuple] = []
        for _, row in df.iterrows():
            keys = [k for k in [row.get('sub_key1'), row.get('sub_key2'),
                                row.get('sub_key3'), row.get('variableName')]
                    if pd.notna(k)]
            if keys[:len(ln)] == ln:
                list_node_rows[ln_tuple].append(row)
    return list_node_rows

# ---- JSON generator ----
def generate_batch_json(df, output_path, answerlist_dict, template):
    list_node_rows = prepare_list_node_rows(df)
    batch_data = {"quote": []}

    for _ in range(batch_size):
        record = copy.deepcopy(template["quote"][0])

        # Step 1️⃣ — non-list fields
        for _, row in df.iterrows():
            if str(row.get('top_key')).strip() != "quote":
                continue
            keys = [k for k in [row.get('sub_key1'), row.get('sub_key2'),
                                row.get('sub_key3'), row.get('variableName')]
                    if pd.notna(k)]
            if not keys:
                continue
            is_list_node = any(keys[:len(ln)] == ln for ln in list_nodes)
            if is_list_node:
                continue

            current_json_value = get_nested_value(record, keys)
            val = get_random_value(row, answerlist_dict, current_json_value)
            if val is not None:
                set_nested_value(record, keys, val)

        # Step 2️⃣ — list nodes
        for ln in list_nodes:
            ln_tuple = tuple(ln)
            rows_for_node = list_node_rows.get(ln_tuple, [])
            if not rows_for_node:
                continue

            n_nodes = max(1, np.random.poisson(2))
            list_values = []
            for _ in range(n_nodes):
                element = {}
                for sub_row in rows_for_node:
                    key = sub_row['variableName']
                    current_val = get_nested_value(template["quote"][0], ln + [key])
                    val = get_random_value(sub_row, answerlist_dict, current_val)
                    element[key] = val
                list_values.append(element)

            parent_keys = ln[:-1]
            cur = record
            for k in parent_keys:
                if k not in cur or not isinstance(cur[k], dict):
                    cur[k] = {}
                cur = cur[k]
            cur[ln[-1]] = list_values

        batch_data["quote"].append(record)

    with open(output_path, "w") as f:
        json.dump(batch_data, f, indent=2)

    print(f"✅ Batch JSON generated: {output_path}")

# ---- Generate Full JSON ----
generate_batch_json(main_df, output_full, answerlist_dict, input_template)
