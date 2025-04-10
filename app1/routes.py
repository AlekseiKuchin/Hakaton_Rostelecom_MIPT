from flask import Blueprint, jsonify, request
from flasgger import swag_from
from app.services.log_service import get_logs

api_blueprint = Blueprint("api", __name__)

@api_blueprint.route("/logs", methods=["GET"])
@swag_from({
    'tags': ['Logs'],
    'description': 'Get logs for a specific date',
    'parameters': [
        {
            'name': 'date',
            'in': 'query',
            'type': 'string',
            'required': False,
            'description': 'Date of logs in the format YYYY-MM-DD'
        }
    ],
    'responses': {
        '200': {
            'description': 'Logs fetched successfully',
            'schema': {
                'type': 'object',
                'properties': {
                    'status': {'type': 'string'},
                    'data': {'type': 'array'}
                }
            }
        },
        '500': {
            'description': 'Error fetching logs'
        }
    }
})
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
