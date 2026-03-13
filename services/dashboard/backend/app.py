import os

from flask import Flask, abort, jsonify, request, send_file

import db
import mqtt_publisher

PER_PAGE = 48
SHARED_FRAMES = os.getenv("SHARED_FRAMES", "/shared_frames")

app = Flask(__name__, template_folder="templates", static_folder="static")


@app.route("/")
def index():
    return send_file(os.path.join(app.root_path, "static", "dist", "index.html"))


@app.route("/api/faces")
def list_faces():
    status = request.args.get("status", "").strip()
    search = request.args.get("search", "").strip()
    try:
        page = max(1, int(request.args.get("page", "1")))
        per_page = min(100, max(10, int(request.args.get("per_page", "50"))))
    except ValueError:
        abort(400)

    faces, total, total_pages = db.list_faces(status, search, page, per_page)

    return jsonify({"faces": faces, "total": total, "page": page, "per_page": per_page})


@app.route("/api/faces/<int:face_id>/image")
def get_face_image(face_id: int):
    path = db.get_image_path(face_id)
    if not path:
        abort(404)
    real_path = os.path.realpath(path)
    allowed_dir = os.path.realpath(SHARED_FRAMES)
    if not real_path.startswith(allowed_dir + os.sep):
        abort(403)
    if not os.path.isfile(real_path):
        abort(404)
    return send_file(real_path, mimetype="image/jpeg")


@app.route("/api/camera/latest")
def camera_latest():
    path = os.path.join(SHARED_FRAMES, "collector", "latest.jpg")
    if not os.path.isfile(path):
        abort(404)
    return send_file(path, mimetype="image/jpeg", max_age=0)


@app.route("/api/faces/bulk-assign", methods=["POST"])
def bulk_assign():
    data = request.get_json(force=True) or {}
    ids = data.get("ids", [])
    assigned_name = str(data.get("assigned_name", "")).strip()
    if not ids or not assigned_name:
        abort(400)
    mqtt_publisher.publish_bulk_update(ids, {"assigned_name": assigned_name})
    return jsonify({"updated": len(ids)})


@app.route("/api/faces/bulk-import", methods=["POST"])
def bulk_import():
    data = request.get_json(force=True) or {}
    ids = data.get("ids", [])
    if not ids:
        abort(400)

    rows = db.get_faces_for_import(ids)
    submitted, errors = 0, []

    for row in rows:
        name = row["assigned_name"] or row["suggested_name"]
        if not name:
            errors.append({"id": row["id"], "error": "nessun nome assegnato"})
            continue
        mqtt_publisher.publish_bulk_update([row["id"]], {"status": "importing"})
        mqtt_publisher.publish_import(row["id"], row["image_path"], name)
        submitted += 1

    missing = set(ids) - {r["id"] for r in rows}
    errors += [{"id": i, "error": "non trovato"} for i in missing]

    return jsonify({"submitted": submitted, "errors": errors})


@app.route("/api/faces/bulk-discard", methods=["POST"])
def bulk_discard():
    data = request.get_json(force=True) or {}
    ids = data.get("ids", [])
    if not ids:
        abort(400)
    mqtt_publisher.publish_bulk_delete(ids)
    return jsonify({"updated": len(ids)})


@app.route("/api/persons")
def list_persons():
    persons = db.list_persons()
    known_names = db.get_known_names()
    return jsonify({"persons": persons, "known_names": known_names})


@app.route("/api/persons/auto-open", methods=["POST"])
def toggle_auto_open():
    data = request.get_json(force=True) or {}
    name = str(data.get("name", "")).strip()
    auto_open = bool(data.get("auto_open", False))
    if not name:
        abort(400)
    db.set_auto_open(name, auto_open)
    return jsonify({"name": name, "auto_open": auto_open})


if __name__ == "__main__":
    db.init_db()
    mqtt_publisher.start()
    app.run(host="0.0.0.0", port=5000, threaded=True, debug=False)

