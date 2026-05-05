#!/usr/bin/env python3
"""
King Monster Fleet - Backend Uploader
Coki script para subir entries y documents directo a Firebase Firestore.
Usa: python3 kmf_upload.py <comando> [args]

Comandos:
  add-entry <truck> <type> <amount> [desc] [date] [miles]
  add-doc <truck> <doc-key> <image-base64> [expiry]
  list-entries <truck>
  list-docs <truck>
"""

import json
import sys
import os
import requests
from datetime import datetime

# Configuracion Firebase
FIREBASE_API_KEY = "AIzaSyDkU42RrkHSRAMcxg9OG5M1GQ3up_F4y44"
FIREBASE_PROJECT_ID = "king-monster-fleet"
FIREBASE_DB = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents"

# Firestore REST API helpers
def firestore_get(collection, doc_id=None):
    url = f"{FIREBASE_DB}/{collection}"
    if doc_id:
        url += f"/{doc_id}"
    r = requests.get(url)
    if r.status_code == 200:
        return r.json()
    return None

def firestore_add(collection, data):
    """Add a document to Firestore with auto-generated ID"""
    url = f"{FIREBASE_DB}/{collection}"
    # Convertir a formato Firestore
    fs_data = to_firestore_doc(data)
    r = requests.post(url, json=fs_data)
    if r.status_code == 200:
        return r.json()
    print(f"Firestore error: {r.status_code} {r.text}")
    return None

def firestore_set(collection, doc_id, data):
    """Set a document with specific ID"""
    url = f"{FIREBASE_DB}/{collection}/{doc_id}"
    fs_data = to_firestore_doc(data)
    r = requests.patch(url, json=fs_data)
    if r.status_code == 200:
        return r.json()
    print(f"Firestore error: {r.status_code} {r.text}")
    return None

def to_firestore_doc(data):
    """Convert Python dict to Firestore Document format"""
    fields = {}
    for key, val in data.items():
        fields[key] = pyval_to_firestore(val)
    return {"fields": fields}

def pyval_to_firestore(val):
    if isinstance(val, str):
        return {"stringValue": val}
    elif isinstance(val, bool):
        return {"booleanValue": val}
    elif isinstance(val, int):
        return {"integerValue": str(val)}
    elif isinstance(val, float):
        if val == int(val):
            return {"integerValue": str(int(val))}
        return {"doubleValue": val}
    elif val is None:
        return {"nullValue": None}
    elif isinstance(val, dict):
        return {"mapValue": {"fields": {k: pyval_to_firestore(v) for k, v in val.items()}}}
    elif isinstance(val, list):
        return {"arrayValue": {"values": [pyval_to_firestore(v) for v in val]}}
    return {"stringValue": str(val)}

def get_week_key():
    """Get the current week key (Monday date)"""
    from datetime import date, timedelta
    today = date.today()
    return (today - timedelta(days=today.weekday())).isoformat()

def get_timestamp():
    """Get current timestamp for Firestore"""
    return datetime.utcnow().isoformat() + "Z"

# Commands
def cmd_add_entry(args):
    """add-entry <truck> <type> <amount> [desc] [date] [miles]"""
    if len(args) < 3:
        print("Uso: add-entry <truck> <type> <amount> [desc] [date] [miles]")
        print("  truck: truck1 | truck2")
        print("  type: rate | diesel | toll | lumper_driver | lumper_broker | eld | trailer | yarda | seguro | other")
        return
    
    truck = args[0]
    entry_type = args[1]
    amount = float(args[2])
    desc = args[3] if len(args) > 3 else ""
    date_str = args[4] if len(args) > 4 else datetime.now().strftime("%Y-%m-%d")
    miles = float(args[5]) if len(args) > 5 else None
    
    entry = {
        "truck": truck,
        "type": entry_type,
        "amount": amount,
        "desc": desc,
        "date": date_str,
        "weekKey": get_week_key(),
        "createdAt": get_timestamp()
    }
    if miles:
        entry["miles"] = miles
    
    result = firestore_add("entries", entry)
    if result:
        doc_id = result.get("name", "").split("/")[-1]
        print(f"✅ Entry added: {doc_id}")
        print(f"   Truck: {truck}")
        print(f"   Type: {entry_type}")
        print(f"   Amount: ${amount:.2f}")
        print(f"   Desc: {desc}")
        print(f"   Date: {date_str}")
        if miles:
            print(f"   Miles: {miles}")
    else:
        print("❌ Error adding entry")

