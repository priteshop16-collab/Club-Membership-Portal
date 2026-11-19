import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from supabase import Client, create_client
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Replace with your actual credentials or configure in environment
SUPABASE_URL = "https://sccnavjqbrqvnfxyqfbz.supabase.co"
SUPABASE_KEY = "sb_publishable_5BQuUB91NMLzM5LNCW2I3Q_0vINIrYD"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


@app.route("/api/signup", methods=["POST"])
def signup():
  data = request.get_json() or {}
  identifier = data.get("identifier", "").strip()
  name = data.get("name", "").strip()
  password = data.get("password", "")

  if not identifier or not name or not password:
    return jsonify({"error": "All fields are required"}), 400

  existing = (
      supabase.table("members")
      .select("id")
      .eq("identifier", identifier)
      .execute()
  )
  if existing.data and len(existing.data) > 0:
    return (
        jsonify(
            {
                "error": (
                    "This User ID or Phone number is already registered."
                )
            }
        ),
        400,
    )

  password_hash = generate_password_hash(password)

  # Default initial payment ledger for current year/month
  initial_history = [{
      "month": "Current Month (₹100)",
      "status": "Unpaid",
      "date": "-",
      "due": 100,
  }]

  new_member = {
      "identifier": identifier,
      "name": name,
      "password_hash": password_hash,
      "is_admin": False,
      "payment_history": initial_history,
  }

  response = supabase.table("members").insert(new_member).execute()

  if response.data:
    created = response.data[0]
    return jsonify({
        "message": "Registration successful",
        "user": {
            "id": created["identifier"],
            "name": created["name"],
            "isAdmin": created["is_admin"],
            "paymentHistory": created["payment_history"],
        },
    }), 201

  return jsonify({"error": "Failed to create account"}), 500


@app.route("/api/login", methods=["POST"])
def login():
  data = request.get_json() or {}
  identifier = data.get("identifier", "").strip()
  password = data.get("password", "")

  if not identifier or not password:
    return jsonify({"error": "Identifier and password are required"}), 400

  response = (
      supabase.table("members")
      .select("*")
      .eq("identifier", identifier)
      .execute()
  )

  if not response.data or len(response.data) == 0:
    return jsonify({"error": "Invalid User ID or password"}), 401

  member = response.data[0]

  if check_password_hash(member["password_hash"], password):
    return jsonify({
        "message": "Login successful",
        "user": {
            "id": member["identifier"],
            "name": member["name"],
            "isAdmin": member["is_admin"],
            "paymentHistory": member.get("payment_history", []),
        },
    }), 200

  return jsonify({"error": "Invalid User ID or password"}), 401


@app.route("/api/members", methods=["GET"])
def get_members():
  response = (
      supabase.table("members")
      .select("identifier, name, is_admin, payment_history, created_at")
      .order("created_at", desc=False)
      .execute()
  )

  formatted_members = []
  if response.data:
    for m in response.data:
      formatted_members.append({
          "id": m["identifier"],
          "name": m["name"],
          "isAdmin": m["is_admin"],
          "paymentHistory": m.get("payment_history", []),
      })

  return jsonify(formatted_members), 200


@app.route("/api/members/<identifier>/toggle", methods=["PATCH"])
def toggle_payment(identifier):
  # Fetch member record
  response = (
      supabase.table("members")
      .select("payment_history")
      .eq("identifier", identifier)
      .execute()
  )

  if not response.data or len(response.data) == 0:
    return jsonify({"error": "Member not found"}), 404

  history = response.data[0].get("payment_history", [])
  if not history:
    history = [{
        "month": "Current Month (₹100)",
        "status": "Unpaid",
        "date": "-",
        "due": 100,
    }]

  # Toggle status of the latest month record
  current_status = history[0].get("status", "Unpaid")
  if current_status == "Paid":
    history[0]["status"] = "Unpaid"
    history[0]["date"] = "-"
    history[0]["due"] = 100
  else:
    history[0]["status"] = "Paid"
    history[0]["date"] = "2026-11-14"  # Current payment timestamp
    history[0]["due"] = 0

  update_res = (
      supabase.table("members")
      .update({"payment_history": history})
      .eq("identifier", identifier)
      .execute()
  )

  if update_res.data:
    return jsonify({
        "message": "Payment status updated",
        "identifier": identifier,
        "paymentHistory": history,
    }), 200

  return jsonify({"error": "Failed to update status"}), 500


@app.route("/api/members/<identifier>", methods=["DELETE"])
def delete_member(identifier):
  # Delete duplicate or specified member entry
  response = (
      supabase.table("members").delete().eq("identifier", identifier).execute()
  )
  return jsonify({"message": "Member removed successfully"}), 200


import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
