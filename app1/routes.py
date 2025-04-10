from flask import Blueprint, jsonify, request
from app.services.log_service import get_logs

api_blueprint = Blueprint("api", __name__)

@api_blueprint.route("/logs", methods=["GET"])
def logs():
    try:
        date = request.args.get("date")
        logs_data = get_logs(date)
        return jsonify({
            "status": "success",
            "data": logs_data
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