def cmd_add_doc(args):
    """add-doc <truck> <doc-key> <image-base64> [expiry]"""
    if len(args) < 3:
        print("Uso: add-doc <truck> <doc-key> <image-base64> [expiry]")
        print("  doc-key: registration | smog | insurance | ifta | dot_inspect | twic | license | dot_medical")
        return
    
    truck = args[0]
    doc_key = args[1]
    image_b64 = args[2]  # This will be base64 data URL
    expiry = args[3] if len(args) > 3 else None
    
    doc_data = {
        "truck": truck,
        "docKey": doc_key,
        "image": image_b64,
        "updatedAt": get_timestamp()
    }
    if expiry:
        doc_data["expiry"] = expiry
    
    doc_id = f"{truck}_{doc_key}"
    result = firestore_set("documents", doc_id, doc_data)
    if result:
        print(f"✅ Document saved: {doc_id}")
    else:
        print("❌ Error saving document")

def get_value(field):
    for vtype in ["stringValue", "integerValue", "doubleValue", "booleanValue", "timestampValue"]:
        if vtype in field:
            return field[vtype]
    return None

def cmd_list_entries(args):
    """list-entries [truck]"""
    truck_filter = args[0] if args else None
    
    query_url = f"{FIREBASE_DB}:runQuery"
    
    structured = {"from": [{"collectionId": "entries"}]}
    if truck_filter:
        structured["where"] = {
            "fieldFilter": {
                "field": {"fieldPath": "truck"},
                "op": "EQUAL",
                "value": {"stringValue": truck_filter}
            }
        }
    structured["orderBy"] = [{"field": {"fieldPath": "createdAt"}, "direction": "DESCENDING"}]
    structured["limit"] = 50
    
    r = requests.post(query_url, json={"structuredQuery": structured})
    if r.status_code != 200:
        print(f"Error: {r.status_code} {r.text}")
        return
    
    results = r.json()
    docs = [item.get("document") for item in results if item.get("document")]
    print(f"Entries ({len(docs)}):")
    for doc in docs:
        doc_id = doc["name"].split("/")[-1]
        fields = doc.get("fields", {})
        truck = get_value(fields.get("truck", {}))
        entry_type = get_value(fields.get("type", {}))
        amt = get_value(fields.get("amount", {}))
        desc = get_value(fields.get("desc", {})) or ""
        print(f"  [{doc_id}] {truck} | {entry_type} | ${float(amt):.2f} | {desc}")

def cmd_list_docs(args):
    """list-docs [truck]"""
    truck_filter = args[0] if args else None
    
    query_url = f"{FIREBASE_DB}:runQuery"
    structured = {"from": [{"collectionId": "documents"}]}
    if truck_filter:
        structured["where"] = {
            "fieldFilter": {
                "field": {"fieldPath": "truck"},
                "op": "EQUAL",
                "value": {"stringValue": truck_filter}
            }
        }
    
    r = requests.post(query_url, json={"structuredQuery": structured})
    if r.status_code != 200:
        print(f"Error: {r.status_code} {r.text}")
        return
    
    results = r.json()
    docs = [item.get("document") for item in results if item.get("document")]
    print(f"Documents ({len(docs)}):")
    for doc in docs:
        doc_id = doc["name"].split("/")[-1]
        fields = doc.get("fields", {})
        truck = get_value(fields.get("truck", {}))
        doc_key = get_value(fields.get("docKey", {}))
        has_image = "image" in fields
        expiry = get_value(fields.get("expiry", {})) or "No expiry"
        print(f"  [{doc_id}] {truck} | {doc_key} | Image:{'Yes' if has_image else 'No'} | Exp:{expiry}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    command = sys.argv[1]
    args = sys.argv[2:]
    
    commands = {
        "add-entry": cmd_add_entry,
        "add-doc": cmd_add_doc,
        "list-entries": cmd_list_entries,
        "list-docs": cmd_list_docs,
    }
    
    if command in commands:
        commands[command](args)
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
